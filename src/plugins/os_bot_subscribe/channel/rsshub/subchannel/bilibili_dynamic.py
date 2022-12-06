"""
    B站动态
"""
import cv2
import numpy
import re
import aiohttp
import base64
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import Type
from cacheout.memoization import lru_memoize
from ....utils.rss import Rss, RssChannelData, RssItemData
from ....model import SubscribeModel
from ...factory import channel_factory
from ....logger import logger
from ....exception import MatcherErrorFinsh
from . import RsshubChannelSession, RsshubChannel, Options, Option, v11, GeneralHTMLParser


def img_resize(image, width_new, height_new):
    height, width = image.shape[0], image.shape[1]
    # 判断图片的长宽比率
    if width / height >= width_new / height_new:
        img_new = cv2.resize(image,
                             (width_new, int(height * width_new / width)))
    else:
        img_new = cv2.resize(image,
                             (int(width * height_new / height), height_new))
    return img_new


@lru_memoize(maxsize=256)
async def download_with_resize_to_base64(url: str, width: int,
                                         height: int) -> str:
    try:
        req = aiohttp.request("get",
                              url,
                              timeout=aiohttp.ClientTimeout(total=15))
        async with req as resp:
            code = resp.status
            if code != 200:
                raise Exception("获取图片失败，重新试试？")
            np_array = numpy.asarray(bytearray(await resp.read()),
                                     dtype="uint8")
            img = cv2.imdecode(np_array, cv2.IMREAD_UNCHANGED)
            img_new = img_resize(img, width, height)
            image = cv2.imencode('.png', img_new)[1]
            urlbase64 = str(base64.b64encode(image), "utf-8")
    except Exception as e:
        logger.warning("图片下载失败：{} | {}", e.__class__.__name__, e)
        return ""
    return urlbase64


def download_with_resize_to_base64_invaild(url: str, width: int, height: int):
    key = download_with_resize_to_base64.cache_key(url, width, height)
    download_with_resize_to_base64.cache.delete(key)


class BilibiliDynamicOptions(Options):
    contribute: bool = Option.new(True, ["投稿", "视频"])
    only_japanese: bool = Option.new(False, ["仅日文", "仅日语"])
    share_and_forward: bool = Option.new(False, ["转发", "分享"])


