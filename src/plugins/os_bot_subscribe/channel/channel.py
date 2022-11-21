"""
    订阅的频道基类
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Type, Union
from typing_extensions import Self
from ...os_bot_base import Session
from ...os_bot_base.depends import get_plugin_session


class ChannelSession(Session):

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        return self


@dataclass
class SubscribeInfoData:
    title: str = field(default="")
    des: str = field(default="")


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
    def channel_id(self) -> str:
        return f"{self.channel_type}_{self.channel_subtype}"

    def precheck(self, subscribe: str, option_str: str, options: Dict[str, Union[str, int, bool]], session: ChannelSession) -> bool:
        raise NotImplementedError("need implemented function!")

    def deal(self, subscribe: str, option_str: str, options: Dict[str, Union[str, int, bool]], session: ChannelSession) -> str:
        raise NotImplementedError("need implemented function!")

    def options_to_string(self, options: Dict[str, Union[str, int, bool]], session: ChannelSession) -> str:
        raise NotImplementedError("need implemented function!")

    def get_subscribe_info(self, subscribe: str, session: ChannelSession) -> SubscribeInfoData:
        raise NotImplementedError("need implemented function!")

    def subscribe_update(self) -> None:
        """订阅更新"""

    async def get_session(self) -> ChannelSession:
        return await get_plugin_session(self.channel_session_class)  # type: ignore

    