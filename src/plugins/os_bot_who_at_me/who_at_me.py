import math
import random
from nonebot import on_keyword, on_command, on_message
from nonebot.matcher import Matcher
from nonebot.params import EventMessage
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, GROUP_MEMBER

from .config import AtUnit, WhoAtMeSession
from .logger import logger

from ..os_bot_base.depends import SessionDepend, ArgMatchDepend, AdapterDepend, Adapter
from ..os_bot_base.util import matcher_exception_try
from ..os_bot_base.argmatch import PageArgMatch

who_at_me = on_keyword(keywords={"谁at我", "谁AT我", "谁艾特我", "有人艾特我吗"},
                       priority=5,
                       block=False)


@who_at_me.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            message: v11.Message = EventMessage(),
            adapter: Adapter = AdapterDepend(),
            session: WhoAtMeSession = SessionDepend()):
    if len(str(message)) > 10:
        return

    at_list = [
        at for at in session.ob11_ats if at.target_id in [0, event.user_id]
    ]

    if not at_list:
        return

    if at_list[-1].is_expire():
        return

    at_unit = at_list[-1]

    if at_unit.view:
        return

    nick = await adapter.get_unit_nick(at_unit.origin_id,
                                       group_id=event.group_id)

    finish_msgs = (f"@{nick} 艾特了你", f"或许是 @{nick}")
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


why_at_me = on_keyword(keywords={"at我干啥", "艾特我干啥", "艾特我什么事"},
                       priority=5,
                       block=False)


@why_at_me.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            message: v11.Message = EventMessage(),
            adapter: Adapter = AdapterDepend(),
            session: WhoAtMeSession = SessionDepend()):
    if len(str(message)) > 10:
        return

    at_list = [
        at for at in session.ob11_ats if at.target_id in [0, event.user_id]
    ]

    if not at_list:
        return

    if at_list[-1].is_expire():
        return

    at_unit = at_list[-1]

    if at_unit.view:
        return

    async with session:
        at_unit.view = True

    nick = await adapter.get_unit_nick(at_unit.origin_id,
                                       group_id=event.group_id)

    finish_msgs = (f"来自 {nick}：\n", f"最近一次来自 @{nick}：\n")
    finish_msg = finish_msgs[random.randint(0, len(finish_msgs) - 1)]
    finish_msg = v11.MessageSegment.text(finish_msg)
    finish_msg += v11.Message(at_unit.deal_msg)
    await matcher.finish(finish_msg)


at_me_list = on_command("at列表",
                        aliases={"艾特列表"},
                        block=True,
                        permission=GROUP_ADMIN | GROUP_OWNER | GROUP_MEMBER)


@at_me_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.GroupMessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            session: WhoAtMeSession = SessionDepend(),
            adapter: Adapter = AdapterDepend()):
    size = 5
    at_list = [
        at for at in session.ob11_ats if at.target_id in [0, event.user_id]
    ]
    count = len(at_list)
    maxpage = math.ceil(count / size)

    if count == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    at_list_part = at_list[(arg.page - 1) * size:arg.page * size]
    msg = v11.Message() + v11.MessageSegment.text(f"{arg.page}/{maxpage}")
    for at_unit in at_list_part:
        msg += v11.MessageSegment.text(
            f"\n{await adapter.get_unit_nick(at_unit.origin_id, group_id=event.group_id)}({at_unit.origin_id}) > "
        )
        msg += v11.Message(at_unit.deal_msg)
    await matcher.finish(msg)


at_me_group_list = on_command("群at列表",
                              aliases={"群艾特列表", "群聊艾特列表", "群聊at列表"},
                              block=True,
                              permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)


@at_me_group_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.GroupMessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            session: WhoAtMeSession = SessionDepend(),
            adapter: Adapter = AdapterDepend()):
    size = 5
    at_list = list(session.ob11_ats)
    count = len(at_list)
    maxpage = math.ceil(count / size)

    if count == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    at_list_part = at_list[(arg.page - 1) * size:arg.page * size]
    msg = v11.Message() + v11.MessageSegment.text(f"{arg.page}/{maxpage}")
    for at_unit in at_list_part:
        msg += v11.MessageSegment.text(
            f"\n{await adapter.get_unit_nick(at_unit.origin_id, group_id=event.group_id)}({at_unit.origin_id})"
        )
        if at_unit.target_id == 0:
            msg += v11.MessageSegment.text(f"艾特了全体成员 > ")
        else:
            msg += v11.MessageSegment.text(
                f"艾特了{await adapter.get_unit_nick(at_unit.target_id, group_id=event.group_id)}({at_unit.target_id}) > "
            )
        msg += v11.Message(at_unit.deal_msg)
    await matcher.finish(msg)


at_collect = on_message(priority=1, block=False)


@at_collect.handle()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            message: v11.Message = EventMessage(),
            session: WhoAtMeSession = SessionDepend(),
            adapter: Adapter = AdapterDepend()):
    msg_ats = message["at"]
    if not msg_ats:
        return

    deal_msg = v11.Message()
    for msgseg in message:
        if msgseg.is_text():
            deal_msg += v11.MessageSegment.text(
                msgseg.data.get("text"))  # type: ignore
        elif msgseg.type == "at":
            qq = msgseg.data.get("qq", "")
            if qq == 'all':
                deal_msg += v11.MessageSegment.text("@全体成员 ")
            else:
                deal_msg += v11.MessageSegment.text(
                    f"@{await adapter.get_unit_nick(msgseg.data.get('qq', ''), group_id=event.group_id)} "
                )
        elif msgseg.type == "image":
            url = msgseg.data.get("url", "")
            deal_msg += v11.MessageSegment.image(url)
        elif msgseg.type == "face":
            deal_msg += msgseg

    if len(deal_msg.extract_plain_text()) > 100:
        return

    async with session:
        for at_seg in msg_ats:
            if "qq" not in at_seg.data and at_seg.data.get("qq", None):
                continue
            qq = at_seg.data.get("qq", "")
            if f"{qq}" == f"{event.user_id}":
                # 排除自我感动
                continue
            if qq == 'all':
                qq = 0
            qq = int(qq)
            session.ob11_ats.append(
                AtUnit(origin_id=event.user_id,
                       target_id=qq,
                       origin_msg=str(message),
                       deal_msg=str(deal_msg)))
