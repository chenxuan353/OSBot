"""
    # 多引擎翻译

    目前支持四个引擎的翻译，百度、彩云、谷歌、腾讯。

    支持的语言则为官网上各个引擎的支持范围。
"""
from nonebot import require

require('os_bot_base')

from . import trans

from .config import __plugin_meta__
