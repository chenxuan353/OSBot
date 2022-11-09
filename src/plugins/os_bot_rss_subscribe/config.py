from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY


class Config(BaseSettings):
    # Your Config Here

    class Config:
        extra = "ignore"

    

__plugin_meta__ = PluginMetadata(
    name="echo",
    description="OSBot Echo 说些什么",
    usage="""
        爪巴、ping、在吗 等命令用于测试
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_ADMIN_USAGE: "什么都没有~",  # 管理员可以获取的帮助
    },
)
