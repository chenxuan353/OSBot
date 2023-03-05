import math
import random
from time import strftime
from typing import Any, Dict
from nonebot import on_command, on_message
from nonebot.matcher import Matcher
from nonebot.adapters import Bot
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, PRIVATE_FRIEND
from nonebot.params import CommandArg, EventMessage, CommandStart
from .logger import logger
from .config import QAMode, QASession, QAUnit

from ..os_bot_base.depends import SessionDepend, ArgMatchDepend, AdapterDepend, Adapter
from ..os_bot_base.argmatch import PageArgMatch
from ..os_bot_base.util import matcher_exception_try, only_command
from ..os_bot_base.permission import PermManage, perm_check_permission

PermManage.register("问答库", "问答库管理权限", False, for_group_member=True)


def qa_message_precheck(msg: v11.Message) -> bool:
    for msgseg in msg:
        if msgseg.type not in ("face", "image", "text"):
            return False
    return True


qa_add = on_command("添加问答",
                    aliases={"我教你", "创建问答"},
                    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                    | PRIVATE_FRIEND
                    | perm_check_permission("问答库"))


@qa_add.handle()
@matcher_exception_try()
async def _(
        matcher: Matcher,
        bot: Bot,
        event: v11.MessageEvent,
        adapter: Adapter = AdapterDepend(),
        session: QASession = SessionDepend(),
        msg: v11.Message = CommandArg(),
):
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问答不能为空哦~")
    if ">" not in msg_str:
        await matcher.finish("QA格式：问题>回答1>回答2>回答3，至少包含一个回答")
    msg_splits = msg_str.split(">")
    queston = msg_splits.pop(0)
    answers = msg_splits
    if ">" in queston:
        await matcher.finish("问题不能包含`>`号哦！")
    if len(queston) <= 1:
        await matcher.finish("问题至少两个字符哦！")
    for answer in answers:
        if len(answer) > 100:
            await matcher.finish("单条回答字数上限为：100字")
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
        unit.answers.append(*answers)
        unit.update_by = int(await adapter.get_unit_id_from_event(bot, event))
    await matcher.finish(f"可用知识增加了({len(unit.answers)}->{len(answers)})")


qa_del = on_command("删除问答",
                    aliases={"忘记问题", "移除问答"},
                    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                    | PRIVATE_FRIEND
                    | perm_check_permission("问答库"))


@qa_del.handle()
@matcher_exception_try()
async def _(
        matcher: Matcher,
        event: v11.MessageEvent,
        session: QASession = SessionDepend(),
        msg: v11.Message = CommandArg(),
):
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
    aliases={
        "设置问题完全匹配", "设置问题关键词匹配", "设置问题模糊匹配", "设置问答完全匹配", "设置问答关键词匹配",
        "设置问答模糊匹配", "重置匹配模式", "重置问题匹配"
    },
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER | PRIVATE_FRIEND
    | perm_check_permission("问答库"))


@qa_setting_mode.handle()
@matcher_exception_try()
async def _(
        matcher: Matcher,
        bot: Bot,
        event: v11.MessageEvent,
        adapter: Adapter = AdapterDepend(),
        session: QASession = SessionDepend(),
        start: str = CommandStart(),
        msg: v11.Message = CommandArg(),
):
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


qa_setting_hit_probability = on_command(
    "设置问题回复率",
    aliases={"设置问答回复率", "重置问答回复率", "重置问题回复率", "设置问题回复概率", "设置问答回复概率"},
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER | PRIVATE_FRIEND
    | perm_check_permission("问答库"))


@qa_setting_hit_probability.handle()
@matcher_exception_try()
async def _(
        matcher: Matcher,
        bot: Bot,
        event: v11.MessageEvent,
        adapter: Adapter = AdapterDepend(),
        session: QASession = SessionDepend(),
        start: str = CommandStart(),
        msg: v11.Message = CommandArg(),
):
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    if ">" in msg_str:
        msg_str_split = msg_str.split()
        try:
            hit_probability = int(msg_str_split[1])
        except:
            await matcher.finish("设置问题回复概率时`>`后边需要是1-100的整数！")
        if hit_probability <= 0 or hit_probability > 100:
            await matcher.finish("设置问题回复概率时`>`后边需要是1-100的整数！")
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
                      block=True,
                      rule=only_command(),
                      permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                      | PRIVATE_FRIEND)


