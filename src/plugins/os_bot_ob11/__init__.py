"""
    # OB11协议功能集

    
"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import ob11
from . import withdraw
