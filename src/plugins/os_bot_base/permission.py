"""
    # 简要权限服务（侵入式）

    支持两种方向的授权模式，默认禁用时的授权，以及默认授权时的禁用。



    对应的指令：

    - 授权 权限名
    - 禁用权限 权限名
    - 权限操作 [驱动] 组标识 组ID 对象ID 权限名 [授权时间]
"""
import math
import random
from time import time, localtime, strftime
from typing import Any, Dict, Optional
from typing_extensions import Self
from dataclasses import dataclass, field
from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER, Permission
from nonebot.rule import Rule
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, PRIVATE_FRIEND, GROUP_MEMBER
from nonebot.params import EventMessage

from .util.rule import only_command
from .argmatch import ArgMatch, Field, PageArgMatch
from .session import Session, StoreSerializable
from .logger import logger
from .depends import ArgMatchDepend, Adapter, AdapterDepend, AdapterFactory
from .util import matcher_exception_try, get_plugin_session, seconds_to_dhms
from .exception import PermissionError


@dataclass
class PermUnit(StoreSerializable):
    """
        授权相关数据

        - `mark` 授权掩码 用于标识授权对象
        - `name` 权限名
        - `method` 授权方式（组、组成员、私聊）
        - `drive_type` 驱动标识
        - `is_group` 是否是群组
        - `group_id` 授权组id
        - `unit_id` 授权对象id（可空）
        - `auth` 是否授权
        - `expire_time` 授权过期时间戳，为小于等于0时永久有效
        - `oprate_log` 操作日志
        - `create_time` 创建时间
    """

    mask: str = field(default=None)  # type: ignore
    name: str = field(default=None)  # type: ignore
    drive_type: str = field(default=None)  # type: ignore
    is_group: bool = field(default=None)  # type: ignore
    group_id: str = field(default=None)  # type: ignore
    unit_id: str = field(default=None)  # type: ignore
    auth: bool = field(default=False)  # type: ignore
    expire_time: int = field(default=None)  # type: ignore
    oprate_log: str = field(default=None)  # type: ignore
    create_time: int = field(default_factory=(lambda: int(time())), init=False)

    def is_valid(self) -> bool:
        if self.expire_time <= 0:
            return True
        return self.expire_time > time()

    def expire_time_str(self):
        time_str = "永久"
        if self.expire_time > 0:
            time_str = strftime('%Y-%m-%d %H:%M:%S',
                                localtime(self.expire_time))
        return time_str

    def is_auth(self):
        return self.auth


class PermissionSession(Session):
    premissions: Dict[str, Dict[str, PermUnit]]
    """
        授权列表

        组标识->权限名->权限Unit
    """
    premissions_group_member: Dict[str, Dict[str, Dict[str, PermUnit]]]
    """
        组成员专用授权列表（限群聊）

        组标识->用户标识->权限名->权限Unit
    """

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.premissions = {}
        self.premissions_group_member = {}

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)

        # 加载 premissions
        self.premissions = {
            k: {
                k1: PermUnit._load_from_dict(v1)  # type: ignore
                for k1, v1 in v.items()
            }
            for k, v in self.premissions.items()
        }

        # 加载 ban_group_list
        self.premissions_group_member = {
            k: {
                k1: {
                    k2: PermUnit._load_from_dict(v2)  # type: ignore
                    for k2, v2 in v1.items()
                }
                for k1, v1 in v.items()
            }
            for k, v in self.premissions_group_member.items()
        }

        return self


@dataclass
class PermMeta:
    """
        权限元数据

        - `name` 名称
        - `des` 描述
        - `auth` 默认授权？
        - `for_group_member` 细化到群成员？
        - `only_super_oprate` 仅允许超级管理员操作？
    """
    name: str
    des: str
    auth: bool
    for_group_member: bool
    only_super_oprate: bool
    ignore_super: bool


