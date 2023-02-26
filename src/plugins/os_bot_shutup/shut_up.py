import asyncio
import random
from time import time, localtime, strftime
from typing import Any, Dict, Optional
from typing_extensions import Self
from dataclasses import dataclass, field
from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.adapters import Bot
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, PRIVATE_FRIEND
from nonebot.params import CommandStart
from nonebot.exception import IgnoredException, MockApiException
from nonebot.message import run_preprocessor
from .config import config
from .logger import logger

from ..os_bot_base.argmatch import ArgMatch, Field

from ..os_bot_base.session import Session, StoreSerializable
from ..os_bot_base.depends import SessionPluginDepend, ArgMatchDepend, Adapter, AdapterDepend, AdapterFactory
from ..os_bot_base.util import matcher_exception_try, get_plugin_session, seconds_to_dhms


class ShutUpLevel:
    SHUT_LEVEL_LOW: int = 0
    SHUT_LEVEL_MIDDLE: int = 1
    SHUT_LEVEL_HIGH: int = 2


@dataclass
class ShutUpUnit(StoreSerializable):
    """
        安静一会的相关数据

        - `shut_mark` 需要安静的mark
        - `shut_time` 过期时间戳，为小于等于0时永久闭嘴
        - `shut_level` 过滤等级
        - `oprate_log` 操作日志
        - `create_time` 创建时间

        过滤等级

        低 禁用除本插件及核心插件以外的插件（默认）
        
        中 禁用除本插件以外的插件

        高 禁用所有插件，包括被动消息推送（超级管理员则不受影响）

        > 在超级管理员私聊时中高级别过滤会被视为低级别过滤
        > 超级管理员、管理员、群主在群聊时，高级过滤将被视为中级别过滤
    """
    shut_mark: str = field(default=None)  # type: ignore
    shut_time: int = field(default=0)  # type: ignore
    shut_level: int = field(default=ShutUpLevel.SHUT_LEVEL_LOW)  # type: ignore
    oprate_log: str = field(default=None)  # type: ignore
    create_time: int = field(default_factory=(lambda: int(time())), init=False)

    def is_shut_up(self):
        if self.shut_time <= 0:
            return True
        return self.shut_time > time()

    def shut_time_str(self):
        time_str = "永远"
        if self.shut_time > 0:
            time_str = strftime('%Y-%m-%d %H:%M:%S', localtime(self.shut_time))
        return time_str


class ShutUpSession(Session):
    shut_up_list: Dict[str, ShutUpUnit]

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.shut_up_list = {}

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)

        # 加载 shut_list
        tmp_list: Dict[str, Any] = self.shut_up_list  # type: ignore
        self.shut_up_list = {}
        for key in tmp_list:
            unit = ShutUpUnit._load_from_dict(tmp_list[key])  # type: ignore
            self.shut_up_list[key] = unit

        return self


@run_preprocessor
async def _(bot: Bot,
            event: v11.MessageEvent,
            matcher: Matcher,
            adapter: Adapter = AdapterDepend()):
    """
        这个钩子函数会在 NoneBot2 运行 matcher 前运行。
    """
    plugin = matcher.plugin
    if not plugin:
        return

    if plugin.name == "nonebot_plugin_apscheduler":
        return

    session: ShutUpSession = await get_plugin_session(ShutUpSession
                                                      )  # type: ignore
    mark = await adapter.mark_group_without_drive(bot, event)

    if mark not in session.shut_up_list:
        return

    shut_up = session.shut_up_list[mark]
    shut_level = shut_up.shut_level

    if not shut_up.is_shut_up():
        return

    if isinstance(event, v11.PrivateMessageEvent):
        if await SUPERUSER(bot,
                           event) and shut_level != ShutUpLevel.SHUT_LEVEL_LOW:
            shut_level = ShutUpLevel.SHUT_LEVEL_LOW

    if isinstance(event, v11.GroupMessageEvent
                  ) and shut_level == ShutUpLevel.SHUT_LEVEL_HIGH:
        if await SUPERUSER(bot, event) or await GROUP_ADMIN(
                bot, event) or await GROUP_OWNER(bot, event):
            shut_level = ShutUpLevel.SHUT_LEVEL_MIDDLE

    # 对不同级别过滤采取不同的放行措施
    if shut_level != ShutUpLevel.SHUT_LEVEL_HIGH:
        if plugin.name == "os_bot_shutup":
            return
        if shut_level != ShutUpLevel.SHUT_LEVEL_MIDDLE and plugin.name == "os_bot_base":
            return

    logger.info("在对象`{}`中处于休眠状态，消息处理已禁用", mark)
    raise IgnoredException("")


