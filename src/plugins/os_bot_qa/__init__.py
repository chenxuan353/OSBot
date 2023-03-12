"""
    # 问答库

    提供简单的关键词问题与回复

    支持多条回复、随机回复、概率回复
"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import qa
