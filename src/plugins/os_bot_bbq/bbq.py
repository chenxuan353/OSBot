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
from ..os_bot_base.permission import PermManage, perm_check_permission
from ..os_bot_base.depends import SessionDepend

from .config import BBQSession

PermManage.register("召唤术",
                    "批量at的权限",
                    False,
                    for_group_member=True,
                    only_super_oprate=False)


def list_split(listTemp, n):
    """
        列表分割生成器
    """
    for i in range(0, len(listTemp), n):
        yield listTemp[i:i + n]


at_someone = on_regex(r"^有没有(?P<tag>[^\s!！]{1,5})[!！]{1}$",
                      permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                      | perm_check_permission("召唤术"))


@at_someone.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            regex_group: Dict[str, Any] = RegexDict(),
            session: BBQSession = SessionDepend()):
    if not await session._limit_bucket.consume(1):
        finish_msgs = ["禁止滥用命令哦", "召唤太快了", "休息一会吧！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if not await session._limit_bucket_day.consume(1):
        finish_msgs = ["超过每日限额了哦", "low power"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if 'tag' not in regex_group:
        await matcher.finish("功能异常")
    member_list = await bot.get_group_member_list(group_id=event.group_id)
    if not member_list:
        await matcher.finish("获取群成员列表失败，请联系管理员")
    at_list = []
    for member in member_list:
        if "card" in member:
            if f'{member["user_id"]}' == f"{event.user_id}":
                # 跳过自己
                continue
            card: str = member["card"] or member["nickname"]
            if "请假" in card:
                continue
            if "[" in card:
                card = card[card.index("[") + 1:]
            if "【" in card:
                card = card[card.index("【") + 1:]
            if "{" in card:
                card = card[card.index("{") + 1:]
            if "]" in card:
                card = card[:card.index("]")]
            if "】" in card:
                card = card[:card.index("】")]
            if "}" in card:
                card = card[:card.index("}")]
            if regex_group['tag'] in card:
                at_list.append(member["user_id"])

    if not at_list:
        finish_msgs = ('没有哦', '没有能够召唤的对象x')
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    if len(at_list) > 60:
        random.shuffle(at_list)
        at_list[:60]
        send_msgs = ('召唤过载！将产生不可知变化', '法术已超载截断！', '不稳定召唤')
        await matcher.send(send_msgs[random.randint(0, len(send_msgs) - 1)])
        await asyncio.sleep(random.randint(1000, 5000) / 1000)

    for in_list in list_split(at_list, 20):
        msg = v11.Message()
        for item in in_list:
            msg += v11.MessageSegment.at(item)
        await matcher.send(msg)
        await asyncio.sleep(random.randint(1000, 5000) / 1000)
