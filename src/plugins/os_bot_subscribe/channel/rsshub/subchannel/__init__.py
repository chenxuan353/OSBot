import random
from nonebot.adapters.onebot import v11
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from ....utils.rss import Rss, RssChannelData, GeneralHTMLParser
from ....model import SubscribeModel
from ....utils.options import Options
from ....exception import BaseException
from ...channel import Channel as BaseChannel, ChannelSession as BaseChannelSession, SubscribeInfoData
from ..config import config

from .....os_bot_base.adapter import V11Adapter


class RsshubChannelSession(BaseChannelSession):

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)


class RsshubChannel(BaseChannel):

    _CHANNEL_TYPE: str = "rsshub"

    def __init__(self) -> None:
        super().__init__()

    @property
    def aliases(self) -> List[str]:
        """别名列表"""
        return ["rss"]

    @property
    def name(self) -> str:
        """中文标识名"""
        return "Rsshub"

    @property
    def channel_type(self) -> str:
        return self._CHANNEL_TYPE

    @property
    def poll_interval(self) -> Tuple[int, int]:
        """请求间隔范围 ms"""
        return (1000, 1000)

    async def subscribe_update(self) -> None:
        """rss订阅在更新时更新缓存"""
        from ..polling import rsshub_subscribe_invalid_subtype_cache
        rsshub_subscribe_invalid_subtype_cache(self.channel_subtype)

    @property
    def channel_session_class(self) -> Type[RsshubChannelSession]:
        return RsshubChannelSession

    @property
    def channel_subtype(self) -> str:
        raise NotImplementedError("need implemented function!")

    @property
    def options_cls(self) -> Optional[Type[Options]]:
        return None

    async def precheck(self, subscribe_str: str, option_str: str,
                 state: Dict[str, Any], session: RsshubChannelSession) -> bool:
        raise NotImplementedError("need implemented function!")

    async def deal_subscribe(self, subscribe_str: str, state: Dict[str, Any],
                       session: RsshubChannelSession) -> str:
        raise NotImplementedError("need implemented function!")

    @property
    def rss_cls(self) -> Type[Rss]:
        return Rss

    def subscribe_to_rsshub_path(self, subscribe: str,
                                 session: RsshubChannelSession) -> str:
        """订阅ID转Rsshub路径"""
        return subscribe

    async def polling_update(self, subscribes: List[SubscribeModel],
                             last_data: RssChannelData,
                             now_data: RssChannelData, last_update_time: int,
                             now_time: int):
        """
            RSS轮询更新

            需要判断哪些
        """
        raise NotImplementedError("need implemented function!")

    async def ob_v11_message_conversion(self, subscribe: SubscribeModel,
                                        msg: Union[v11.Message, str]) -> Any:
        """
            通过onebot v11 消息数据转换为特定场景消息
        """
        if subscribe.bot_type == V11Adapter.get_type():
            return msg

        raise BaseException("不支持推送消息的Bot类型")

    async def rss_text_to_send_message(self, text: str) -> v11.Message:
        """将rss html文本转换为待发送消息"""

        # def handle_image(url: str):
        #     return v11.MessageSegment.image(url)

        # parser = GeneralHTMLParser(handle_image=handle_image)
        parser = GeneralHTMLParser()
        
        parser.feed(text)
        return parser.message

    async def test_path(self, path: str):
        """通过标准rss path测试连通性 如果一切正常则返回None，如果出现错误，则返回错误原因。"""
        if not config.os_subscribe_rsshub_enable:
            return "rsshub订阅未开启"
        urls = config.os_subscribe_rsshub_urls
        
        rss = self.rss_cls(
            urls[random.randint(0, len(urls) - 1)],
            path,
            source_type=self.channel_type,
            source_subtype=self.channel_subtype
        )

        return await rss.test()


from ....utils.options import Option