class PermManage:
    """
        权限管理器

        提供权限的认证与管理、查询等功能

        注意，在使用权限管理前需要注册权限，该过程建议在启动完成前完成。
    """
    PERMISSIONS: Dict[str, PermMeta] = {}

    @classmethod
    def register(cls,
                 name: str,
                 des: str,
                 auth: bool = False,
                 for_group_member=False,
                 only_super_oprate=True,
                 ignore_super: bool = False):
        """
            - `name` 权限名
            - `des` 权限描述
            - `auth` 默认授权状态，默认否
            - `for_group_member` 作用与群组成员，默认否
            - `only_super_oprate` 仅允许超级管理员操作
        """
        cls.PERMISSIONS[name] = PermMeta(name, des, auth, for_group_member,
                                         only_super_oprate, ignore_super)

    @classmethod
    async def check_permission_from_mark(cls,
                                         name: str,
                                         adapter_type: str,
                                         group_id: str,
                                         unit_id: str = "",
                                         is_group: bool = True):
        """
            权限检查

            检查指定事件主体是否拥有指定权限

            注意：不会检查超级管理员权限
        """
        if name not in cls.PERMISSIONS:
            raise PermissionError(f"权限`{name}`未注册")
        meta = cls.PERMISSIONS[name]

        session: PermissionSession = await get_plugin_session(PermissionSession
                                                              )

        mark_group = f"{adapter_type}-{'G' if is_group else 'P'}-{group_id}"
        mark_unit = unit_id

        if meta.for_group_member:
            unit = session.premissions_group_member.get(mark_group, {}).get(
                mark_unit, {}).get(name, None)
        else:
            unit = session.premissions.get(mark_group, {}).get(name, None)

        if not unit or not unit.is_valid():
            return meta.auth

        return unit.is_auth()

    @classmethod
    async def check_permission(cls,
                               name: str,
                               bot: Bot,
                               event: Event,
                               ignore_super: bool = False):
        """
            权限检查

            检查指定事件主体是否拥有指定权限

            当事件主体为超级管理员时默认为True
        """
        if name not in cls.PERMISSIONS:
            raise PermissionError(f"权限`{name}`未注册")
        meta = cls.PERMISSIONS[name]

        if not ignore_super and not meta.ignore_super and await SUPERUSER(
                bot, event):
            return True

        session: PermissionSession = await get_plugin_session(PermissionSession
                                                              )
        adapter = AdapterFactory.get_adapter(bot)
        is_group = await adapter.msg_is_multi_group(bot, event)
        group_id = f"{await adapter.get_group_id_from_event(bot, event)}"
        unit_id = f"{await adapter.get_unit_id_from_event(bot, event)}"

        return await cls.check_permission_from_mark(name, adapter.get_type(),
                                                    group_id, unit_id,
                                                    is_group)

    @classmethod
    async def get_mask(cls, bot: Bot, event: Event) -> str:
        adapter = AdapterFactory.get_adapter(bot)
        is_group = await adapter.msg_is_multi_group(bot, event)
        group_id = f"{await adapter.get_group_id_from_event(bot, event)}"
        unit_id = f"{await adapter.get_unit_id_from_event(bot, event)}"
        return f"{adapter.get_type()}-{'G' if is_group else 'P'}-{group_id}-{unit_id}"

    @classmethod
    async def get_group_mask(cls, bot: Bot, event: Event) -> str:
        adapter = AdapterFactory.get_adapter(bot)
        is_group = await adapter.msg_is_multi_group(bot, event)
        group_id = f"{await adapter.get_group_id_from_event(bot, event)}"
        return f"{adapter.get_type()}-{'G' if is_group else 'P'}-{group_id}"

    @classmethod
    async def auth(cls,
                   name: str,
                   drive_type: str,
                   is_group: bool,
                   group_id: str,
                   unit_id: str,
                   oprate_log: str,
                   expire_time: int = 0,
                   auth=True) -> PermUnit:
        if name not in cls.PERMISSIONS:
            raise PermissionError(f"权限`{name}`未注册")
        session: PermissionSession = await get_plugin_session(PermissionSession
                                                              )
        meta = cls.PERMISSIONS[name]
        unit = PermUnit()
        unit.name = name
        unit.drive_type = drive_type
        unit.is_group = is_group
        unit.mask = f"{drive_type}-{'G' if is_group else 'P'}-{group_id}-{unit_id}"
        unit.group_id = group_id
        unit.unit_id = unit_id
        unit.auth = auth
        unit.oprate_log = oprate_log
        unit.expire_time = expire_time

        mark_group = f"{drive_type}-{'G' if is_group else 'P'}-{group_id}"
        mark_unit = unit_id

        async with session:
            if meta.for_group_member:
                if mark_group not in session.premissions_group_member:
                    session.premissions_group_member[mark_group] = {}
                if mark_unit not in session.premissions_group_member[
                        mark_group]:
                    session.premissions_group_member[mark_group][
                        mark_unit] = {}
                session.premissions_group_member[mark_group][mark_unit][
                    name] = unit
            else:
                if mark_group not in session.premissions:
                    session.premissions[mark_group] = {}
                session.premissions[mark_group][name] = unit

        return unit

    @classmethod
    async def reset_perm(cls, drive_type: str, is_group: bool, group_id: str):
        """重置当前组权限"""
        session: PermissionSession = await get_plugin_session(PermissionSession
                                                              )
        mark_group = f"{drive_type}-{'G' if is_group else 'P'}-{group_id}"
        async with session:
            if mark_group in session.premissions_group_member:
                del session.premissions_group_member[mark_group]
            if mark_group in session.premissions:
                del session.premissions[mark_group]

    @classmethod
    async def reset_perm_all(cls, name: str):
        """重置所有权限到默认值（危险操作）"""
        if name not in cls.PERMISSIONS:
            raise PermissionError(f"权限`{name}`未注册")
        session: PermissionSession = await get_plugin_session(PermissionSession
                                                              )
        async with session:
            # 移除该权限所有权限配置
            for mark_groups in session.premissions_group_member.values():
                for mark_units in mark_groups.values():
                    if name in mark_units:
                        del mark_units[name]

            for mark_groups in session.premissions.values():
                if name in mark_groups:
                    del mark_groups[name]

    @classmethod
    async def is_register(cls, name: str) -> bool:
        return name in cls.PERMISSIONS

    @classmethod
    async def get_register(cls, name: str) -> Optional[PermMeta]:
        return cls.PERMISSIONS.get(name, None)


