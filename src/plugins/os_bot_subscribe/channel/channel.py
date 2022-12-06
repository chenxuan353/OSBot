"""
    订阅的频道基类
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union
from typing_extensions import Self
from ..utils.options import Options
from ..logger import logger
from ..model import SubscribeModel


from ...os_bot_base import Session
from ...os_bot_base.session import StoreSerializable
from ...os_bot_base.depends import get_plugin_session
from ...os_bot_base.notice import BotSend
from ...os_bot_base.util import plug_is_disable


@dataclass
class SubscribeInfoData(StoreSerializable):
    title: str = field(default="")
    des: str = field(default="")


class ChannelSession(Session):

    subscribe_info_map: Dict[str, SubscribeInfoData]

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.subscribe_info_map = {}

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        load_map: Dict[str,
                       Dict[str,
                            Any]] = self.subscribe_info_map  # type: ignore
        self.subscribe_info_map = {}
        for key in load_map:
            self.subscribe_info_map[key] = SubscribeInfoData._load_from_dict(
                load_map[key])
        return self

    def set_subscribe_info(self, channel: "Channel", subscribe: str,
                           info: SubscribeInfoData):
        self.subscribe_info_map[
            f"{channel.channel_type}-{channel.channel_subtype}-{subscribe}"] = info

    def get_subscribe_info(self, channel: "Channel",
                           subscribe: str) -> Optional[SubscribeInfoData]:
        return self.subscribe_info_map.get(
            f"{channel.channel_type}-{channel.channel_subtype}-{subscribe}",
            None)

    def clear_subscribe_info(self):
        self.subscribe_info_map.clear()

    async def _unlock(self) -> None:
        await self._session_manage._hook_session_activity(self.key)


class Channel:

    def __init__(self) -> None:
        pass

    @property
    def aliases(self) -> List[str]:
        """别名列表"""
        return []

    @property
    def name(self) -> str:
        """中文标识名"""
        raise NotImplementedError("need implemented function!")

    @property
    def channel_session_class(self) -> Type[ChannelSession]:
        return ChannelSession

    @property
    def channel_type(self) -> str:
        raise NotImplementedError("need implemented function!")

    @property
    def channel_subtype(self) -> str:
        raise NotImplementedError("need implemented function!")

    @property
    def options_cls(self) -> Optional[Type[Options]]:
        return None

    @property
    def channel_id(self) -> str:
        return f"{self.channel_type}_{self.channel_subtype}"

    async def precheck(self, subscribe_str: str, option_str: str,
                 state: Dict[str, Any], session: ChannelSession) -> bool:
        """预处理，返回值决定是否使用此频道订阅"""
        raise NotImplementedError("need implemented function!")

    async def deal_subscribe(self, subscribe_str: str, state: Dict[str, Any],
                       session: ChannelSession) -> str:
        """解析唯一订阅ID"""
        raise NotImplementedError("need implemented function!")

    async def subscribe_update(self) -> None:
        """订阅更新的钩子函数"""

    def get_subscribe_info(
            self, subscribe: str,
            session: ChannelSession) -> Optional[SubscribeInfoData]:
        """通过唯一订阅ID获取订阅信息"""
        return session.get_subscribe_info(self, subscribe)

    def deal_options(
            self, subscribe: SubscribeModel, option_str: str,
            session: ChannelSession) -> Dict[str, Union[str, int, bool]]:
        """预处理通过后执行，解析订阅配置"""
        if self.options_cls is None:
            return {}
        options_ins = self.options_cls._load_from_dict(subscribe.options)
        options_ins.matcher_options(option_str)
        return options_ins._serializable()

    def update_options(
            self, subscribe: SubscribeModel, option_str: str,
            session: ChannelSession) -> Dict[str, Union[str, int, bool]]:
        """更新订阅配置"""
        if self.options_cls is None:
            return {}
        options_ins = self.options_cls._load_from_dict(subscribe.options)
        options_ins.matcher_options(option_str)
        return options_ins._serializable()

    def options_to_string(self, options: Dict[str, Union[str, int, bool]],
                          session: ChannelSession) -> str:
        """选项转字符串"""
        if self.options_cls is None:
            return ""
        options_ins = self.options_cls._load_from_dict(options)
        return str(options_ins)

    async def get_session(self) -> ChannelSession:
        """获取频道session"""
        return await get_plugin_session(self.channel_session_class
                                        )  # type: ignore

    async def clear(self):
        """清空频道快速查询缓存"""
        session = await self.get_session()
        session.clear_subscribe_info()

    async def send_msg(self, subscribe: SubscribeModel, message: Any) -> bool:
        """尽力发送消息，失败返回False"""
        if await plug_is_disable("os_bot_subscribe", subscribe.group_mark):
            logger.info("因组 {} 的订阅插件被关闭，转推消息推送取消。(相关订阅 {})",
                        subscribe.group_mark, subscribe.id)
            return True
        return await BotSend.send_msg(subscribe.bot_type, subscribe.send_param,
                                      message)
