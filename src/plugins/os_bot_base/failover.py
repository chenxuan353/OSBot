"""
    故障转移

    当前仅支持 Onebot适配器

    当一个群存在多个Bot时，故障转移将生效。
    当消息到来时智能指定处理对象（仅群聊）

    忽略事件规则
    1. 设置了优先响应，且对应Bot连接正常，事件对应Bot与优先响应Bot不一致
    2. 群事件最先到来的，且对应Bot连接正常，事件对应Bot与最先到来的Bot不一致
"""
import random
from time import strftime, time
from typing import Any, Dict
from typing_extensions import Self
from dataclasses import dataclass, field
from nonebot import on_command, get_bots, Bot
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from nonebot.rule import to_me
from .argmatch import ArgMatch, Field
from .logger import logger
from .depends import SessionPluginDepend, AdapterDepend, Adapter
from .session import Session, StoreSerializable
from .adapter import AdapterFactory, V11Adapter
from .util import matcher_exception_try, only_command


@dataclass
class PriorityUnit(StoreSerializable):
    """
        优先级

        - `drive_mask` 驱动标识
        - `oprate_log` 操作日志
        - `create_time` 创建时间
    """
    drive_mask: str = field(default="")
    bot_type: str = field(default="")
    bot_id: str = field(default="")
    oprate_log: str = field(default=None)  # type: ignore
    create_time: int = field(default_factory=(lambda: int(time())), init=False)


class LoadBalancingSession(Session):
    priority_map: Dict[str, PriorityUnit]
    """
        优先级地图

        key group_mask
    """
    _auto_priority_map: Dict[str, PriorityUnit]
    """
        自动优先级地图

        key group_mask
    """

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.priority_map = {}
        self._auto_priority_map = {}

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)

        # 加载 priority_map
        tmp_list: Dict[str, Any] = self.priority_map
        self.priority_map = {}
        for key in tmp_list:
            unit = PriorityUnit._load_from_dict(tmp_list[key])
            self.priority_map[key] = unit

        return self

    async def is_priority(self, bot: Bot,
                          event: v11.Event) -> bool:
        """
            判断指定`bot`及`event`所对应的群聊是否是属于优先响应对象
        """
        session: LoadBalancingSession = self
        adapter = AdapterFactory.get_adapter(bot)
        drive_mask = await adapter.mark_drive(bot, event)
        bot_type = adapter.get_type()
        bot_id = await adapter.get_bot_id(bot, event)
        group_mask = await adapter.mark_group_without_drive(bot, event)
        priority = session.priority_map.get(group_mask)
        if await to_me()(bot, event, {}):
            """
                指定对象的事件不处理
            """
            return True
        if priority:
            if priority.drive_mask == drive_mask:
                return True
            if bot_type == V11Adapter.get_type() and bot_id != priority.bot_id:
                """
                    事件来自非优先连接
                """
                bots = get_bots()
                if bots.get(priority.bot_id):
                    return False

        priority = session._auto_priority_map.get(group_mask)
        if priority:
            if priority.drive_mask == drive_mask:
                return True
            if bot_type == V11Adapter.get_type() and bot_id != priority.bot_id:
                """
                    事件来自非优先连接
                """
                bots = get_bots()
                if bots.get(priority.bot_id):
                    return False

        # 放行后注册优先连接
        session._auto_priority_map[group_mask] = PriorityUnit(
            drive_mask=drive_mask,
            bot_type=bot_type,
            bot_id=bot_id,
            oprate_log="auto")

        return True


@event_preprocessor
async def _(
    bot: Bot,
    event: v11.Event,
    state: T_State,
    adapter: Adapter = AdapterDepend(),
    session: LoadBalancingSession = SessionPluginDepend(LoadBalancingSession)):
    if not isinstance(event, v11.GroupMessageEvent) and not isinstance(event, v11.NoticeEvent):
        """仅处理通知及群消息事件的优先响应"""
        return
    try:
        adapter = AdapterFactory.get_adapter(bot)
        drive_mask = await adapter.mark_drive(bot, event)
        group_mask = await adapter.mark_group_without_drive(bot, event)
        if not await session.is_priority(bot, event):
            raise IgnoredException(
                f"因故障转移自动设置 {drive_mask}-{group_mask} 的响应被禁止了")
    except IgnoredException as e:
        logger.debug(e.reason)
        raise e
    except Exception:
        logger.opt(exception=True).error("故障转移未知异常")


class BalanceArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "均衡参数"
        des = "均衡参数"

    unit_uuid: int = Field.Int("设置到哪个",
                               min=9999,
                               max=99999999999,
                               require=False)

    def __init__(self) -> None:
        super().__init__([self.unit_uuid])


set_balance = on_command(
    "优先响应",
    aliases={"响应优先", "优先处理", "就决定是你了", "就决定是你啦", "就决定是你辣", "还得是你"},
    rule=only_command(),
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@set_balance.handle()
@matcher_exception_try()
async def _(
    matcher: Matcher,
    bot: Bot,
    event: v11.MessageEvent,
    adapter: Adapter = AdapterDepend(),
    session: LoadBalancingSession = SessionPluginDepend(LoadBalancingSession)):
    group_mask = await adapter.mark_group_without_drive(bot, event)
    drive_mask = await adapter.mark_drive(bot, event)
    bot_type = adapter.get_type()
    bot_id = await adapter.get_bot_id(bot, event)
    oprate_log = f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"  # 溯源信息
    priority = session.priority_map.get(group_mask)
    if priority and priority.drive_mask == drive_mask:
        finish_msgs = ('已经是我了哦！', '早就是咱啦')
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    # 注册优先连接
    async with session:
        session.priority_map[group_mask] = PriorityUnit(drive_mask=drive_mask,
                                                        bot_type=bot_type,
                                                        bot_id=bot_id,
                                                        oprate_log=oprate_log)
    finish_msgs = ('好耶', '收到', '到我负责了吗？', '了解')
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])
