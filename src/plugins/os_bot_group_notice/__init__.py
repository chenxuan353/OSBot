"""
    群提醒
"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import group_notice
