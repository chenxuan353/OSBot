"""
    # B站功能支持

    提供动态发送、动态删除、直播间标题设置、指定分区开播、下播等功能
"""
import asyncio
import platform
from nonebot import require




# 如果系统为 Windows，则防止修改loop_policy
if "windows" in platform.system().lower():
    policy = asyncio.get_event_loop_policy()
    import bilibili_api
    asyncio.set_event_loop_policy(policy)


require('os_bot_base')

from .config import __plugin_meta__

from . import command
