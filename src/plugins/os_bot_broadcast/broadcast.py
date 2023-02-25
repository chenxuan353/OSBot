import asyncio
import math
import random
from time import time
from typing import Any, Dict, List
from typing_extensions import Self
from nonebot import on_command
from nonebot.typing import T_State
from nonebot.adapters import Bot
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.params import EventMessage
from nonebot.adapters.onebot import v11
from dataclasses import dataclass, field

from .logger import logger

from ..os_bot_base.depends import SessionDriveDepend, ArgMatchDepend, AdapterDepend, Adapter
from ..os_bot_base.session import Session, StoreSerializable
from ..os_bot_base.util import matcher_exception_try, plug_is_disable
from ..os_bot_base.argmatch import ArgMatch, Field
from ..os_bot_base.notice import BotSend, LeaveGroupHook, UrgentNotice


@dataclass
class BroadcastUnit(StoreSerializable):
    nick: str = field(default="")
    drive_type: str = field(default="")
    group_type: str = field(default="")
    unit_id: int = field(default=0)
    bot_id: int = field(default=0)
    create_time: int = field(default_factory=(lambda: int(time())), init=False)


class BroadcastSession(Session):
    channels: Dict[str, Dict[str, BroadcastUnit]]
    """频道列表"""

    history: List[str]
    """广播历史 记录指令原文"""

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.channels = {}
        self.history = []

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        for channel in self.channels:
            self.channels[channel] = {
                key: BroadcastUnit._load_from_dict(item)  # type: ignore
                for key, item in self.channels[channel].items()
            }
        return self


class BroadcastChannelArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "广播频道参数"
        des = "管理广播频道"

    channel: str = Field.Str("频道")
    unit_name: str = Field.Str("名称", require=False)

    def __init__(self) -> None:
        super().__init__([self.channel, self.unit_name])


class BroadcastArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "广播参数"
        des = "管理广播频道"

    drive_type: str = Field.Keys("驱动", {
        "ob11": ["onebot11", "gocqhttp"],
    },
                                 default="ob11",
                                 require=False)

    group_type: str = Field.Keys(
        "组标识", {
            "group": ["g", "group", "组", "群", "群聊"],
            "private": ["p", "private", "私聊", "好友", "私"],
        })
    unit_id: int = Field.Int("组ID", min=9999, max=99999999999)

    channel: str = Field.Str("频道")

    unit_name: str = Field.Str("名称", require=False)

    def __init__(self) -> None:
        super().__init__([
            self.drive_type, self.group_type, self.unit_id, self.channel,
            self.unit_name
        ])


broadcast = on_command("广播", aliases={"发送广播"}, permission=SUPERUSER)


@broadcast.handle()
@matcher_exception_try()
async def _(
        matcher: Matcher,
        bot: Bot,
        event: v11.PrivateMessageEvent,
        state: T_State,
        adapter: Adapter = AdapterDepend(),
        session: BroadcastSession = SessionDriveDepend(BroadcastSession),
        arg: BroadcastChannelArg = ArgMatchDepend(BroadcastChannelArg),
):
    if arg.channel not in session.channels:
        await matcher.finish("频道不存在哦")

    if len(session.channels[arg.channel]) == 0:
        await matcher.finish("频道为空哦...")

    state["channel"] = arg.channel
    await matcher.finish("要广播什么呢？")


@broadcast.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            state: T_State,
            msg: v11.Message = EventMessage()):
    state["msg"] = msg
    await matcher.pause(f"确认要向频道`{state['channel']}`广播上述信息吗？")


