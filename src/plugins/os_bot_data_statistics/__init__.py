"""
    此插件将以最小侵入性，对各类数据进行统计


"""
from nonebot import require

require('os_bot_base')

from .config import __plugin_meta__

from . import data_statistics
