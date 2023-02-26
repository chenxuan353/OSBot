from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base import Session
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_PLUGIN_ALIAS


class Config(BaseSettings):
    """
        工具插件
    """

    class Config:
        extra = "ignore"


class UtilSession(Session):

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)


__plugin_meta__ = PluginMetadata(
    name="broadcast",
    description="OSBot broadcast 广播，仅支持Onebot协议",
    usage="""
        收听就好
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["广播"],
        META_ADMIN_USAGE: """
            通过`广播 频道`开始广播~
            通过`频道列表 [频道] [页码]`、`加入频道`、`退出频道`、`创建/移除广播频道 频道名`、`添加/删除广播对象 [驱动] 组标识 组ID [昵称]`来管理频道
        """,  # 管理员可以获取的帮助
        META_SESSION_KEY: UtilSession,
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