@broadcast.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.PrivateMessageEvent,
            state: T_State,
            adapter: Adapter = AdapterDepend(),
            message: v11.Message = EventMessage(),
            session: BroadcastSession = SessionDriveDepend(BroadcastSession)):

    msg = str(message).strip()
    if msg not in ["确认广播", "确认发送", "发送", "确认"]:
        finish_msgs = ["pass", "取消操作"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    async def send():
        success_count = 0
        failure_count = 0
        for channelKey in session.channels[state["channel"]]:
            channelUnit = session.channels[state["channel"]][channelKey]
            mark = f"{adapter.get_type()}-global-{channelUnit.group_type}-{channelUnit.unit_id}"
            if await plug_is_disable("os_bot_broadcast", mark):
                logger.info("因组 {} 的广播插件被关闭，广播推送取消。",mark)
                UrgentNotice.add_notice(f"{mark}的广播操作因插件被关闭取消！")
                continue

            if channelUnit.group_type == "group":
                send_params = {"group_id": channelUnit.unit_id}
            else:
                send_params = {"user_id": channelUnit.unit_id}
            success = await BotSend.send_msg(
                channelUnit.drive_type, send_params, state["msg"],
                f"{channelUnit.bot_id}" if channelUnit.bot_id else None)
            if not success:
                failure_count += 1
                msg = f"向`{state['channel']}`的{channelKey}广播讯息失败"
                logger.warning(msg)
                UrgentNotice.add_notice(msg)
            else:
                success_count += 1
            if success:
                await asyncio.sleep(random.randint(1000, 5000) / 1000)
        await matcher.finish(f"对`{state['channel']}`的广播完成~" +
                             (f"成功{success_count} 失败{failure_count}" if
                              failure_count != 0 else f"共发送{success_count}"))

    asyncio.gather(send())
    await matcher.finish(f"正在向`{state['channel']}`广播讯息~")


channel_create = on_command("创建广播频道", permission=SUPERUSER)


@channel_create.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            session: BroadcastSession = SessionDriveDepend(BroadcastSession),
            arg: BroadcastChannelArg = ArgMatchDepend(BroadcastChannelArg)):
    if arg.channel in session.channels:
        await matcher.finish("频道已存在！")

    async with session:
        session.channels[arg.channel] = {}

    await matcher.finish(f"频道 {arg.channel} 创建成功")


channel_remove = on_command("移除广播频道", permission=SUPERUSER)


@channel_remove.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            session: BroadcastSession = SessionDriveDepend(BroadcastSession),
            arg: BroadcastChannelArg = ArgMatchDepend(BroadcastChannelArg)):
    if arg.channel not in session.channels:
        await matcher.finish("频道不存在！！！")
    finish_msgs = ["请发送`确认清空`确认~", "通过`确认清空`继续操作哦"]
    await matcher.pause(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


@channel_remove.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            message: v11.Message = EventMessage(),
            session: BroadcastSession = SessionDriveDepend(BroadcastSession),
            arg: BroadcastChannelArg = ArgMatchDepend(BroadcastChannelArg)):
    msg = str(message).strip()
    if msg == "确认清空":
        async with session:
            del session.channels[arg.channel]
        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["未确认操作", "pass"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


channel_unit_add = on_command("添加广播对象",
                              aliases={"增加广播对象", "新增广播对象"},
                              permission=SUPERUSER)


@channel_unit_add.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BroadcastSession = SessionDriveDepend(BroadcastSession),
            arg: BroadcastArg = ArgMatchDepend(BroadcastArg)):
    if arg.channel not in session.channels:
        await matcher.finish("频道不存在！！！")
    mark = f"{adapter.get_type()}-{arg.group_type}-{arg.unit_id}"
    if mark in session.channels[arg.channel]:
        await matcher.finish("对象已经存在！")
    unit = BroadcastUnit(arg.unit_name, adapter.get_type(), arg.group_type,
                         arg.unit_id, int(bot.self_id))
    async with session:
        session.channels[arg.channel][mark] = unit

    nick = arg.unit_id
    if arg.group_type == "group":
        nick = await adapter.get_group_nick(arg.unit_id, bot)
    else:
        nick = await adapter.get_unit_nick(arg.unit_id, bot)

    await matcher.finish(
        f"为`{arg.channel}`添加了{'群' if arg.group_type == 'group' else ''}对象 ({nick}){arg.unit_id}"
    )


channel_unit_del = on_command("删除广播对象",
                              aliases={"移除广播对象", "减少广播对象"},
                              permission=SUPERUSER)


@channel_unit_del.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.PrivateMessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BroadcastSession = SessionDriveDepend(BroadcastSession),
            arg: BroadcastArg = ArgMatchDepend(BroadcastArg)):
    if arg.channel not in session.channels:
        await matcher.finish("频道不存在！！！")
    mark = f"{adapter.get_type()}-{arg.group_type}-{arg.unit_id}"
    if mark not in session.channels[arg.channel]:
        await matcher.finish("对象不存在！！！")
    async with session:
        del session.channels[arg.channel][mark]

    nick = arg.unit_id
    if arg.unit_name:
        nick = arg.unit_name
    elif arg.group_type == "group":
        nick = await adapter.get_group_nick(arg.unit_id, bot)
    else:
        nick = await adapter.get_unit_nick(arg.unit_id, bot)

    await matcher.finish(
        f"从`{arg.channel}`移除了{'群' if arg.group_type == 'group' else ''}对象 ({nick}){arg.unit_id}"
    )


