"""
    # 详细数据统计插件（未完成）

    预计以最小侵入
"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import data_statistics
