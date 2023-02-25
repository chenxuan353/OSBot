"""
    # 广播系统

    将支持广播任意内容到对应频道中
"""

from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import broadcast