channel_unit_join = on_command("加入频道", aliases={"进入频道"}, permission=SUPERUSER)


@channel_unit_join.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BroadcastSession = SessionDriveDepend(BroadcastSession),
            arg: BroadcastChannelArg = ArgMatchDepend(BroadcastChannelArg)):
    if arg.channel not in session.channels:
        await matcher.finish("频道不存在！！！")
    if isinstance(event, v11.GroupMessageEvent):
        mark = f"{adapter.get_type()}-group-{event.group_id}"
    elif isinstance(event, v11.PrivateMessageEvent):
        mark = f"{adapter.get_type()}-private-{event.user_id}"
    else:
        await matcher.finish("不支持的消息类型")
    if mark in session.channels[arg.channel]:
        await matcher.finish("已经在该频道中了哦")
    group_type = "group" if isinstance(event,
                                       v11.GroupMessageEvent) else "private"
    unit_id = event.group_id if isinstance(
        event, v11.GroupMessageEvent) else event.user_id

    unit = BroadcastUnit(arg.unit_name, adapter.get_type(), group_type,
                         unit_id, int(bot.self_id))
    async with session:
        session.channels[arg.channel][mark] = unit

    await matcher.finish(f"已成功加入频道`{arg.channel}`")


channel_unit_quit = on_command("退出频道", permission=SUPERUSER)


@channel_unit_quit.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BroadcastSession = SessionDriveDepend(BroadcastSession),
            arg: BroadcastChannelArg = ArgMatchDepend(BroadcastChannelArg)):
    if arg.channel not in session.channels:
        await matcher.finish("频道不存在！！！")
    if isinstance(event, v11.GroupMessageEvent):
        mark = f"{adapter.get_type()}-group-{event.group_id}"
    elif isinstance(event, v11.PrivateMessageEvent):
        mark = f"{adapter.get_type()}-private-{event.user_id}"
    else:
        await matcher.finish("不支持的消息类型")
    if mark not in session.channels[arg.channel]:
        await matcher.finish("不在该频道中哦")

    async with session:
        del session.channels[arg.channel][mark]

    await matcher.finish(f"已成功退出频道`{arg.channel}`")


class BroadcastChannelFilterArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "广播频道参数"
        des = "过滤广播频道"

    channel: str = Field.Str("频道", require=False)
    page: int = Field.Int("页数", min=1, default=1, help="页码，大于等于1。")

    def __init__(self) -> None:
        super().__init__([self.channel, self.page])


channel_list = on_command("频道列表",
                          aliases={"查看频道列表", "打开频道列表"},
                          permission=SUPERUSER)


@channel_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.PrivateMessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BroadcastSession = SessionDriveDepend(BroadcastSession),
            arg: BroadcastChannelFilterArg = ArgMatchDepend(
                BroadcastChannelFilterArg)):
    if arg.channel and arg.channel not in session.channels:
        await matcher.finish("频道不存在哦~")

    if not arg.channel:
        await matcher.finish(
            f"频道列表：{'、'.join([key for key in session.channels])}")

    size = 50
    channel = session.channels[arg.channel]
    keys = list(channel.keys())
    count = len(keys)
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["暂无通知~", "没有通知哦"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")
    list_page = keys[(arg.page - 1) * size:arg.page * size]
    msg = f"{arg.page}/{maxpage}" if count >= 50 else ""
    names = []
    for item in list_page:
        nick = channel[item].unit_id
        if channel[item].nick:
            nick = channel[item].nick
        else:
            if channel[item].group_type == "group":
                nick = await adapter.get_group_nick(channel[item].unit_id, bot)
            else:
                nick = await adapter.get_unit_nick(channel[item].unit_id, bot)
        names.append(
            f"{nick}({'g' if channel[item].group_type == 'group' else 'p'}{channel[item].unit_id})"
        )
    await matcher.finish(f"`{arg.channel}`的成员：{'、'.join(names)}")