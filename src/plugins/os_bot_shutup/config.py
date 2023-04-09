from typing import List, Union
from pydantic import BaseSettings, Field
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base import Session
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_PLUGIN_ALIAS


class Config(BaseSettings):
    """
        工具插件
    """
    superusers: List[Union[int, str]] = Field(default=[])

    class Config:
        extra = "ignore"


class UtilSession(Session):

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)


__plugin_meta__ = PluginMetadata(
    name="安静",
    description="OSBot 闭嘴！",
    usage="""
        支持通过指令来让Bot安静一会
        `禁言`、`安静`、`闭嘴`、`安静一会`等用于使bot安静，这些指令均支持可选参数`[时间] [等级]`。
        `解除禁言`、`醒一醒`等指令用于解除安静状态
        时间支持：十分钟、一小时等描述方式
        等级支持：很安静，完全安静/特别安静
        例如 安静十分钟 特别安静的那种 或是 安静一会
        特殊指令：`被动模式` 启用被动模式后将不响应群成员的指令，`退出被动模式` 可用于恢复对群成员指令的响应
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["shut up", "闭嘴", "休眠", "睡一会", "禁言", "安静一会"],
        META_ADMIN_USAGE:
        "可以通过`远程禁言 群/私聊 ID`或者`远程解除禁言 群/私聊 ID`来控制指定对象的安静状态",  # 管理员可以获取的帮助
        META_SESSION_KEY: UtilSession
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
