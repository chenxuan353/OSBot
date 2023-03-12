"""
    # 通用订阅支持

    支持的订阅：bilibili、rss-email

    通过分发器将操作分发给各个适配器
"""
from nonebot import require

require('os_bot_base')

from . import commands
from . import model
from . import channel

from .config import __plugin_meta__