@Bot.on_calling_api
async def _(bot: Bot, api: str, data: Dict[str, Any]):
    """
        API 请求前
    """
    if not isinstance(bot, v11.Bot):
        return

    if api not in [
            "send_msg", "send_private_msg", "send_group_msg",
            "send_group_forward_msg", "send_private_forward_msg"
    ]:
        return

    session: ShutUpSession = await get_plugin_session(  # type: ignore
        ShutUpSession)
    adapter: Adapter = AdapterFactory.get_adapter(bot)
    if data.get("group_id"):
        mark = f"{adapter.get_type()}-global-group-{data.get('group_id')}"
    elif data.get("user_id"):
        mark = f"{adapter.get_type()}-global-private-{data.get('user_id')}"
        try:
            if data.get("user_id") in config.superusers or int(
                    data.get("user_id", 0)) in config.superusers:
                return
        except:
            pass
    else:
        return

    if mark not in session.shut_up_list:
        return

    shut_up = session.shut_up_list[mark]
    shut_level = shut_up.shut_level

    if not shut_up.is_shut_up():
        return

    # 对不同级别过滤采取不同的放行措施
    if shut_level != ShutUpLevel.SHUT_LEVEL_HIGH:
        return

    shut_up_result = {
        "status": "500",
        "retcode": 500,
        "msg": "此用户或群组已被禁用（hook）",
        "wording": "此用户或群组已被禁用（hook）",
    }

    logger.info("在对象`{}`中处于完全休眠状态，消息发送已禁用", mark)
    raise MockApiException(shut_up_result)


class ShutUpArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "闭嘴参数"
        des = "闭嘴（"

    shut_up_time: int = Field.RelateTime("安静时长", default=3600, require=False)

    shut_up_level: int = Field.Keys("过滤等级", {
        ShutUpLevel.SHUT_LEVEL_LOW: ["低"],
        ShutUpLevel.SHUT_LEVEL_MIDDLE: ["中", "非常安静", "很安静的那种", "很安静"],
        ShutUpLevel.SHUT_LEVEL_HIGH: ["高", "完全安静", "完全静默", "完全", "特别安静"],
    },
                                    default=ShutUpLevel.SHUT_LEVEL_LOW)

    def __init__(self) -> None:
        super().__init__([self.shut_up_time, self.shut_up_level])


shut_up_create = on_command(
    "闭嘴",
    aliases={"安静", "睡一会", "安静一会", "休眠", "别说话", "肃静", "禁声", "禁言"},
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND)


@shut_up_create.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            arg: ShutUpArg = ArgMatchDepend(ShutUpArg),
            command_start: str = CommandStart(),
            adapter: Adapter = AdapterDepend(),
            session: ShutUpSession = SessionPluginDepend(ShutUpSession)):

    mark = await adapter.mark_group_without_drive(bot, event)

    # if mark in session.shut_up_list and session.shut_up_list[mark].is_shut_up(
    # ):
    #     await matcher.finish(
    #         f"已经安静至{session.shut_up_list[mark].shut_time_str()}了哦")
    shut_up_level = arg.shut_up_level
    shut_up_time = arg.shut_up_time + int(
        time()) if arg.shut_up_time > 0 else 0
    interval = arg.shut_up_time
    if arg.shut_up_time == -1 and command_start in ["安静一会", "睡一会"]:
        shut_up_time = int(time()) + 900
        interval = 900

    if command_start in ("禁言",
                         "禁声") and shut_up_level == ShutUpLevel.SHUT_LEVEL_LOW:
        shut_up_level = ShutUpLevel.SHUT_LEVEL_HIGH

    async def lay_deal():
        async with session:
            session.shut_up_list[mark] = ShutUpUnit(
                shut_mark=mark,
                shut_time=shut_up_time,
                shut_level=shut_up_level,
                oprate_log=
                f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
            )
        if arg.shut_up_time == -1 and command_start in ["安静一会", "睡一会"]:
            await bot.send(event, "我会安静一会")
        if interval == 0:
            await bot.send(event, "休眠模式已启用")
        else:
            await bot.send(
                event, f"好的~我会休眠至{seconds_to_dhms(interval, compact=True)}后哦")

    asyncio.gather(lay_deal())
    await matcher.finish()


shut_up_rescind = on_command("醒醒",
                             aliases={
                                 "醒一醒", "别睡了", "起来干活", "好了你可以说了", "你可以说话了",
                                 "可以说话了", "起床", "起来嗨", "解除禁言"
                             },
                             block=True,
                             permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                             | PRIVATE_FRIEND)


