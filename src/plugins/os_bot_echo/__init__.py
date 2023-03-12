"""
    # echo（说些什么）

    基础插件示例，同时提供询问Bot是否还在的功能。
"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import echo