@qa_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.MessageEvent,
            session: QASession = SessionDepend()):
    if not session.QAList:
        await matcher.finish("问答库还空空如也呢~")
    await matcher.pause(f">>警告，发送确认清空已继续操作<<")


@qa_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            message: v11.Message = EventMessage(),
            session: QASession = SessionDepend()):
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
                     aliases={"问答库列表", "问题列表"},
                     permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                     | PRIVATE_FRIEND
                     | perm_check_permission("问答库"))


@qa_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.MessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            session: QASession = SessionDepend()):
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
        msg += f"\n{queston} > {len(session.QAList[queston].answers)}回复({mode_map[session.QAList[queston].mode]})"
    await matcher.finish(msg)


qa_view = on_command("检视问题",
                     aliases={"查看问答"},
                     permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                     | PRIVATE_FRIEND
                     | perm_check_permission("问答库"))


@qa_view.handle()
@matcher_exception_try()
async def _(
        matcher: Matcher,
        bot: Bot,
        event: v11.MessageEvent,
        adapter: Adapter = AdapterDepend(),
        session: QASession = SessionDepend(),
        msg: v11.Message = CommandArg(),
):
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    if ">" in msg_str:
        msg_str_split = msg_str.split()
        try:
            page = int(msg_str_split[1])
        except:
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

    if page == 1:
        finish_msg = f"{queston}共有{len(unit.answers)}个回答({mode_map[unit.mode]})"
        finish_msg += f"\n回复率：{unit.hit_probability}%"
        finish_msg += f"\n更新：{await adapter.get_unit_nick(unit.update_by)}({unit.update_by})"
        finish_msg += f"\n创建：{await adapter.get_unit_nick(unit.create_by)}({unit.create_by})"
        finish_msg += "\n通过`删除回复 问题>回答编号`来移除指定回复"
    else:
        finish_msg = f"{queston}的回答~"
    if maxpage > 1:
        finish_msg += f"\n{page}/{maxpage}"
    items_part = items[(page - 1) * size:page * size]
    for i in range(len(items_part)):
        finish_msg += f"\n{i + (page - 1) * size + 1} | {items_part[i]}"
    await matcher.finish(finish_msg)


qa_reply_del = on_command("删除回复",
                          aliases={"删除回答", "删除问答回复", "删除问题回复"},
                          permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                          | PRIVATE_FRIEND
                          | perm_check_permission("问答库"))


@qa_reply_del.handle()
@matcher_exception_try()
async def _(
        matcher: Matcher,
        bot: Bot,
        event: v11.MessageEvent,
        adapter: Adapter = AdapterDepend(),
        session: QASession = SessionDepend(),
        msg: v11.Message = CommandArg(),
):
    if not qa_message_precheck(msg):
        await matcher.finish("消息里有不受支持的元素哦！")
    msg_str = str(msg).strip()
    if not msg_str:
        await matcher.finish("问题不能为空哦~")
    if ">" not in msg_str:
        await matcher.finish("删除回复时必须提供问题与序号哦！")
    msg_str_split = msg_str.split()
    try:
        reply_id = int(msg_str_split[1])
    except:
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
    reply_id -= 1
    unit = session.QAList[queston]
    if reply_id > len(unit.answers) - 1:
        finish_msgs = ["啊咧，回复不存在哦！", "并没有找到对应回复"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    async with session:
        unit.answers.pop(reply_id)
        unit.update_by = int(await adapter.get_unit_id_from_event(bot, event))
        unit.oprate_log += f"\n删除回复 {await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
    await matcher.finish(f"删除了该问题的一个回复(序列 {reply_id})")


qa_auto_reply = on_message(priority=5, block=False, rule=None)


@qa_auto_reply.handle()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            session: QASession = SessionDepend(),
            msg: v11.Message = EventMessage()):
    if not session.QAList:
        return
    msg_str = str(msg).strip()

    def use_qa_unit(qa_unit: QAUnit) -> bool:
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

    for queston in session.QAList:
        qa_unit = session.QAList[queston]
        if not use_qa_unit(qa_unit):
            continue
        if len(qa_unit.answers) == 0:
            continue
        if qa_unit.hit_probability != 100:
            rand = random.randint(1, 100)
            if rand > qa_unit.hit_probability:
                continue
        if len(qa_unit.answers) == 1:
            await matcher.finish(qa_unit.answers[0])
        rand_i = random.randint(0, len(qa_unit.answers) - 1)
        await matcher.finish(qa_unit.answers[rand_i])
