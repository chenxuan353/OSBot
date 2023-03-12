"""
    # 推特

    支持订阅推特、查看推文、烤推等功能

    此插件部分功能依赖`翻译`插件，请保证翻译插件正常运行。
"""
from nonebot import require

require('os_bot_base')

from . import model
from . import polling
from . import commands

from .config import __plugin_meta__
