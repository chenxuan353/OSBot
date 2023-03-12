"""
    # 群提醒（进群、退群）

    支持群聊相关提醒，并可以设置模版。
"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import group_notice
