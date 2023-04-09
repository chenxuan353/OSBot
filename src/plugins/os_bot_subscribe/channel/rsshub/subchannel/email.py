"""
    爱丽丝组定制的邮箱推送
"""
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import Type
from ....utils.rss import Rss, RssChannelData, RssItemData
from ....model import SubscribeModel
from ...factory import channel_factory
from ....logger import logger
from ....exception import MatcherErrorFinsh
from . import RsshubChannelSession, RsshubChannel, Options


class EmailAliceOptions(Options):
    pass


class RsshubEmailAliceChannel(RsshubChannel):

    @property
    def aliases(self) -> List[str]:
        """别名列表"""
        return ["邮件推送"]

    @property
    def name(self) -> str:
        """中文标识名"""
        return "邮件"

    @property
    def channel_subtype(self) -> str:
        return "email"

    @property
    def options_cls(self) -> Optional[Type[Options]]:
        return EmailAliceOptions

    @property
    def poll_interval(self) -> Tuple[int, int]:
        """请求间隔范围 ms"""
        return (5000, 6000)

    def subscribe_str_to_path(self, subscribe_str: str) -> str:
        arg = subscribe_str.strip()
        if arg.endswith('@126.com'):
            arg = arg.split('/')[-1]
            arg = arg.split('?')[0]
            arg = '/mail/imap/' + arg
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
                '/mail/imap/'):
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

        for data in update_data:

            msg = "{0}更新了~\n{1}".format(
                now_data.title_full, await
                self.rss_text_to_send_message(data.des_full.replace("\n\n", "")))

            for subscribe in subscribes:
                try:
                    option = EmailAliceOptions()
                    option._init_from_dict(subscribe.options)
                    msg = await self.ob_v11_message_conversion(subscribe, msg)
                    if not await self.send_msg(subscribe, msg):
                        logger.warning("{}({})消息推送失败：{}", self.channel_id,
                                       now_data.source_url, str(msg))
                except Exception as e:
                    logger.opt(exception=True).error("{}({}) 推送邮件消息时异常",
                                                     self.channel_id,
                                                     now_data.source_url)

channel_factory.register(RsshubEmailAliceChannel())
