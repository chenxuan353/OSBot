from asyncio import events
import base64
import math
import random
from time import strftime, time
from typing import Optional
import aiohttp
from nonebot import on_command, on_message
from nonebot.matcher import Matcher
from nonebot.adapters import Bot
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, PRIVATE_FRIEND
from nonebot.params import CommandArg, EventMessage, RawCommand, T_State
from .logger import logger
from .config import QAMode, QASession, QAUnit

from ..os_bot_base.depends import SessionDepend, ArgMatchDepend, AdapterDepend, Adapter, SessionPluginDepend
from ..os_bot_base.argmatch import PageArgMatch
from ..os_bot_base.util import matcher_exception_try, only_command
from ..os_bot_base.permission import PermManage, perm_check_permission
from ..os_bot_base.exception import MatcherErrorFinsh

PermManage.register("问答库",
                    "问答库管理权限",
                    False,
                    for_group_member=True,
                    only_super_oprate=False)


def qa_message_precheck(msg: v11.Message) -> bool:
    for msgseg in msg:
        if msgseg.type not in ("face", "image", "text"):
            return False
    return True


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


qa_add = on_command("添加问答",
                    aliases={"我教你", "创建问答", "教你", "创建全局问答", "添加全局问答"},
                    block=True,
                    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                    | PRIVATE_FRIEND
                    | perm_check_permission("问答库"))


@qa_add.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session

    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")

    msg_recombination = v11.Message()
    for msgseg in msg:
        if msgseg.is_text():
            msg_recombination += v11.MessageSegment.text(
                msgseg.data.get("text", ""))
        elif msgseg.type == "at":
            msg_recombination += msgseg
        elif msgseg.type == "image":
            url = msgseg.data.get("url", "")
            b64 = await download_to_base64(url)
            msg_recombination += v11.MessageSegment.image(f"base64://{b64}")
        elif msgseg.type == "face":
            msg_recombination += msgseg
        else:
            await matcher.finish("消息中包含无法设为问答的元素！")

    msg_str = str(msg_recombination).strip()
    if not msg_str:
        await matcher.finish("问答不能为空哦~")
    if ">" not in msg_str:
        await matcher.finish("QA格式：问题>回复1>...>回复n，至少包含一个回复")
    msg_splits = msg_str.split(">")
    queston = msg_splits.pop(0)
    answers = msg_splits
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    queston_msg = v11.Message(queston)
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    if len(queston_msg.extract_plain_text()) > 50:
        await matcher.finish("问题的字数上限为50")
    if len(queston_msg["image"]) > 0:
        await matcher.finish("问题无法携带图片！")
    for answer in answers:
        answer_msg = v11.Message(answer)
        if len(answer_msg.extract_plain_text()) > 100:
            await matcher.finish("单条回答字数上限为：100字")
        if len(answer_msg['image']) > 9:
            await matcher.finish("单条回答至多9张图哦")
    if queston not in session.QAList:
        async with session:
            session.QAList[queston] = QAUnit(
                queston=queston,
                answers=answers,
                mode=QAMode.LIKE,
                hit_probability=100,
                create_by=int(await adapter.get_unit_id_from_event(bot,
                                                                   event)),
                update_by=int(await adapter.get_unit_id_from_event(bot,
                                                                   event)),
                oprate_log=
                f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
            )
        await matcher.finish(f"学会了它以及它的{len(answers)}个回复(模糊)")
    unit = session.QAList[queston]
    if len(unit.answers) + len(answers) > 50:
        await matcher.finish(f"回答总数合计无法超过50哦！")

    async with session:
        unit.oprate_log += f"\n{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
        for answer in answers:
            unit.answers.append(answer)
        unit.update_by = int(await adapter.get_unit_id_from_event(bot, event))
    await matcher.finish(
        f"可用知识增加了({len(unit.answers) - len(answers)}->{len(unit.answers)})")


qa_del = on_command("删除问答",
                    aliases={
                        "忘记问题", "移除问答", "忘掉问题", "忘掉问答", "忘记全局问题", "忘掉全局问题"
                        "移除全局问答", "删除全局问答", "删除问题", "全局删除问题", "忘了"
                    },
                    block=True,
                    priority=2,
                    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                    | PRIVATE_FRIEND
                    | perm_check_permission("问答库"))


