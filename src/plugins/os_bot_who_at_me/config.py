from collections import deque
from time import time
from typing import Any, Deque, Dict
from typing_extensions import Self
from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from dataclasses import dataclass, field

from ..os_bot_base.session import Session, StoreSerializable
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_PLUGIN_ALIAS


class Config(BaseSettings):
    """
        工具插件
    """

    class Config:

        extra = "ignore"


@dataclass
class AtUnit(StoreSerializable):
    """
        AT数据单元

        - `origin_id` 谁at的
        - `target_id` at谁去了(0表示at全体)
        - `origin_msg` 原始消息
        - `deal_msg` 处理后的消息（用于发送
        - `view` 该AT是否已被查看（at全体永远未被查看
        - `create_time` 创建时间
    """
    origin_id: int = field(default=0)
    target_id: int = field(default=0)
    origin_msg: str = field(default="")
    deal_msg: str = field(default="")
    view: bool = field(default=False)
    create_time: int = field(default_factory=(lambda: int(time())), init=False)

    def is_expire(self):
        return time() - self.create_time > 43200


class WhoAtMeSession(Session):

    ob11_ats: Deque[AtUnit]
    """收集所有at"""

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.ob11_ats = deque(maxlen=100)

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        self.ob11_ats = deque(
            [
                AtUnit._load_from_dict(at)  # type: ignore
                for at in self.ob11_ats
            ],
            maxlen=100)
        return self


__plugin_meta__ = PluginMetadata(
    name="谁在AT我",
    description="OSBot 谁在AT我！",
    usage="""
        支持在群聊中使用`谁在艾特我`、`谁at我`、`艾特我什么事`等指令使用
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["谁在AT我", "谁在艾特我", "艾特我什么事", "at我什么事"],
        META_ADMIN_USAGE: "可以通过`群at列表`查看所有at~",  # 管理员可以获取的帮助
        META_SESSION_KEY: WhoAtMeSession
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
