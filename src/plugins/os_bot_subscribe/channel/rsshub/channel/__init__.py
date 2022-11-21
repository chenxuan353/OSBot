from typing import Dict, List, Type, Union
from ...channel import Channel as BaseChannel, ChannelSession as BaseChannelSession, SubscribeInfoData


class RsshubChannelSession(BaseChannelSession):
    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)


class RsshubChannel(BaseChannel):
    def __init__(self) -> None:
        super().__init__()
    @property
    def aliases(self) -> List[str]:
        """别名列表"""
        return []

    @property
    def name(self) -> str:
        """中文标识名"""
        raise NotImplementedError("need implemented function!")

    @property
    def channel_session_class(self) -> Type[RsshubChannelSession]:
        return RsshubChannelSession

    @property
    def channel_type(self) -> str:
        raise NotImplementedError("need implemented function!")

    @property
    def channel_subtype(self) -> str:
        raise NotImplementedError("need implemented function!")

    @property
    def channel_id(self) -> str:
        return f"{self.channel_type}_{self.channel_subtype}"

    def precheck(self, subscribe: str, option_str: str, options: Dict[str, Union[str, int, bool]], session: RsshubChannelSession) -> bool:
        raise NotImplementedError("need implemented function!")

    def deal(self, subscribe: str, option_str: str, options: Dict[str, Union[str, int, bool]], session: RsshubChannelSession) -> str:
        raise NotImplementedError("need implemented function!")

    def options_to_string(self, options: Dict[str, Union[str, int, bool]], session: RsshubChannelSession) -> str:
        raise NotImplementedError("need implemented function!")

    def get_subscribe_info(self, subscribe: str, session: RsshubChannelSession) -> SubscribeInfoData:
        raise NotImplementedError("need implemented function!")

    def subscribe_update(self) -> None:
        """订阅更新"""