def perm_check_rule(name: str):
    """
        参数为权限名
    """

    async def checker(bot: Bot, event: Event) -> bool:
        return await PermManage.check_permission(name, bot, event)

    return Rule(checker)


def perm_check_permission(name: str):
    """
        参数为权限名
    """

    async def checker(bot: Bot, event: Event) -> bool:
        return await PermManage.check_permission(name, bot, event)

    return Permission(checker)


class PermissionOprateArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "权限参数"
        des = "管理权限"

    drive_type: str = Field.Keys("驱动", {
        "ob11": ["onebot11", "gocqhttp"],
    },
                                 default="ob11",
                                 require=False,
                                 ignoreCase=True)

    is_group: bool = Field.Keys("组标识", {
        True: ["g", "group", "组", "群", "群聊"],
        False: ["p", "private", "私聊", "好友", "私"],
    },
                                ignoreCase=True)
    group_id: int = Field.Int("组ID", min=9999, max=99999999999)

    unit_id: int = Field.Int("成员ID", min=9999, max=99999999999)

    name: str = Field.Keys(
        "权限名",
        keys_generate=lambda: {item: item
                               for item in PermManage.PERMISSIONS})

    auth: bool = Field.Bool("是否授权")

    auth_time: int = Field.RelateTime("授权时间", default=0)

    def __init__(self) -> None:
        super().__init__([
            self.drive_type, self.is_group, self.group_id, self.unit_id,
            self.name, self.auth, self.auth_time
        ])


