"""
    闭嘴！

    让机器人安静指定时间的插件（

    将直接屏蔽除核心插件及本插件以外的插件处理事件

    在遭遇被禁言事件时自动触发
"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import shut_up
