"""
    B站直播
"""
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import Type
from ....utils.rss import Rss, RssChannelData
from ....model import SubscribeModel
from ...factory import channel_factory
from ....logger import logger
from ....exception import MatcherErrorFinsh
from . import RsshubChannelSession, RsshubChannel, Options, Option


class BilibiliLiveOptions(Options):
    display_des: bool = Option.new(False, ["简介", "备注"])
    title: bool = Option.new(True, ["标题"])


class RsshubBilibiliLiveChannel(RsshubChannel):

    @property
    def aliases(self) -> List[str]:
        """别名列表"""
        return ["bilibili直播"]

    @property
    def name(self) -> str:
        """中文标识名"""
        return "B站直播"

    @property
    def channel_subtype(self) -> str:
        return "bilibili_live"

    @property
    def poll_interval(self) -> Tuple[int, int]:
        """请求间隔范围 ms"""
        return (5000, 6000)

    @property
    def options_cls(self) -> Optional[Type[Options]]:
        return BilibiliLiveOptions

    def subscribe_str_to_path(self, subscribe_str: str) -> str:
        arg = subscribe_str
        if arg.startswith('https://live.bilibili.com/'):
            arg = arg.split('/')[-1]
            arg = arg.split('?')[0]
            arg = '/bilibili/live/room/' + arg
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
        if path.startswith(
                '/bilibili/live/room/'):
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
        if now_time - now_data.updated > 30 * 60 * 1000:
            """不推送延迟超过30分钟的数据"""
            return

        if len(now_data.entries) != 1:
            """关播或未开播则不推送"""
            return
        item = now_data.entries[0]
        up_name = now_data.title_full.replace("直播间开播状态", "").strip()  # up主名称
        live_name = item.title_full.strip()[:-20]
        if len(last_data.entries) == 0:
            """开播"""
            for subscribe in subscribes:
                try:
                    option = BilibiliLiveOptions()
                    option._init_from_dict(subscribe.options)
                    if option.display_des:
                        msg = "{0}开播啦！\n{1}".format(
                            up_name,
                            item.des_full[:15].strip() +
                            ('...' if len(item.des_full) > 15 else ''),
                        )
                    else:
                        msg = "{0}开播啦！{1}".format(
                            up_name,
                            live_name,
                        )
                    msg = await self.ob_v11_message_conversion(subscribe, msg)
                    if not await self.send_msg(subscribe, msg):
                        logger.warning("{}({})消息推送失败：{}", self.channel_id,
                                       now_data.source_url, str(msg))
                except Exception as e:
                    logger.opt(exception=True).error("{}({}) 推送B站直播消息时异常",
                                                     self.channel_id,
                                                     now_data.source_url)
            return
        last_item = now_data.entries[0]
        last_live_name = last_item.title_full.strip()[:-20]
        
        if live_name != last_live_name:
            """直播标题更新"""
            msg = "{0}的直播标题改为{1}".format(
                up_name,
                live_name,
            )
            for subscribe in subscribes:
                try:
                    option = BilibiliLiveOptions()
                    option._init_from_dict(subscribe.options)
                    if not option.title:
                        continue
                    msg = await self.ob_v11_message_conversion(subscribe, msg)
                    if not await self.send_msg(subscribe, msg):
                        logger.warning("{}({})消息推送失败：{}", self.channel_id,
                                       now_data.source_url, str(msg))
                except Exception as e:
                    logger.opt(exception=True).error("{}({}) 推送B站直播消息时异常",
                                                     self.channel_id,
                                                     now_data.source_url)


channel_factory.register(RsshubBilibiliLiveChannel())