perm_oprate = on_command(
    "权限操作",
    aliases={"权限控制", "授权控制", "定向权限控制"},
    block=True,
    permission=SUPERUSER,
)


@perm_oprate.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: PermissionOprateArg = ArgMatchDepend(PermissionOprateArg),
            adapter: Adapter = AdapterDepend()):
    meta = await PermManage.get_register(arg.name)
    if not meta:
        await matcher.finish(f"权限`{arg.name}`不存在！")

    unit = await PermManage.auth(
        arg.name,
        arg.drive_type,
        arg.is_group,
        f"{arg.group_id}",
        f"{arg.unit_id}",
        oprate_log=
        f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}",
        expire_time=0 if not arg.auth_time else int(time()) + arg.auth_time,
        auth=arg.auth)

    if arg.is_group:
        if meta.for_group_member:
            await matcher.finish(
                f"已为群 {await adapter.get_group_nick(arg.group_id)}({arg.group_id}) 的"
                f"{await adapter.get_unit_nick(arg.unit_id)}({arg.unit_id}) "
                f"{'授予' if unit.auth else '禁用'}权限`{arg.name}`，期限 {unit.expire_time_str()}"
            )
        else:
            await matcher.finish(
                f"已为群 {await adapter.get_group_nick(arg.group_id)}({arg.group_id})"
                f"{'授予' if unit.auth else '禁用'}权限`{arg.name}`，期限 {unit.expire_time_str()}"
            )
    else:
        await matcher.finish(
            f"已为 {await adapter.get_unit_nick(arg.unit_id)}({arg.unit_id}) "
            f"{'授予' if unit.auth else '禁用'}权限`{arg.name}`，期限 {unit.expire_time_str()}"
        )


class PermissionGroupArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "权限参数"
        des = "管理权限"

    name: str = Field.Keys(
        "权限名",
        keys_generate=lambda: {item: item
                               for item in PermManage.PERMISSIONS})

    unit_id: int = Field.Int("成员ID", min=9999, max=99999999999, require=False)

    auth_time: int = Field.RelateTime("授权时间", default=0)

    def __init__(self) -> None:
        super().__init__([self.name, self.unit_id, self.auth_time])


class PermissionPrivateArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "权限参数"
        des = "管理权限"

    name: str = Field.Keys(
        "权限名",
        keys_generate=lambda: {item: item
                               for item in PermManage.PERMISSIONS})

    auth_time: int = Field.RelateTime("授权时间", default=0)

    def __init__(self) -> None:
        super().__init__([self.name, self.auth_time])


perm_auth = on_command(
    "权限授予",
    aliases={"权限发放", "授权", "启用权限"},
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER | PRIVATE_FRIEND,
)


@perm_auth.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: PermissionPrivateArg = ArgMatchDepend(PermissionPrivateArg)):
    meta = await PermManage.get_register(arg.name)
    if not meta:
        await matcher.finish(f"权限`{arg.name}`不存在！")
    if meta.auth and await PermManage.check_permission(
            arg.name, bot, event, ignore_super=True):
        await matcher.finish(f"权限`{arg.name}`已默认授权")
    if meta.only_super_oprate and not await SUPERUSER(bot, event):
        await matcher.finish(f"权限`{arg.name}`仅允许超级管理员设定")

    await PermManage.auth(
        arg.name,
        adapter.get_type(),
        False,
        f"{await adapter.get_group_id_from_event(bot, event)}",
        f"{await adapter.get_unit_id_from_event(bot, event)}",
        oprate_log=
        f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}",
        expire_time=0 if not arg.auth_time else int(time()) + arg.auth_time,
        auth=True)
    if arg.auth_time == 0:
        await matcher.finish(f"`{arg.name}`已授权")
    await matcher.finish(
        f"`{arg.name}`成功授权，有效期{seconds_to_dhms(arg.auth_time, compact=True)}。")


