"""
    # 字幕组专用插件

    用于提供字幕组相关功能
    
    例如：有没有x（批量AT）
"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import bbq
