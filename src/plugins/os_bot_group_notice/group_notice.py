import base64
import random
from time import time
import aiohttp
from nonebot import on_command, on_notice, get_bots
from nonebot.matcher import Matcher
from nonebot.adapters import Bot
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.params import CommandArg, RawCommand
from .logger import logger
from .config import GroupNoticeSession

from ..os_bot_base.depends import SessionDepend, AdapterDepend, Adapter
from ..os_bot_base.util import matcher_exception_try, only_command
from ..os_bot_base.exception import MatcherErrorFinsh

notice_enable = on_command("启用群聊提醒",
                           aliases={
                               "启用入群提醒", "启用进群提醒", "启用退群提醒", "打开入群提醒",
                               "打开进群提醒", "打开退群提醒", "打开群聊提醒"
                           },
                           block=True,
                           rule=only_command(),
                           permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)


@notice_enable.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.GroupMessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: GroupNoticeSession = SessionDepend(),
            start: str = RawCommand()):
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
                            block=True,
                            rule=only_command(),
                            permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)


@notice_disable.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.GroupMessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: GroupNoticeSession = SessionDepend(),
            start: str = RawCommand()):
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


async def download_to_base64(url: str,
                             maxsize_kb=1024,
                             ignore_exception: bool = False) -> str:
    maxsize = maxsize_kb * 1024
    timeout = 15
    try:
        req = aiohttp.request("get",
                              url,
                              timeout=aiohttp.ClientTimeout(total=10))
        async with req as resp:
            code = resp.status
            if code != 200:
                raise MatcherErrorFinsh("获取图片失败，状态看起来不是很好的样子。")
            if resp.content_length and resp.content_length > maxsize:
                raise MatcherErrorFinsh(f'图片太大！要小于{maxsize_kb}kb哦')
            size = 0
            start = time()
            filedata = bytes()
            async for chunk in resp.content.iter_chunked(1024):
                if time() - start > timeout:
                    raise MatcherErrorFinsh('下载超时了哦')
                filedata += chunk
                size += len(chunk)
                if size > maxsize:
                    raise MatcherErrorFinsh(f'图片太大！要小于{maxsize_kb}kb哦')
            urlbase64 = str(base64.b64encode(filedata), "utf-8")
    except MatcherErrorFinsh as e:
        if ignore_exception:
            logger.warning("图片下载失败：{} | {}", url, e)
            return ""
        raise e
    except Exception as e:
        logger.warning("图片下载失败：{} | {} | {}", url, e.__class__.__name__, e)
        return ""
    return urlbase64


notice_setting = on_command("设置进群提醒",
                            aliases={"设置入群提醒", "设置退群提醒"},
                            block=True,
                            permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)


@notice_setting.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.GroupMessageEvent,
            session: GroupNoticeSession = SessionDepend(),
            start: str = RawCommand(),
            msg: v11.Message = CommandArg()):

    msg_recombination = v11.Message()
    for msgseg in msg:
        if msgseg.is_text():
            msg_recombination += v11.MessageSegment.text(
                msgseg.data.get("text", ""))
        elif msgseg.type == "image":
            url = msgseg.data.get("url", "")
            b64 = await download_to_base64(url)
            msg_recombination += v11.MessageSegment.image(f"base64://{b64}")
        elif msgseg.type == "face":
            msg_recombination += msgseg
        else:
            await matcher.finish("消息中包含无法设为问答的元素！")

    if len(msg_recombination["image"]) > 9:
        await matcher.finish("进群或退群提醒至多允许9张图")

    msg_str = str(msg_recombination).strip()

    if len(msg_recombination.extract_plain_text()) < 5 or len(
            msg_recombination.extract_plain_text()) > 150:
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
                                 block=True,
                                 permission=SUPERUSER | GROUP_ADMIN
                                 | GROUP_OWNER)


@notice_setting_view.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.GroupMessageEvent,
            session: GroupNoticeSession = SessionDepend(),
            start: str = RawCommand()):
    if "入群" in start or "进群" in start:
        await matcher.finish(
            v11.MessageSegment.text("进群提醒：\n") +
            v11.Message(session.enter_notice_template))
    elif "退群" in start:
        await matcher.finish(
            v11.MessageSegment.text("退群提醒：\n") +
            v11.Message(session.leave_notice_template))


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
        result_msg += v11.MessageSegment.text(
            f"{nick}({event.user_id})") + v11.Message(template_part)

    template_split = str(result_msg).split("[账号]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.MessageSegment.text(
            f"{event.user_id}") + v11.Message(template_part)

    template_split = str(result_msg).split("[昵称]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.MessageSegment.text(f"{nick}") + v11.Message(
            template_part)

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

    template_split = template.split("[账号信息]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.MessageSegment.text(
            f"{nick}({event.user_id})") + v11.Message(template_part)

    template_split = str(result_msg).split("[账号]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.MessageSegment.text(
            f"{event.user_id}") + v11.Message(template_part)

    template_split = str(result_msg).split("[昵称]")
    result_msg = v11.Message(template_split.pop(0))
    for template_part in template_split:
        result_msg += v11.MessageSegment.text(f"{nick}") + v11.Message(
            template_part)

    await matcher.finish(result_msg)
