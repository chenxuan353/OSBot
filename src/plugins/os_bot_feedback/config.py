from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY
from ..os_bot_base.depends import Session
from ..os_bot_base.util import AsyncTokenBucket

class Config(BaseSettings):
    # Your Config Here

    class Config:
        extra = "ignore"


class FeedbackSession(Session):
    _limit_bucket_day: AsyncTokenBucket
    _limit_bucket: AsyncTokenBucket
    """用于限制使用频率"""

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self._limit_bucket_day = AsyncTokenBucket(30,
                                         86400,
                                         initval=30)
        self._limit_bucket = AsyncTokenBucket(3,
                                         10 * 60,
                                         initval=3)
        self._keep = True



__plugin_meta__ = PluginMetadata(
    name="反馈",
    description="OSBot反馈插件",
    usage="使用`反馈 你想说的`",
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_ADMIN_USAGE: "可用：反馈列表、历史反馈、清空反馈、处理反馈 反馈ID、查看反馈 反馈ID",
        META_SESSION_KEY: FeedbackSession
    },
)

global_config = get_driver().config
config = Config.parse_obj(global_config)
