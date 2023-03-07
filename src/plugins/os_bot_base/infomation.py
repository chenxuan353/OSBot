"""
    用于展示一些账号数据，及支持相关操作

    例如群成员列表、好友列表等
"""
import math
import random
from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.adapters.onebot import v11
from nonebot.permission import SUPERUSER
from .depends import ArgMatchDepend, OBCacheBotDepend
from .cache.onebot import BotRecord
from .util import matcher_exception_try
from .argmatch import PageArgMatch


group_list = on_command(
    "群列表",
    block=True,
    permission=SUPERUSER,
)


@group_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            cache: BotRecord = OBCacheBotDepend(),
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    keys = [key for key in cache.groups]
    keys.sort()
    size = 10
    count = len(keys)
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["空的哦", "空的！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    msg = f"{arg.page}/{maxpage}"
    page_keys = keys[(arg.page - 1) * size:arg.page * size]
    for key in page_keys:
        group = cache.groups[key]
        msg += f"\n{group.get_nick()}({group.id}) - {group.member_count or '?'}/{group.max_member_count or '?'}"
    await matcher.finish(msg)


friend_list = on_command(
    "好友列表",
    block=True,
    permission=SUPERUSER,
)


@friend_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            cache: BotRecord = OBCacheBotDepend(),
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    keys = [key for key in cache.friends]
    keys.sort()
    size = 10
    count = len(keys)
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["空的哦", "空的！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    msg = f"{arg.page}/{maxpage}"
    nicks = []
    page_keys = keys[(arg.page - 1) * size:arg.page * size]
    for key in page_keys:
        unit = cache.friends[key]
        nicks.append(f"{unit.get_nick()}({unit.id})")
    await matcher.finish(f"{msg}\n{'、'.join(nicks)}")
