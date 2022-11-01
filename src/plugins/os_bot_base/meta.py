from nonebot.plugin import PluginMetadata
from .session import Session
from .consts import META_SESSION_KEY, META_AUTHOR_KEY, META_NO_MANAGE, META_ADMIN_USAGE
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="OSBot核心",
    description="OSBot插件组的核心插件",
    usage="暂无",
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_SESSION_KEY: Session,  # 只有声明后，才可以使用`Session`依赖注入
        META_NO_MANAGE: True,
        META_ADMIN_USAGE: "什么都没有~"  # 管理员可以获取的帮助
    },
)
