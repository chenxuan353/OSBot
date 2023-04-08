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


class GroupNoticeSession(Session):
    enter_notice: bool
    enter_notice_template: str
    leave_notice: bool
    leave_notice_template: str

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.enter_notice = True
        self.leave_notice = True
        self.enter_notice_template = "@新人欢迎加入群聊，记得查看群公告哦~"
        self.leave_notice_template = "[账号信息] 离开了我们……"


__plugin_meta__ = PluginMetadata(
    name="群提醒",
    description="OSBot 提供群聊提醒功能（进群、退群）",
    usage="""
        通过`启用/禁用群聊提醒`、`启用/禁用进群提醒`、`启用/禁用退群提醒`管理提醒的开闭状态
        通过`设置进群提醒 模版`、`设置退群提醒 模版`来设置提醒的模版
        通过`查看进群/退群提醒`可以检查当前设置的模版
        模版变量：
        @新人 在进群模版中有效，用于自动艾特新人
        [账号信息] 在进群或退群模版均有效，会显示对应账号信息，例 张三(12345)
        [昵称] 会显示昵称，例 张三
        [账号] 会显示账号，例 12345
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["进群提醒", "退群提醒"],
        META_ADMIN_USAGE: "什么都没有~",  # 管理员可以获取的帮助
        META_SESSION_KEY: GroupNoticeSession
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
