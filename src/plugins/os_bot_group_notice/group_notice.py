import random
from nonebot import on_command, on_notice, get_bots
from nonebot.matcher import Matcher
from nonebot.adapters import Bot
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.params import CommandArg, CommandStart
from .logger import logger
from .config import GroupNoticeSession

from ..os_bot_base.depends import SessionDepend, AdapterDepend, Adapter
from ..os_bot_base.util import matcher_exception_try, only_command

notice_enable = on_command("启用群聊提醒",
                           aliases={
                               "启用入群提醒", "启用进群提醒", "启用退群提醒", "打开入群提醒",
                               "打开进群提醒", "打开退群提醒", "打开群聊提醒"
                           },
                           rule=only_command(),
                           permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)


@notice_enable.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.GroupMessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: GroupNoticeSession = SessionDepend(),
            start: str = CommandStart()):
    async with session:
        if "入群" in start or "进群" in start:
            session.enter_notice = True
        elif "退群" in start:
            session.leave_notice = True
        else:
            session.enter_notice = True
            session.leave_notice = True

    if "入群" in start or "进群" in start:
        await matcher.finish("已启用进群提醒！")
    elif "退群" in start:
        await matcher.finish("已启用退群提醒！")
    else:
        await matcher.finish("已启用进群及退群提醒！")


notice_disable = on_command("禁用群聊提醒",
                            aliases={
                                "禁用入群提醒", "禁用进群提醒", "禁用退群提醒", "关闭入群提醒",
                                "关闭进群提醒", "关闭退群提醒", "关闭群聊提醒"
                            },
                            rule=only_command(),
                            permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)


@notice_disable.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.GroupMessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: GroupNoticeSession = SessionDepend(),
            start: str = CommandStart()):
    async with session:
        if "入群" in start or "进群" in start:
            session.enter_notice = False
        elif "退群" in start:
            session.leave_notice = False
        else:
            session.enter_notice = False
            session.leave_notice = False

    if "入群" in start or "进群" in start:
        await matcher.finish("已禁用进群提醒！")
    elif "退群" in start:
        await matcher.finish("已禁用退群提醒！")
    else:
        await matcher.finish("已禁用进群及退群提醒！")


notice_setting = on_command("设置进群提醒",
                            aliases={"设置入群提醒", "设置退群提醒"},
                            permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)


@notice_setting.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.GroupMessageEvent,
            session: GroupNoticeSession = SessionDepend(),
            start: str = CommandStart(),
            msg: v11.Message = CommandArg()):
    msg_str = str(msg).strip()
    if len(msg_str) < 5 or len(msg_str) > 150:
        await matcher.finish("进群或退群提醒的字数限制为5-150字！")
    async with session:
        if "入群" in start or "进群" in start:
            session.enter_notice_template = msg_str
        elif "退群" in start:
            session.leave_notice_template = msg_str

    if "入群" in start or "进群" in start:
        await matcher.finish("成功设置进群提醒！")
    elif "退群" in start:
        await matcher.finish("成功设置退群提醒！")


notice_setting_view = on_command("查看进群提醒",
                                 aliases={"查看入群提醒", "查看退群提醒"},
                                 permission=SUPERUSER | GROUP_ADMIN
                                 | GROUP_OWNER)


@notice_setting_view.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.GroupMessageEvent,
            session: GroupNoticeSession = SessionDepend(),
            start: str = CommandStart()):
    if "入群" in start or "进群" in start:
        await matcher.finish(f"进群提醒：\n{session.enter_notice_template}")
    elif "退群" in start:
        await matcher.finish(f"退群提醒：\n{session.leave_notice_template}")


notice_deal = on_notice(priority=5, block=False)


@notice_deal.handle()
async def _(matcher: Matcher,
            event: v11.GroupIncreaseNoticeEvent,
            session: GroupNoticeSession = SessionDepend()):
    if not session.enter_notice:
        return


@notice_deal.handle()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupIncreaseNoticeEvent,
            session: GroupNoticeSession = SessionDepend()):
    if not session.enter_notice:
        return
    card = None
    try:
        card = await bot.get_group_member_info(group_id=event.group_id,
                                               user_id=event.user_id)
    except Exception as e:
        logger.warning("在请求入群成员名片时异常 {}", e)

    if f"{event.user_id}" in get_bots():
        finish_msgs = ["你好啊~", "你好啊，我的替身！", "欢迎！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    nick = f"{event.user_id}"

    if card and "nickname" in card:
        nick = card["nickname"]

    template = session.enter_notice_template

    template_split = template.split("@新人")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.MessageSegment.at(
            event.user_id) + v11.Message(template_part)

    template_split = str(result_msg).split("[账号信息]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.Message(f"{nick}({event.user_id})") + v11.Message(
            template_part)

    template_split = str(result_msg).split("[账号]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.Message(f"{event.user_id}") + v11.Message(
            template_part)

    template_split = str(result_msg).split("[昵称]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.Message(f"{nick}") + v11.Message(template_part)

    await matcher.finish(result_msg)


@notice_deal.handle()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupDecreaseNoticeEvent,
            session: GroupNoticeSession = SessionDepend()):
    if not session.leave_notice:
        return
    card = None
    try:
        card = await bot.get_group_member_info(group_id=event.group_id,
                                               user_id=event.user_id)
    except Exception as e:
        logger.warning("在请求入群成员名片时异常 {}", e)

    if f"{event.user_id}" in get_bots():
        finish_msgs = ["你好啊~", "你好啊，我的替身！", "欢迎！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    nick = f"{event.user_id}"

    if card and "nickname" in card:
        nick = card["nickname"]

    template = session.leave_notice_template

    template_split = str(template).split("[账号信息]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.Message(f"{nick}({event.user_id})") + v11.Message(
            template_part)

    template_split = str(result_msg).split("[账号]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.Message(f"{event.user_id}") + v11.Message(
            template_part)

    template_split = str(result_msg).split("[昵称]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.Message(f"{nick}") + v11.Message(template_part)

    await matcher.finish(result_msg)
