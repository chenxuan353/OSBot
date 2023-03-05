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
        指令：有没有x！
        无需前缀，管理员可用，其它群员可以由管理员通过`授权 召唤术 @群友`来特殊授权。
        需要禁用权限可以使用`禁用权限 召唤术 @群友` 
        注意，该AT仅对修改了群名片的群员生效。
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
