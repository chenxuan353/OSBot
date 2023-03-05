import asyncio
import random
from time import time
from typing import Any, Dict
from nonebot import on_regex
from nonebot.matcher import Matcher
from nonebot.adapters.onebot import v11
from nonebot.params import RegexDict
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER

from ..os_bot_base.util import matcher_exception_try


def list_split(listTemp, n):
    """
        列表分割生成器
    """
    for i in range(0, len(listTemp), n):
        yield listTemp[i:i + n]


at_someone = on_regex(r"^有没有(?P<tag>:[^\s!！]{1,5})[!！]{1}$",
                      permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)


@at_someone.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            regex_group: Dict[str, Any] = RegexDict()):
    if 'tag' not in regex_group:
        await matcher.finish("功能异常")
    member_list = await bot.get_group_member_list(group_id=event.group_id)
    if not member_list:
        await matcher.finish("获取群成员列表时异常")
    at_list = []
    for member in member_list:
        if "card" in member and regex_group['tag'] in member["card"]:
            at_list.append(member["user_id"])
    if len(at_list) > 45:
        await matcher.finish("at列表过长！")

    for in_list in list_split(at_list, 15):
        msg = v11.Message()
        for item in in_list:
            msg += v11.MessageSegment.at(item)
        await matcher.send(msg)
        await asyncio.sleep(random.randint(1000, 5000) / 1000)
