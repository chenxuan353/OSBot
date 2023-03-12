"""
    # 请求处理

    维护群邀请列表以及好友请求列表，并提供请求处理功能
"""
from dataclasses import dataclass, field
import math
import random
from time import time
from nonebot import on_request, on_command
from nonebot.matcher import Matcher
from nonebot.adapters.onebot import v11
from nonebot.permission import SUPERUSER
from typing import Any, Dict
from typing_extensions import Self
from .depends import SessionDriveDepend, ArgMatchDepend, AdapterDepend, Adapter
from .session import Session, StoreSerializable
from .util import matcher_exception_try
from .argmatch import PageArgMatch, IntArgMatch
from .logger import logger


@dataclass
class RequestUnit(StoreSerializable):
    time: int = field(default=0)
    type: str = field(default="请求")
    """类型"""
    sub_type: str = field(default="add")
    group_id: str = field(default="")
    user_id: str = field(default="")
    """请求发起人"""
    comment: str = field(default="")
    """验证信息"""
    flag: str = field(default="")
    """请求 flag，在调用处理请求的 API 时需要传入"""
    is_oprate: bool = field(default=False)
    """是否已经操作过"""


class RequestSession(Session):
    friends: Dict[int, RequestUnit]
    friend_now_id: int
    groups: Dict[int, RequestUnit]
    group_now_id: int

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.friends = {}
        self.friend_now_id = 1
        self.groups = {}
        self.group_now_id = 1

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        self.friend_now_id = int(self.friend_now_id)
        self.group_now_id = int(self.group_now_id)
        self.friends = {
            int(key): RequestUnit._load_from_dict(friend)  # type: ignore
            for key, friend in self.friends.items()
        }
        self.groups = {
            int(key): RequestUnit._load_from_dict(group)  # type: ignore
            for key, group in self.groups.items()
        }
        return self


request_matcher = on_request()


@request_matcher.handle()
async def _(event: v11.RequestEvent,
            session: RequestSession = SessionDriveDepend(RequestSession)):

    if isinstance(event, v11.GroupRequestEvent):
        request = RequestUnit()
        request.comment = event.comment
        request.group_id = str(event.group_id)
        request.user_id = str(event.user_id)
        request.flag = event.flag
        request.sub_type = event.sub_type
        if event.sub_type == "invite":
            request.type = "邀请"
        async with session:
            session.groups[session.group_now_id] = request
            session.group_now_id += 1
    elif isinstance(event, v11.FriendRequestEvent):
        request = RequestUnit()
        request.comment = event.comment
        request.flag = event.flag
        request.user_id = str(event.user_id)
        async with session:
            session.friends[session.friend_now_id] = request
            session.friend_now_id += 1
    else:
        logger.warning("未知的请求类型 {}", event.request_type)
        return


friend_request_list = on_command(
    "好友请求列表",
    aliases={"好友请求"},
    block=True,
    permission=SUPERUSER,
)


@friend_request_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            session: RequestSession = SessionDriveDepend(RequestSession),
            adapter: Adapter = AdapterDepend()):
    keys = [key for key in session.friends]
    keys.sort(reverse=True)
    size = 10
    count = len(keys)
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["暂时还没收到请求", "没有找到请求哟"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    msg = f"{arg.page}/{maxpage}"
    page_keys = keys[(arg.page - 1) * size:arg.page * size]
    for key in page_keys:
        friend = session.friends[key]
        msg += f"\n{key if not friend.is_oprate else '★'} | {await adapter.get_unit_nick(friend.user_id)}-{friend.comment[:15] + (friend.comment[15:] and '...')}"
    await matcher.finish(msg)


group_request_list = on_command(
    "群请求列表",
    aliases={"群请求", "加群请求", "群邀请列表", "加群请求列表", "群邀请"},
    block=True,
    permission=SUPERUSER,
)


@group_request_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            session: RequestSession = SessionDriveDepend(RequestSession),
            adapter: Adapter = AdapterDepend()):
    keys = [key for key in session.groups]
    keys.sort(reverse=True)
    size = 10
    count = len(keys)
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["暂时还没收到请求", "没有找到请求哟"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    msg = f"{arg.page}/{maxpage}"
    page_keys = keys[(arg.page - 1) * size:arg.page * size]
    for key in page_keys:
        group = session.groups[key]
        msg += f"\n{key if not group.is_oprate else '★'} | {await adapter.get_group_nick(group.group_id)}-{group.comment[:15] + (group.comment[15:] and '...')}"
    await matcher.finish(msg)


friend_request_apply = on_command(
    "通过好友请求",
    aliases={"通过好友邀请"},
    block=True,
    permission=SUPERUSER,
)


@friend_request_apply.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: IntArgMatch = ArgMatchDepend(IntArgMatch),
            session: RequestSession = SessionDriveDepend(RequestSession)):
    unit = session.friends.get(arg.num, None)
    if not unit:
        await matcher.finish("请求不存在")
    if unit.time - time() > 5 * 24 * 3600:
        await matcher.finish("请求已超时，操作已被禁止")
    if unit.is_oprate:
        await matcher.finish("请求曾被处理，操作失败")
    await bot.set_friend_add_request(flag=unit.flag, approve=True)
    async with session:
        unit.is_oprate = True
    await matcher.finish("已通过")


group_request_apply = on_command(
    "通过群请求",
    aliases={"通过拉群请求", "通过加群请求", "通过群邀请"},
    block=True,
    permission=SUPERUSER,
)


@group_request_apply.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: IntArgMatch = ArgMatchDepend(IntArgMatch),
            session: RequestSession = SessionDriveDepend(RequestSession)):
    unit = session.groups.get(arg.num, None)
    if not unit:
        await matcher.finish("请求不存在")
    if unit.time - time() > 5 * 24 * 3600:
        await matcher.finish("请求已超时，操作已被禁止")
    if unit.is_oprate:
        await matcher.finish("请求曾被处理，操作失败")
    await bot.set_group_add_request(flag=unit.flag,
                                    sub_type=unit.sub_type,
                                    approve=True)
    async with session:
        unit.is_oprate = True
    await matcher.finish("已通过")
