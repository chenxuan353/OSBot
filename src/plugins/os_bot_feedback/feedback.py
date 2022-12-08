import asyncio
from functools import partial
import math
import random
from nonebot import on_command
from nonebot.adapters.onebot import v11
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.params import CommandArg
from .model import Feedback
from .config import FeedbackSession

from ..os_bot_base.util import matcher_exception_try, message_to_str
from ..os_bot_base.notice import UrgentNotice
from ..os_bot_base.adapter import AdapterFactory
from ..os_bot_base.argmatch import PageArgMatch, IntArgMatch
from ..os_bot_base.depends import ArgMatchDepend, SessionDepend

on_command = partial(on_command, block=True)


def feedback_format(feedback: Feedback) -> v11.Message:
    return f"{feedback.source}\n" + v11.Message(feedback.msg)





fb = on_command("反馈", aliases={"建议", "BUG", "bug"})


@fb.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            message: v11.Message = CommandArg(),
            session: FeedbackSession = SessionDepend(FeedbackSession)):
    # 群聊
    if not await session._limit_bucket.consume(1):
        finish_msgs = ["禁止滥用命令", "反馈太快了哦", "休息一会吧！"]
        await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])
    if not await session._limit_bucket_day.consume(1):
        finish_msgs = ["超过每日限额了哦", "反馈太多勒！"]
        await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])
    adapter = AdapterFactory.get_adapter(bot)
    group_nick = await adapter.get_group_nick(event.group_id)
    user_nick = await adapter.get_unit_nick_from_event(event.user_id, bot,
                                                       event)
    mark = await adapter.mark(bot, event)
    feedback = await Feedback.create(
        **{
            "source_mark": mark,
            "source":
            f"{group_nick}({event.group_id})-{user_nick}({event.user_id})",
            "msg": str(message)
        })
    fb_msg = feedback_format(feedback)
    # asyncio.gather(UrgentNotice.send(f"新的反馈消息：\n{fb_msg}"))
    finish_msgs = ["收到~", "已转达！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


@fb.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            message: v11.Message = CommandArg(),
            session: FeedbackSession = SessionDepend(FeedbackSession)):
    # 私聊
    if not await session._limit_bucket.consume(1):
        finish_msgs = ["禁止滥用命令", "反馈太快了哦", "休息一会吧！"]
        await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])
    if not await session._limit_bucket_day.consume(1):
        finish_msgs = ["超过每日限额了哦", "反馈太多勒！"]
        await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])

    adapter = AdapterFactory.get_adapter(bot)
    user_nick = await adapter.get_unit_nick_from_event(event.user_id, bot,
                                                       event)
    mark = await adapter.mark(bot, event)
    feedback = await Feedback.create(
        **{
            "source_mark": mark,
            "source": f"{user_nick}({event.user_id})",
            "msg": str(message)
        })
    fb_msg = feedback_format(feedback)
    # asyncio.gather(UrgentNotice.send(f"新的反馈消息：\n{fb_msg}"))
    finish_msgs = ["收到~", "已转达！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


fb_list = on_command("反馈列表", permission=SUPERUSER)


@fb_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    size = 5
    count = await Feedback.filter(deal=False).count()
    maxpage = math.ceil(count / size)

    if count == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    feedbacks = await Feedback.filter(deal=False).offset(
        (arg.page - 1) * size).limit(size).order_by("-id")
    msg = f"{arg.page}/{maxpage}"
    for feedback in feedbacks:
        obmsg = message_to_str(v11.Message(feedback.msg))
        msg += f"\n{feedback.id}-{feedback.source}:{obmsg[:10] + (obmsg[10:] and '...')}"
    await matcher.finish(msg)


fb_history_list = on_command("历史反馈列表", aliases={"历史反馈"}, permission=SUPERUSER)


@fb_history_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    size = 5
    count = await Feedback.filter(deal=True).count()
    maxpage = math.ceil(count / size)

    if count == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    feedbacks = await Feedback.filter(deal=True).offset(
        (arg.page - 1) * size).limit(size).order_by("-id")
    msg = f"{arg.page}/{maxpage}"
    for feedback in feedbacks:
        obmsg = message_to_str(v11.Message(feedback.msg))
        msg += f"\n{feedback.id}-{feedback.source}:{obmsg[:10] + (obmsg[10:] and '...')}"
    await matcher.finish(msg)


fb_clear = on_command("清空反馈", aliases={"清空反馈列表"}, permission=SUPERUSER)


@fb_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    await Feedback.filter(deal=False).update(deal=True)
    finish_msgs = ["成功啦", "OK！", "clear！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


fb_get = on_command("获取反馈", aliases={"查看反馈"}, permission=SUPERUSER)


@fb_get.handle()
@matcher_exception_try()
async def _(matcher: Matcher, arg: IntArgMatch = ArgMatchDepend(IntArgMatch)):
    feedback = await Feedback.get_or_none(**{"id": arg.num})
    if not feedback:
        finish_msgs = ["不存在的领域", "空空如也", "什么都没有找到"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    await matcher.finish(feedback_format(feedback))


fb_deal = on_command("处理反馈", aliases={"反馈处理", "完成反馈"}, permission=SUPERUSER)


@fb_deal.handle()
@matcher_exception_try()
async def _(matcher: Matcher, arg: IntArgMatch = ArgMatchDepend(IntArgMatch)):
    feedback = await Feedback.get_or_none(**{"id": arg.num})
    if not feedback:
        finish_msgs = ["不存在的领域", "空空如也", "什么都没有找到"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if feedback.deal:
        finish_msgs = ["重复处理……？", "已经处理过了哦"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    feedback.deal = True
    await feedback.save()
    finish_msgs = ["已确认执行", "万事大吉"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])
