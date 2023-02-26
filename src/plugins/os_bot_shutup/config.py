from typing import List, Union
from pydantic import BaseSettings, Field
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base import Session
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY


class Config(BaseSettings):
    """
        工具插件
    """
    superusers: List[Union[int, str]] = Field(default=[])
    
    class Config:
        extra = "ignore"


class UtilSession(Session):

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)


__plugin_meta__ = PluginMetadata(
    name="shutup",
    description="OSBot shutup 闭嘴！",
    usage="""
        `安静一会~`等
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_ADMIN_USAGE: "什么都没有~",  # 管理员可以获取的帮助
        META_SESSION_KEY: UtilSession
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
