from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base import Session
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_PLUGIN_ALIAS, META_DEFAULT_SWITCH


class Config(BaseSettings):
    """
        工具插件
    """

    class Config:
        extra = "ignore"


class BBQSession(Session):

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)


__plugin_meta__ = PluginMetadata(
    name="搬运组",
    description="OSBot 烤肉组专长",
    usage="""
        
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["来点x", "来点x!", "来点x！", "x呢!!!", "x呢！！！"],
        META_ADMIN_USAGE: "什么都没有~",  # 管理员可以获取的帮助
        META_SESSION_KEY: BBQSession,
        META_DEFAULT_SWITCH: False
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