@shut_up_rescind.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: ShutUpSession = SessionPluginDepend(ShutUpSession)):

    mark = await adapter.mark_group_without_drive(bot, event)

    if mark not in session.shut_up_list or not session.shut_up_list[
            mark].is_shut_up():
        await matcher.finish(f"没有在休眠状态哦")

    async with session:
        del session.shut_up_list[mark]

    finish_msgs = ["醒来！", "我在！", "我醒啦", "复活！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


shut_up_view = on_command("在休眠吗",
                          aliases={"醒着吗", "在睡觉吗"},
                          block=True,
                          permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                          | PRIVATE_FRIEND)


@shut_up_view.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: ShutUpSession = SessionPluginDepend(ShutUpSession)):
    mark = await adapter.mark_group_without_drive(bot, event)

    level = {
        ShutUpLevel.SHUT_LEVEL_LOW: "低",
        ShutUpLevel.SHUT_LEVEL_MIDDLE: "中",
        ShutUpLevel.SHUT_LEVEL_HIGH: "高",
    }
    if (mark in session.shut_up_list
            and session.shut_up_list[mark].is_shut_up()):
        await matcher.finish(
            f"休眠至{session.shut_up_list[mark].shut_time_str()}，等级 {level[session.shut_up_list[mark].shut_level]}"
        )

    await matcher.finish(f"并没有~")


class ShutUpManageArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "闭嘴参数"
        des = "进行一个定向的闭嘴（"

    drive_type: str = Field.Keys("驱动", {
        "ob11": ["onebot11", "gocqhttp"],
    },
                                 default="ob11",
                                 ignoreCase=True,
                                 require=False)

    group_type: str = Field.Keys("组标识", {
        "group": ["g", "group", "组", "群", "群聊"],
        "private": ["p", "private", "私聊", "好友", "私"],
    },
                                 ignoreCase=True)
    unit_id: int = Field.Int("组ID", min=9999, max=99999999999)

    shut_up_time: int = Field.RelateTime("安静时长", default=-1, require=False)

    shut_up_level: int = Field.Keys("过滤等级", {
        ShutUpLevel.SHUT_LEVEL_LOW: ["低"],
        ShutUpLevel.SHUT_LEVEL_MIDDLE: ["中"],
        ShutUpLevel.SHUT_LEVEL_HIGH: ["高"],
    },
                                    default=ShutUpLevel.SHUT_LEVEL_LOW)

    def __init__(self) -> None:
        super().__init__([
            self.drive_type, self.group_type, self.unit_id, self.shut_up_time,
            self.shut_up_level
        ])


shut_up_oprate = on_command("指定禁言",
                            aliases={"远程禁言"},
                            block=True,
                            permission=SUPERUSER)


@shut_up_oprate.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: ShutUpManageArg = ArgMatchDepend(ShutUpManageArg),
            adapter: Adapter = AdapterDepend(),
            session: ShutUpSession = SessionPluginDepend(ShutUpSession)):
    mark = f"{arg.drive_type}-global-{arg.group_type}-{arg.unit_id}"

    shut_up_level = arg.shut_up_level
    shut_up_time = arg.shut_up_time + int(
        time()) if arg.shut_up_time > 0 else 0

    async with session:
        session.shut_up_list[mark] = ShutUpUnit(
            shut_mark=mark,
            shut_time=shut_up_time,
            shut_level=shut_up_level,
            oprate_log=
            f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
        )

    nick = arg.unit_id
    if arg.group_type == "group":
        nick = await adapter.get_group_nick(arg.unit_id, bot)
    else:
        nick = await adapter.get_unit_nick(arg.unit_id, bot)

    await matcher.finish(
        f"已为{'群' if arg.group_type == 'group' else ''}{nick}({arg.unit_id})创建休眠任务，至{session.shut_up_list[mark].shut_time_str()}结束"
    )


shut_up_oprate = on_command("指定解除禁言",
                            aliases={"远程取消禁言", "远程解除禁言"},
                            block=True,
                            permission=SUPERUSER)


@shut_up_oprate.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: ShutUpManageArg = ArgMatchDepend(ShutUpManageArg),
            session: ShutUpSession = SessionPluginDepend(ShutUpSession)):

    mark = f"{arg.drive_type}-global-{arg.group_type}-{arg.unit_id}"

    if mark not in session.shut_up_list or not session.shut_up_list[
            mark].is_shut_up():
        await matcher.finish(f"对象没有在休眠状态哦")

    async with session:
        del session.shut_up_list[mark]

    nick = arg.unit_id
    if arg.group_type == "group":
        nick = await adapter.get_group_nick(arg.unit_id, bot)
    else:
        nick = await adapter.get_unit_nick(arg.unit_id, bot)

    nick = f"{'群' if arg.group_type == 'group' else ''}{nick}({arg.unit_id})"

    finish_msgs = ["操作成功", f"对{nick}的操作已生效", "成功啦"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])