@perm_auth.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: PermissionGroupArg = ArgMatchDepend(PermissionGroupArg)):
    meta = await PermManage.get_register(arg.name)
    if not meta:
        await matcher.finish(f"权限`{arg.name}`不存在！")
    if meta.auth and await PermManage.check_permission(
            arg.name, bot, event, ignore_super=True):
        await matcher.finish(f"权限`{arg.name}`已默认授权")
    if meta.only_super_oprate and not await SUPERUSER(bot, event):
        await matcher.finish(f"权限`{arg.name}`仅允许超级管理员设定")
    if meta.for_group_member and not arg.unit_id:
        await matcher.finish(f"权限`{arg.name}`需要指定授权对象")
    if not meta.for_group_member and arg.unit_id:
        await matcher.finish(f"权限`{arg.name}`无法指定授权对象")

    await PermManage.auth(
        arg.name,
        adapter.get_type(),
        True,
        f"{await adapter.get_group_id_from_event(bot, event)}",
        f"{arg.unit_id if meta.for_group_member else await adapter.get_unit_id_from_event(bot, event)}",
        oprate_log=
        f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}",
        expire_time=0 if not arg.auth_time else int(time()) + arg.auth_time,
        auth=True)

    if meta.for_group_member:
        if arg.auth_time == 0:
            await matcher.finish(
                f"`{arg.name}`已永久授权 {await adapter.get_unit_nick(arg.unit_id, group_id=event.group_id)}({arg.unit_id})"
            )
        await matcher.finish(
            f"`{arg.name}`已授权 {await adapter.get_unit_nick(arg.unit_id, group_id=event.group_id)}({arg.unit_id}) 有效期{seconds_to_dhms(arg.auth_time, compact=True)}"
        )

    if arg.auth_time == 0:
        await matcher.finish(f"`{arg.name}`授权成功")
    await matcher.finish(
        f"`{arg.name}`授权有效期{seconds_to_dhms(arg.auth_time, compact=True)}")


perm_auth_rm = on_command(
    "权限收回",
    aliases={"收回权限", "取消授权", "取消权限", "权限禁用", "禁用权限", "禁用授权"},
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER | PRIVATE_FRIEND,
)


@perm_auth_rm.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: PermissionPrivateArg = ArgMatchDepend(PermissionPrivateArg)):
    meta = await PermManage.get_register(arg.name)
    if not meta:
        await matcher.finish(f"权限`{arg.name}`不存在！")
    if not meta.auth and not await PermManage.check_permission(
            arg.name, bot, event, ignore_super=True):
        await matcher.finish(f"权限`{arg.name}`已默认禁用")
    if meta.only_super_oprate and not await SUPERUSER(bot, event):
        await matcher.finish(f"权限`{arg.name}`仅允许超级管理员设定")

    await PermManage.auth(
        arg.name,
        adapter.get_type(),
        False,
        f"{await adapter.get_group_id_from_event(bot, event)}",
        f"{await adapter.get_unit_id_from_event(bot, event)}",
        oprate_log=
        f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}",
        expire_time=0 if not arg.auth_time else int(time()) + arg.auth_time,
        auth=False)
    if arg.auth_time == 0:
        await matcher.finish(f"`{arg.name}`权限禁用成功")
    await matcher.finish(
        f"`{arg.name}`禁用至{seconds_to_dhms(arg.auth_time, compact=True)}。")