class RsshubBilibiliDynamicChannel(RsshubChannel):

    JP_REGEX = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7A3]')

    @property
    def aliases(self) -> List[str]:
        """别名列表"""
        return ["bilibili动态"]

    @property
    def name(self) -> str:
        """中文标识名"""
        return "B站动态"

    @property
    def poll_interval(self) -> Tuple[int, int]:
        """请求间隔范围 ms"""
        return (15000, 20000)

    @property
    def channel_subtype(self) -> str:
        return "bilibili_dynamic"

    @property
    def options_cls(self) -> Optional[Type[Options]]:
        return BilibiliDynamicOptions

    def subscribe_str_to_path(self, subscribe_str: str) -> str:
        arg = subscribe_str
        if arg.startswith('https://space.bilibili.com/'):
            arg = arg.replace('/dynamic', '')
            arg = arg.split('/')[-1]
            arg = arg.split('?')[0]
            arg = '/bilibili/user/dynamic/' + arg
        if arg.startswith('https://rsshub.app') or arg.startswith(
                'http://rsshub.app'):
            arg = arg.replace('https://rsshub.app', '')
            arg = arg.replace('http://rsshub.app', '')
        if not arg.startswith('/'):
            arg = '/' + arg
        return arg

    async def precheck(self, subscribe_str: str, option_str: str,
                       state: Dict[str, Any],
                       session: RsshubChannelSession) -> bool:
        path = self.subscribe_str_to_path(subscribe_str)
        if path.startswith('/bilibili/user/dynamic/'):
            result = await self.test_path(path)
            if not result:
                return True
            raise MatcherErrorFinsh(result)
        return False

    async def deal_subscribe(self, subscribe_str: str, state: Dict[str, Any],
                             session: RsshubChannelSession) -> str:
        path = self.subscribe_str_to_path(subscribe_str)
        return path

    @property
    def rss_cls(self) -> Type[Rss]:
        return Rss

    async def polling_update(self, subscribes: List[SubscribeModel],
                             last_data: RssChannelData,
                             now_data: RssChannelData, last_update_time: int,
                             now_time: int):
        """
            RSS轮询更新

            需要判断哪些
        """
        update_data: List[RssItemData] = []
        for data in now_data.entries:
            if data.published < last_data.updated:
                """不推送已经更新过的数据"""
                continue
            if now_time - data.published > 30 * 60 * 1000:
                """不推送延迟超过30分钟的数据"""
                continue

            skip = False
            for last_data_unit in last_data.entries:
                if data.uuid == last_data_unit.uuid:
                    logger.debug("{}({}) 重复的元素 {}", self.channel_id,
                                 now_data.source_url, data.uuid)
                    skip = True
                    break
            if skip:
                continue
            update_data.append(data)

        if not update_data:
            # 没有待更新数据
            return

        class UpdateType:
            normal: str = "normal"
            contribute: str = "contribute"
            share_and_forward: str = "share_and_forward"

        author_name = now_data.title_full.replace(" 的 bilibili 动态", "")

        for data in update_data:
            update_type = UpdateType.normal
            title_full = data.title_full.strip()
            if title_full == "转发动态" or title_full == "分享动态":
                update_type = UpdateType.share_and_forward
                msg = "{0}的转发了一条动态\n{1}".format(
                    author_name,
                    await self.rss_text_to_send_message(data.des_source),
                )
            elif title_full.find('/bfs/archive/') != -1:
                update_type = UpdateType.contribute
                msg = "{0}投稿啦\n{1}\n{2}".format(author_name, data.title_full,
                                                data.link)
            else:
                msg = "{0}的动态~\n{1}\n{2}".format(
                    author_name, await
                    self.rss_text_to_send_message(data.des_source), data.link)

            for subscribe in subscribes:
                try:
                    option = BilibiliDynamicOptions()
                    option._init_from_dict(subscribe.options)
                    if update_type == UpdateType.share_and_forward and not option.share_and_forward:
                        continue
                    if update_type == UpdateType.contribute and not option.contribute:
                        continue
                    if update_type == UpdateType.normal and option.only_japanese:
                        if not self.JP_REGEX.search(now_data.des_full):
                            continue
                    msg = await self.ob_v11_message_conversion(subscribe, msg)
                    if not await self.send_msg(subscribe, msg):
                        logger.warning("{}({})消息推送失败：{}", self.channel_id,
                                       now_data.source_url, str(msg))
                except Exception as e:
                    logger.opt(exception=True).error("{}({}) 推送B站动态消息时异常",
                                                     self.channel_id,
                                                     now_data.source_url)

    async def rss_text_to_send_message(self, text: str) -> v11.Message:
        """将rss html文本转换为待发送消息"""

        def handle_image(url: str):
            return v11.MessageSegment.image(url)

        parser = GeneralHTMLParser(handle_image=handle_image)

        parser.feed(text)
        rtnmessage = v11.Message()
        message = v11.Message(parser.message)
        for msgseg in message:
            if msgseg.is_text():
                rtnmessage += msgseg
            elif msgseg.type == "image":
                url = msgseg.data.get("file", "")
                if url.find("/bfs/emote") != -1:
                    imgb64 = await download_with_resize_to_base64(url, 25, 25)
                    if imgb64:
                        rtnmessage += v11.MessageSegment.image(
                            f"base64://{imgb64}")
                    else:
                        # 无效错误的转换结果
                        download_with_resize_to_base64_invaild(url, 25, 25)
                        rtnmessage += msgseg
                else:
                    rtnmessage += msgseg
        return rtnmessage


channel_factory.register(RsshubBilibiliDynamicChannel())
