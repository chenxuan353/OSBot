from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE


class Config(BaseSettings):
    # Your Config Here

    class Config:
        extra = "ignore"


__plugin_meta__ = PluginMetadata(
    name="OSBot反馈",
    description="反馈插件",
    usage="使用`反馈 你想说的`",
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_ADMIN_USAGE: "什么都没有~"  # 管理员可以获取的帮助
    },
)

global_config = get_driver().config
config = Config.parse_obj(global_config)