@perm_auth_rm.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: PermissionGroupArg = ArgMatchDepend(PermissionGroupArg)):
    meta = await PermManage.get_register(arg.name)
    if not meta:
        await matcher.finish(f"权限`{arg.name}`不存在！")
    if not meta.auth and not await PermManage.check_permission(
            arg.name, bot, event, ignore_super=True):
        await matcher.finish(f"权限`{arg.name}`已默认禁用")
    if meta.only_super_oprate and not await SUPERUSER(bot, event):
        await matcher.finish(f"权限`{arg.name}`仅允许超级管理员设定")
    if meta.for_group_member and not arg.unit_id:
        await matcher.finish(f"权限`{arg.name}`需要指定禁用对象")
    if not meta.for_group_member and arg.unit_id:
        await matcher.finish(f"权限`{arg.name}`无法指定禁用对象")

    await PermManage.auth(
        arg.name,
        adapter.get_type(),
        True,
        f"{await adapter.get_group_id_from_event(bot, event)}",
        f"{arg.unit_id if meta.for_group_member else await adapter.get_unit_id_from_event(bot, event)}",
        oprate_log=
        f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}",
        expire_time=0 if not arg.auth_time else int(time()) + arg.auth_time,
        auth=False)

    if meta.for_group_member:
        if arg.auth_time == 0:
            await matcher.finish(
                f"`{arg.name}`已永久禁用 {await adapter.get_unit_nick(arg.unit_id, group_id=event.group_id)}({arg.unit_id})"
            )
        await matcher.finish(
            f"`{arg.name}`已对 {await adapter.get_unit_nick(arg.unit_id, group_id=event.group_id)}({arg.unit_id}) 禁用 {seconds_to_dhms(arg.auth_time, compact=True)}"
        )

    if arg.auth_time == 0:
        await matcher.finish(f"`{arg.name}`禁用成功")
    await matcher.finish(
        f"`{arg.name}`已禁用至{seconds_to_dhms(arg.auth_time, compact=True)}")


perm_list = on_command(
    "权限列表",
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER | PRIVATE_FRIEND
    | GROUP_MEMBER,
)


@perm_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    size = 10
    perms = [v for v in PermManage.PERMISSIONS.values()]
    count = len(perms)
    maxpage = math.ceil(count / size)

    if count == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    is_super = await SUPERUSER(bot, event)

    msg = f"{arg.page}/{maxpage}"
    for item in perms:
        if item.only_super_oprate and not is_super:
            continue
        auth = await PermManage.check_permission(item.name,
                                                 bot,
                                                 event,
                                                 ignore_super=True)
        msg += f"\n{'' if item.for_group_member else '群 '}{item.name}[{'√' if auth else 'X'}] - {item.des or '没有描述'}"
    await matcher.finish(msg)


class AtPageArgMatch(ArgMatch):

    unit_id: int = Field.Int("ID", min=9999, max=99999999999)

    page: int = Field.Int("页数", min=1, default=1, help="页码，大于等于1。")

    def __init__(self) -> None:
        super().__init__([AtPageArgMatch.unit_id, AtPageArgMatch.page])


user_perm_list = on_command(
    "用户权限列表",
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
)


@user_perm_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: AtPageArgMatch = ArgMatchDepend(AtPageArgMatch)):
    size = 10
    perms = [v for v in PermManage.PERMISSIONS.values()]
    count = len(perms)
    maxpage = math.ceil(count / size)

    if count == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    is_super = await SUPERUSER(bot, event)

    msg = f"{arg.page}/{maxpage}"
    for item in perms:
        if item.only_super_oprate and not is_super:
            continue
        auth = await PermManage.check_permission_from_mark(
            item.name, adapter.get_type(), str(event.group_id),
            str(arg.unit_id))
        msg += f"\n{'' if item.for_group_member else '群 '}{item.name}[{'√' if auth else 'X'}] - {item.des or '没有描述'}"
    await matcher.finish(msg)


perm_reset = on_command(
    "重置权限",
    block=True,
    rule=only_command(),
    permission=SUPERUSER,
)


@perm_reset.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend()):
    finish_msgs = ["请发送`确认重置`确认~", "通过`确认重置`继续操作哦"]
    await matcher.pause(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


@perm_reset.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            message: v11.Message = EventMessage(),
            adapter: Adapter = AdapterDepend()):
    msg = str(message).strip()
    if msg == "确认重置":
        await PermManage.reset_perm(
            adapter.get_type(), await adapter.msg_is_multi_group(bot, event),
            str(await adapter.get_group_id_from_event(bot, event)))
        finish_msgs = ["已重置！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["未确认操作", "pass"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])
