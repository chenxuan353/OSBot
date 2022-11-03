from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE


class Config(BaseSettings):
    # Your Config Here

    class Config:
        extra = "ignore"


__plugin_meta__ = PluginMetadata(
    name="反馈",
    description="OSBot反馈插件",
    usage="使用`反馈 你想说的`",
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_ADMIN_USAGE: "可用：反馈列表、历史反馈、清空反馈、处理反馈 反馈ID、查看反馈 反馈ID"
    },
)

global_config = get_driver().config
config = Config.parse_obj(global_config)
