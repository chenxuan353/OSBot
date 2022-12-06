from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY


class Config(BaseSettings):
    # Your Config Here

    class Config:
        extra = "ignore"

    

__plugin_meta__ = PluginMetadata(
    name="订阅管理",
    description="OSBot 订阅管理 支持订阅RSSHub、B站、等",
    usage="""
        本功能仅允许管理员进行操作
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_ADMIN_USAGE: """
            `订阅 [频道] 订阅标识`、`取消订阅 [频道] 订阅标识`、`订阅配置 [频道] 订阅标识 选项`、`订阅列表`
            `全局订阅列表`
            频道[选项] B站动态[投稿、仅日语、转发]、B站直播[标题、简介]、邮件
        """,  # 管理员可以获取的帮助
    },
)


global_config = get_driver().config
config = Config(**global_config.dict())
