"""
    # 广播系统

    实现了广播的一系列功能，支持相对自动化的频道创建方式（通过Bot群列表、好友列表创建），或是通过插件开关创建。

    可以使用此功能对整个频道进行广播
"""

from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import broadcast
