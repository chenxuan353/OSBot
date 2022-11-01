from dataclasses import dataclass, field
from typing import Any, Dict
from typing_extensions import Self
from pydantic import BaseSettings, Field
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base import Session
from ..os_bot_base.session import StoreSerializable
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY


class Config(BaseSettings):
    """
        多引擎翻译
        
        - trans_default_engine 配置默认引擎(默认google)
        - trena_lang_optimize 翻译优化
    """
    trans_default_engine: str = Field(default="google")
    trena_lang_optimize: bool = Field(default=True)

    class Config:
        extra = "ignore"


@dataclass
class StreamUnit(StoreSerializable):
    user_id: int = field(default=None)  # type: ignore
    engine: str = field(default=None)  # type: ignore
    source: str = field(default=None)  # type: ignore
    target: str = field(default=None)  # type: ignore
    oprate_log: str = field(default=None)  # type: ignore


class TransSession(Session):
    stream_list: Dict[int, StreamUnit]

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.stream_list = {}

    def __init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.data.update(self_dict)
        for key in self.stream_list:
            del self.stream_list[key]
            stream = StreamUnit()
            stream.__init_from_dict(**self.stream_list[key])  # type: ignore
            self.stream_list[int(key)] = stream

        return self


__plugin_meta__ = PluginMetadata(
    name="OSBot多引擎翻译",
    description="支持多个翻译引擎翻译的插件",
    usage="暂无",
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_ADMIN_USAGE: "什么都没有~",  # 管理员可以获取的帮助
        META_SESSION_KEY: TransSession
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
