"""
    # 反馈

    基于核心插件数据库服务及提醒服务的反馈。

    支持接收反馈的消息同时可以进行回复或是忽略处理。
"""
from nonebot import require

require('os_bot_base')

from . import config
from . import feedback

from .config import __plugin_meta__