@qa_del.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session

    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    queston = msg_str
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    if queston not in session.QAList:
        finish_msgs = ["问题不存在哦！", "唔，没找到这个问题哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    unit = session.QAList[queston]
    async with session:
        del session.QAList[queston]
    await matcher.finish(f"遗忘了它以及它的{len(unit.answers)}个回复")


qa_setting_mode = on_command(
    "重置问题匹配模式",
    block=True,
    aliases={
        "设置问题完全匹配", "设置问题关键词匹配", "设置问题模糊匹配", "设置问答完全匹配", "设置问答关键词匹配",
        "设置问答模糊匹配", "重置匹配模式", "重置问题匹配", "设置全局问题完全匹配", "设置全局问题关键词匹配",
        "设置全局问题模糊匹配", "设置全局问答完全匹配", "设置全局问答关键词匹配", "设置全局问答模糊匹配", "重置全局匹配模式",
        "重置全局问题匹配", "重置全局问题匹配模式"
    },
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER | PRIVATE_FRIEND
    | perm_check_permission("问答库"))


@qa_setting_mode.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    queston = msg_str
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    if queston not in session.QAList:
        finish_msgs = ["问题不存在哦！", "唔，没找到这个问题哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    unit = session.QAList[queston]
    async with session:
        if "完全" in start:
            unit.mode = QAMode.FULL
        elif "关键词" in start:
            unit.mode = QAMode.KEY
        else:
            unit.mode = QAMode.LIKE
        unit.oprate_log += f"\n{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
        unit.update_by = int(await adapter.get_unit_id_from_event(bot, event))
    finish_msgs = ["设置成功", "完成啦", "好勒！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


qa_setting_hit_probability = on_command("设置问题回复率",
                                        block=True,
                                        aliases={
                                            "设置问答回复率",
                                            "重置问答回复率",
                                            "重置问题回复率",
                                            "设置问题回复概率",
                                            "设置问答回复概率",
                                            "设置全局问答回复率",
                                            "重置全局问答回复率",
                                            "重置全局问题回复率",
                                            "设置全局问题回复概率",
                                            "设置全局问答回复概率",
                                            "设置全局问题回复率",
                                            "设置回复概率",
                                            "设置全局回复概率",
                                            "设置问题回复概率",
                                            "设置全局问题回复概率",
                                        },
                                        permission=SUPERUSER | GROUP_ADMIN
                                        | GROUP_OWNER | PRIVATE_FRIEND
                                        | perm_check_permission("问答库"))


@qa_setting_hit_probability.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    if "=" in msg_str:
        msg_str_split = msg_str.split("=", maxsplit=1)
        try:
            hit_probability = int(msg_str_split[1])
        except Exception:
            await matcher.finish("设置问题回复概率时`=`后边需要是1-100的整数！")
        if hit_probability <= 0 or hit_probability > 100:
            await matcher.finish("设置问题回复概率时`=`后边需要是1-100的整数！")
        queston = msg_str_split[0]
    else:
        hit_probability = 100
        queston = msg_str
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    if queston not in session.QAList:
        finish_msgs = ["问题不存在哦！", "唔，没找到这个问题哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    unit = session.QAList[queston]
    async with session:
        unit.hit_probability = hit_probability
        unit.oprate_log += f"\n{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
        unit.update_by = int(await adapter.get_unit_id_from_event(bot, event))
    finish_msgs = ["设置成功", "完成啦", "好勒！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


qa_clear = on_command("清空问答库",
                      aliases={"清空全局问答库"},
                      block=True,
                      rule=only_command(),
                      permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                      | PRIVATE_FRIEND)


@qa_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            state: T_State,
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session
    state["session"] = session
    if not session.QAList:
        await matcher.finish("问答库还空空如也呢~")
    await matcher.pause(f">>警告，发送确认清空已继续操作<<")


@qa_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            state: T_State,
            message: v11.Message = EventMessage()):
    session = state["session"]
    msg = str(message).strip()
    if msg == "确认清空":
        async with session:
            session.QAList = {}
        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["未确认的操作", "操作已取消"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


qa_list = on_command("问答列表",
                     aliases={
                         "问答库列表", "问题列表", "全局问答库列表", "全局问题列表", "全局问答列表",
                         "全局问答库", "问答库", "你学过什么"
                     },
                     block=True,
                     permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                     | PRIVATE_FRIEND
                     | perm_check_permission("问答库"))


@qa_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session
    size = 5
    questons = [q for q in session.QAList.keys()]
    count = len(questons)
    maxpage = math.ceil(count / size)

    if count == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    mode_map = {
        QAMode.KEY: "关键词",
        QAMode.FULL: "完全",
        QAMode.LIKE: "模糊",
    }

    queston_part = questons[(arg.page - 1) * size:arg.page * size]
    msg = f"{arg.page}/{maxpage}"
    for queston in queston_part:
        msg += v11.MessageSegment.text("\n")
        msg += v11.Message(queston)
        msg += v11.MessageSegment.text(
            f" > {len(session.QAList[queston].answers)}条回复({mode_map[session.QAList[queston].mode]})"
        )
    await matcher.finish(msg)


qa_view = on_command(
    "检视问题",
    aliases={"查看问答", "查看问题", "检视问答", "查看全局问答", "查看全局问题", "检视全局问答", "检视全局问题"},
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND
    | perm_check_permission("问答库"))


@qa_view.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    if ">" in msg_str:
        msg_str_split = msg_str.split(">", maxsplit=1)
        try:
            page = int(msg_str_split[1])
        except Exception:
            await matcher.finish("查看问题时`>`后边需要是合法的页码！")
        if page <= 0:
            page = 1
        queston = msg_str_split[0]
    else:
        page = 1
        queston = msg_str
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    if queston not in session.QAList:
        finish_msgs = ["问题不存在哦！", "唔，没找到这个问题哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    mode_map = {
        QAMode.KEY: "关键词",
        QAMode.FULL: "完全",
        QAMode.LIKE: "模糊",
    }

    unit = session.QAList[queston]

    items = unit.answers
    size = 5
    count = len(items)
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["回答为空", "震惊，居然没有回复吗！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    group_id = event.group_id if isinstance(event,
                                            v11.GroupMessageEvent) else None

    if page == 1:
        finish_msg = f"共有{len(unit.answers)}个回答({mode_map[unit.mode]})"
        finish_msg += f"\n回复率：{unit.hit_probability}%"
        if unit.alias:
            finish_msg += f"\n别名：{'、'.join(unit.alias)}"
        finish_msg += f"\n更新：{await adapter.get_unit_nick(unit.update_by, group_id=group_id)}({unit.update_by})"
        finish_msg += f"\n创建：{await adapter.get_unit_nick(unit.create_by, group_id=group_id)}({unit.create_by})"
    else:
        finish_msg = f"的回答~"
    if maxpage > 1:
        finish_msg += f"\n{page}/{maxpage}"
    finish_msg = v11.Message(queston) + v11.MessageSegment.text(finish_msg)
    items_part = items[(page - 1) * size:page * size]
    for i in range(len(items_part)):
        finish_msg += v11.MessageSegment.text(
            f"\n{i + (page - 1) * size + 1} | ")
        finish_msg += v11.Message(items_part[i])
    await matcher.finish(finish_msg)


qa_reply_del = on_command("删除回复",
                          aliases={
                              "删除回答", "删除问答回复", "删除问题回复", "删除全局回复", "删除全局回答",
                              "删除全局问答回复", "删除全局问题回复"
                          },
                          block=True,
                          permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                          | PRIVATE_FRIEND
                          | perm_check_permission("问答库"))


@qa_reply_del.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    if ">" not in msg_str:
        await matcher.finish("删除回复时必须提供问题与序号哦！")
    msg_str_split = msg_str.split(">", maxsplit=1)
    try:
        reply_id = int(msg_str_split[1])
    except Exception:
        await matcher.finish("删除回复时`>`后边需要是合法的回复序号！")
    if reply_id <= 0:
        await matcher.finish("删除回复时`>`后边需要是合法的回复序号！")
    queston = msg_str_split[0]
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    if queston not in session.QAList:
        finish_msgs = ["问题不存在哦！", "唔，没找到这个问题哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    unit = session.QAList[queston]
    if reply_id > len(unit.answers):
        finish_msgs = ["啊咧，回复不存在哦！", "并没有找到对应回复"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    async with session:
        unit.answers.pop(reply_id - 1)
        unit.update_by = int(await adapter.get_unit_id_from_event(bot, event))
        unit.oprate_log += f"\n删除回复 {await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
    await matcher.finish(f"删除了该问题的一个回复(序列 {reply_id})")


qa_alia_add = on_command("添加问题别名",
                         aliases={"添加别名", "添加全局问题别名", "添加全局别名"},
                         block=True,
                         permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                         | PRIVATE_FRIEND
                         | perm_check_permission("问答库"))


@qa_alia_add.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    if ">" not in msg_str:
        await matcher.finish("删除别名时必须提供问题与别名序号哦！")
    msg_str_split = msg_str.split(">", maxsplit=1)

    queston = msg_str_split[0]
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")

    alia_name = msg_str_split[1]
    if ">" in alia_name:
        await matcher.finish("别名不能包含`>`号哦！")
    if len(alia_name) <= 1:
        await matcher.finish("别名至少两个字符哦！")

    if queston not in session.QAList:
        finish_msgs = ["问题不存在哦！", "唔，没找到这个问题哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    unit = session.QAList[queston]
    if alia_name in unit.alias:
        finish_msgs = ["啊咧，别名已经存在了哦！", "重复的别名哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    async with session:
        unit.alias.append(alia_name)
        unit.update_by = int(await adapter.get_unit_id_from_event(bot, event))
        unit.oprate_log += f"\n添加别名 {await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
    await matcher.finish(f"添加了该问题的一个别名(序列 {len(unit.alias)})")


qa_alia_del = on_command("删除问题别名",
                         aliases={"删除别名", "删除全局问题别名", "删除全局别名"},
                         block=True,
                         permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                         | PRIVATE_FRIEND
                         | perm_check_permission("问答库"))


@qa_alia_del.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    if ">" not in msg_str:
        await matcher.finish("删除别名时必须提供问题与别名名称哦！")
    msg_str_split = msg_str.split(">", maxsplit=1)

    alia_name = msg_str_split[1]
    if ">" in alia_name:
        await matcher.finish("别名不能包含`>`号哦！")
    if len(alia_name) <= 1:
        await matcher.finish("别名至少两个字符哦！")

    queston = msg_str_split[0]
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    if queston not in session.QAList:
        finish_msgs = ["问题不存在哦！", "唔，没找到这个问题哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    unit = session.QAList[queston]
    if alia_name not in unit.alias:
        finish_msgs = ["啊咧，别名不存在哦！", "并没有找到对应别名"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    async with session:
        unit.alias.remove(alia_name)
        unit.update_by = int(await adapter.get_unit_id_from_event(bot, event))
        unit.oprate_log += f"\n删除别名 {await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
    await matcher.finish(f"删除了该问题的一个别名")


qa_alias_clear = on_command("清空问答别名",
                            aliases={"清空全局问答别名"},
                            block=True,
                            permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                            | PRIVATE_FRIEND)


@qa_alias_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            state: T_State,
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "全局" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session

    if not session.QAList:
        await matcher.finish("问答库还空空如也呢~")
    queston = msg.extract_plain_text().strip()
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    if queston not in session.QAList:
        finish_msgs = ["问题不存在哦！", "唔，没找到这个问题哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    state["session"] = session
    state["queston"] = queston
    await matcher.pause(f">>警告，发送确认清空已继续操作<<")


@qa_alias_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            state: T_State,
            adapter: Adapter = AdapterDepend(),
            message: v11.Message = EventMessage()):
    session: QASession = state["session"]
    queston = state["queston"]
    unit = session.QAList[queston]
    msg = str(message).strip()
    if msg == "确认清空":
        async with session:
            unit.alias.clear()
            unit.oprate_log += f"\n清空别名 {await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["未确认的操作", "操作已取消"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


qa_index_check = on_command(
    "索引问题",
    aliases={"全局索引问题", "问题索引", "全局问题索引", "全局索引问答", "问答索引", "全局问答索引", "索引问答"},
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND)


@qa_index_check.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            msg: v11.Message = CommandArg(),
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if not g_session.QAList and not p_session.QAList:
        await matcher.finish("还没有设置任何问答哦……")
    msg_str = str(msg).strip()
    qa_keys = set()

    def use_qa_unit(queston, qa_unit: QAUnit) -> bool:
        if qa_unit.mode == QAMode.KEY:
            if queston in msg_str:
                return True
        elif qa_unit.mode == QAMode.FULL:
            if queston == msg_str:
                return True
        elif qa_unit.mode == QAMode.LIKE:
            if queston in msg_str and len(msg_str) <= len(queston) * 25:
                return True
        else:
            logger.warning("未知的问答模式：{}", qa_unit)
        return False

    async def select_answers(queston, qa_unit: QAUnit):
        if not use_qa_unit(queston, qa_unit):
            return
        qa_keys.add(qa_unit.queston)

    async def find_qa():
        if g_session.QAList:
            for queston in g_session.QAList:
                qa_unit = g_session.QAList[queston]
                await select_answers(queston, qa_unit)

            for queston in g_session._alias_index:
                alia_units = g_session._alias_index[queston]
                for alia_unit in alia_units:
                    await select_answers(queston, alia_unit)

        if not g_session.global_enable or not p_session.global_enable or not p_session.QAList:
            return

        for queston in p_session.QAList:
            qa_unit = p_session.QAList[queston]
            await select_answers(queston, qa_unit)

        for queston in p_session._alias_index:
            alia_units = p_session._alias_index[queston]
            for alia_unit in alia_units:
                await select_answers(queston, alia_unit)

    await find_qa()
    if not qa_keys:
        await matcher.finish("阿拉，没有找到相关问答。")
    msg = v11.MessageSegment.text("索引列表：") + v11.Message("、".join(qa_keys))
    await matcher.finish(msg)


qa_auto_reply = on_message(priority=99, block=False, rule=None)


@qa_auto_reply.handle()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            msg: v11.Message = EventMessage()):
    if not g_session.QAList and not p_session.QAList:
        return
    msg_str = str(msg).strip()

    def use_qa_unit(queston, qa_unit: QAUnit) -> bool:
        if qa_unit.mode == QAMode.KEY:
            if queston in msg_str:
                return True
        elif qa_unit.mode == QAMode.FULL:
            if queston == msg_str:
                return True
        elif qa_unit.mode == QAMode.LIKE:
            if queston in msg_str and len(msg_str) <= len(queston) * 25:
                return True
        else:
            logger.warning("未知的问答模式：{}", qa_unit)
        return False

    async def select_answers(queston, qa_unit: QAUnit):
        if not use_qa_unit(queston, qa_unit):
            return
        if len(qa_unit.answers) == 0:
            return
        if qa_unit.hit_probability != 100:
            rand = random.randint(1, 100)
            if rand > qa_unit.hit_probability:
                return
        if len(qa_unit.answers) == 1:
            matcher.stop_propagation()
            await matcher.finish(v11.Message(qa_unit.answers[0]))
        rand_i = random.randint(0, len(qa_unit.answers) - 1)
        matcher.stop_propagation()
        await matcher.finish(v11.Message(qa_unit.answers[rand_i]))

    if g_session.QAList:
        for queston in g_session.QAList:
            qa_unit = g_session.QAList[queston]
            await select_answers(queston, qa_unit)

        for queston in g_session._alias_index:
            alia_units = g_session._alias_index[queston]
            for alia_unit in alia_units:
                await select_answers(queston, alia_unit)

    if not g_session.global_enable or not p_session.global_enable or not p_session.QAList:
        return

    for queston in p_session.QAList:
        qa_unit = p_session.QAList[queston]
        await select_answers(queston, qa_unit)

    for queston in p_session._alias_index:
        alia_units = p_session._alias_index[queston]
        for alia_unit in alia_units:
            await select_answers(queston, alia_unit)


qa_enable_global = on_command("启用全局问答库",
                              aliases={"打开全局问答库", "默认启用全局问答库", "默认打开全局问答库"},
                              rule=only_command(),
                              block=True,
                              permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                              | PRIVATE_FRIEND
                              | perm_check_permission("问答库"))


@qa_enable_global.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "默认" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session

    if session.global_enable:
        await matcher.finish("阿拉，已经是启用的状态了")
    async with session:
        session.global_enable = True
    if "默认" in start:
        await matcher.finish("全局问答库已默认启用~")
    else:
        await matcher.finish("已启用全局问答库~")


qa_disable_global = on_command("禁用全局问答库",
                               aliases={"关闭全局问答库", "默认禁用全局问答库", "默认关闭全局问答库"},
                               rule=only_command(),
                               block=True,
                               permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                               | PRIVATE_FRIEND
                               | perm_check_permission("问答库"))


@qa_disable_global.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            p_session: QASession = SessionPluginDepend(QASession),
            g_session: QASession = SessionDepend(),
            start: str = RawCommand()):
    if "默认" in start:
        session = p_session
        if not await SUPERUSER(bot, event):
            await matcher.finish()
    else:
        session = g_session

    if session.global_enable:
        await matcher.finish("阿拉，已经是禁用的状态了")
    async with session:
        session.global_enable = True
    if "默认" in start:
        await matcher.finish("全局问答库已默认禁用~")
    else:
        await matcher.finish("已禁用全局问答库~")
