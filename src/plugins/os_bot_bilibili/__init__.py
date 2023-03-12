"""
    # B站支持（未完成）

    预计将支持动态的获取与发送，直播开关播等功能。
"""
# import nonebot
from nonebot import get_driver

from .config import Config

global_config = get_driver().config
config = Config(**global_config.dict())

# Export something for other plugin
# export = nonebot.export()
# export.foo = "bar"

# @export.xxx
# def some_function():
#     pass
