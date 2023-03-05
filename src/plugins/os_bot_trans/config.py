from dataclasses import dataclass, field
import os
from typing import Any, Dict
from typing_extensions import Self
from pydantic import BaseSettings, Field
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base import Session
from ..os_bot_base.session import StoreSerializable
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_PLUGIN_ALIAS


class Config(BaseSettings):
    """
        多引擎翻译
        
        - trans_default_engine 配置默认引擎(默认google)
        - trans_lang_optimize 翻译优化
        - 
    """
    trans_default_engine: str = Field(default="google")
    trans_lang_optimize: bool = Field(default=True)
    trans_emoji_filter_file: str = Field(default=os.path.join(".", "emoji-regex.txt"))

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
    default_trans: str

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.stream_list = {}
        self.default_trans = "zh-cn"

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        tmp_list: Dict[str, Any] = self.stream_list  # type: ignore
        self.stream_list = {}
        for key in tmp_list:
            stream = StreamUnit._load_from_dict(tmp_list[key])  # type: ignore
            self.stream_list[int(key)] = stream

        return self


__plugin_meta__ = PluginMetadata(
    name="翻译",
    description="OSBot多引擎翻译，支持多个翻译引擎翻译的插件",
    usage="""
        使用`翻译 引擎 源语言 目标语言 内容`来进行翻译，除了内容以外都是可选的~
        引擎支持谷歌、腾讯、百度、彩云，语言的话就看各个引擎本身是否支持了。
        通过`翻译引擎列表`查看当前支持的引擎！
        管理员可通过`流式翻译 目标 引擎 源语言 目标语言`来启用自动翻译，除了目标以外都可选(推荐使用默认配置)。
        可以通过`流式翻译@对象`来进行定向开关(完整指令`流式翻译 状态 对象 引擎 源语言 目标语言`)。
        管理员如果需要修改默认翻译语言可以使用`设置默认翻译语言 语言`的命令(默认为日语)
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["机翻", "翻译翻译", "多引擎翻译", "多引擎机翻", "机器翻译", "流式翻译", "跟随翻译"],
        META_ADMIN_USAGE: "什么都没有~",  # 管理员可以获取的帮助
        META_SESSION_KEY: TransSession
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
