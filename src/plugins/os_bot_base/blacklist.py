"""
    黑名单服务
"""
import random
from time import time, localtime, strftime
from typing import Any, Dict, Union
from typing_extensions import Self
from dataclasses import dataclass, field
from nonebot import on_command, get_bots
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.adapters import Bot
from nonebot.adapters.onebot import v11
from nonebot.params import EventMessage
from nonebot.exception import IgnoredException, MockApiException
from nonebot.message import event_preprocessor
from .argmatch import ArgMatch, Field
from .config import config
from .session import Session, StoreSerializable
from .logger import logger
from .depends import SessionPluginDepend, ArgMatchDepend, OnebotCache, OBCacheDepend, Adapter, AdapterDepend
from .util import matcher_exception_try, only_command, get_plugin_session


@dataclass
class BanUnit(StoreSerializable):
    """
        封禁相关数据

        - `id` 封禁的ID
        - `ban_time` 封禁过期时间戳，为小于等于0时永久封禁
        - `oprate_log` 操作日志
        - `create_time` 创建时间
    """

    id: int = field(default=None)  # type: ignore
    ban_time: int = field(default=0)  # type: ignore
    oprate_log: str = field(default=None)  # type: ignore
    create_time: int = field(default_factory=(lambda: int(time())), init=False)

    def is_ban(self):
        if self.ban_time <= 0:
            return True
        return self.ban_time > time()

    def ban_time_str(self):
        time_str = "永久"
        if self.ban_time > 0:
            time_str = strftime('%Y-%m-%d %H:%M:%S', localtime(self.ban_time))
        return time_str


class BlackSession(Session):
    ban_user_list: Dict[int, BanUnit]
    ban_group_list: Dict[int, BanUnit]

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.ban_user_list = {}
        self.ban_group_list = {}

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)

        # 加载 ban_user_list
        tmp_list: Dict[str, Any] = self.ban_user_list  # type: ignore
        self.ban_user_list = {}
        for key in tmp_list:
            banunit = BanUnit._load_from_dict(tmp_list[key])  # type: ignore
            self.ban_user_list[int(key)] = banunit

        # 加载 ban_group_list
        tmp_list: Dict[str, Any] = self.ban_group_list  # type: ignore
        self.ban_group_list = {}
        for key in tmp_list:
            banunit = BanUnit._load_from_dict(tmp_list[key])  # type: ignore
            self.ban_group_list[int(key)] = banunit

        return self


ban_clear = on_command("清空黑名单列表",
                       block=True,
                       rule=only_command(),
                       permission=SUPERUSER)


@ban_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            session: BlackSession = SessionPluginDepend(BlackSession)):
    if not session.ban_group_list and not session.ban_user_list:
        await matcher.finish("黑名单列表就是空的哟")
    await matcher.pause(
        f">>警告，会同时清空群列表({len(session.ban_group_list)})与用户列表({len(session.ban_user_list)})<<"
    )


@ban_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            message: v11.Message = EventMessage(),
            session: BlackSession = SessionPluginDepend(BlackSession)):
    msg = str(message).strip()
    if msg == "确认清空":
        async with session:
            session.ban_group_list = {}
            session.ban_user_list = {}
        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["确认……失败。", "无法确认"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


class BanArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "封禁参数"
        des = "匹配封禁用户或群组，包含时间"

    unit_uuid: int = Field.Int("封禁对象",
                               min=9999,
                               max=99999999999,
                               require=False)

    ban_time: int = Field.RelateTime("封禁时间", default=0, require=False)

    def __init__(self) -> None:
        super().__init__([self.unit_uuid, self.ban_time])


ban_add = on_command(
    "封禁",
    aliases={"添加黑名单用户", "ban", "封禁用户", "添加黑名单"},
    block=True,
    permission=SUPERUSER,
)


@ban_add.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: BanArg = ArgMatchDepend(BanArg),
            cache: OnebotCache = OBCacheDepend(),
            adapter: Adapter = AdapterDepend(),
            session: BlackSession = SessionPluginDepend(BlackSession)):
    uid = arg.unit_uuid
    if not uid:
        await matcher.finish(f"要写用户账号哦！")
    if uid in config.superusers or str(uid) in config.superusers:
        await matcher.finish(f"超级用户无法封禁！")
    if uid in config.os_ob_black_user_list:
        await matcher.finish(f"此用户已被配置封禁！")
    if uid in session.ban_user_list and session.ban_user_list[uid].is_ban():
        await matcher.finish(
            f"用户{cache.get_unit_nick(uid)}已在封禁中，结束时间{session.ban_user_list[uid].ban_time_str()}"
        )
    ban_time = arg.ban_time + int(time()) if arg.ban_time > 0 else 0
    async with session:
        session.ban_user_list[uid] = BanUnit(
            id=uid,
            ban_time=ban_time,
            oprate_log=
            f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
        )
    await matcher.finish(
        f"好，{cache.get_unit_nick(uid)}被封禁至{session.ban_user_list[uid].ban_time_str()}！"
    )


ban_add_group = on_command(
    "群封禁",
    aliases={"添加黑名单组", "添加黑名单群组", "groupban", "封禁群"},
    block=True,
    permission=SUPERUSER,
)


@ban_add_group.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: BanArg = ArgMatchDepend(BanArg),
            cache: OnebotCache = OBCacheDepend(),
            adapter: Adapter = AdapterDepend(),
            session: BlackSession = SessionPluginDepend(BlackSession)):
    gid = arg.unit_uuid
    if not gid:
        await matcher.finish(f"要写群号哦！")
    if gid in config.os_ob_black_group_list:
        await matcher.finish(f"此群组已被配置封禁！")
    if gid in session.ban_group_list and session.ban_group_list[gid].is_ban():
        await matcher.finish(
            f"群{cache.get_group_nick(gid)}已在封禁中，直至{session.ban_group_list[gid].ban_time_str()}"
        )
    ban_time = arg.ban_time + int(time()) if arg.ban_time > 0 else 0
    async with session:
        session.ban_group_list[gid] = BanUnit(
            id=gid,
            ban_time=ban_time,
            oprate_log=
            f"{await adapter.mark(bot, event)}_{strftime('%Y-%m-%d %H:%M:%S')}"
        )
    await matcher.finish(
        f"OK！群{cache.get_group_nick(gid)}被封禁至{session.ban_group_list[gid].ban_time_str()}！"
    )


ban_del = on_command(
    "解禁",
    aliases={"解除封禁", "解封", "移除封禁", "解除封禁"},
    block=True,
    permission=SUPERUSER,
)


@ban_del.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: BanArg = ArgMatchDepend(BanArg),
            cache: OnebotCache = OBCacheDepend(),
            session: BlackSession = SessionPluginDepend(BlackSession)):
    uid = arg.unit_uuid
    if not uid:
        await matcher.finish(f"要写用户账号哦！")
    if uid in config.os_ob_black_user_list:
        await matcher.finish(f"此用户已被配置封禁！")
    if uid not in session.ban_user_list or not session.ban_user_list[
            uid].is_ban():
        await matcher.finish(f"用户{cache.get_unit_nick(uid)}不在封禁中哦")
    async with session:
        del session.ban_user_list[uid]
    await matcher.finish(f"{cache.get_unit_nick(uid)}，成功解封！")


ban_del_group = on_command(
    "群解禁",
    aliases={"移除黑名单组", "移除黑名单群组", "groupdeban", "解禁群", "群解封", "解封群"},
    block=True,
    permission=SUPERUSER,
)


@ban_del_group.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: BanArg = ArgMatchDepend(BanArg),
            cache: OnebotCache = OBCacheDepend(),
            session: BlackSession = SessionPluginDepend(BlackSession)):
    gid = arg.unit_uuid
    if not gid:
        await matcher.finish(f"要写群号哦！")
    if gid in config.os_ob_black_group_list:
        await matcher.finish(f"此群组已被配置封禁！")
    if gid not in session.ban_group_list or not session.ban_group_list[
            gid].is_ban():
        await matcher.finish(f"群{cache.get_group_nick(gid)}没有被封禁哦！")
    async with session:
        del session.ban_group_list[gid]
    await matcher.finish(f"好耶，群{cache.get_group_nick(gid)}被解禁啦。")


ban_list = on_command(
    "黑名单列表",
    aliases={"封禁列表", "查看黑名单列表", "打开黑名单列表", "查看封禁列表", "打开封禁列表"},
    block=True,
    permission=SUPERUSER,
    rule=only_command())


@ban_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            cache: OnebotCache = OBCacheDepend(),
            session: BlackSession = SessionPluginDepend(BlackSession)):
    ban_user_list = {
        f'{cache.get_unit_nick(uid)}({uid})-{session.ban_user_list[uid].ban_time_str()}'
        for uid in session.ban_user_list
        if session.ban_user_list[uid].is_ban()
    }
    ban_group_list = {
        f'{cache.get_group_nick(gid)}({gid})-{session.ban_group_list[gid].ban_time_str()}'
        for gid in session.ban_group_list
        if session.ban_group_list[gid].is_ban()
    }
    if not ban_user_list and not ban_group_list:
        await matcher.finish("黑名单列表是空的！")
    msg = f"封禁人：{'、'.join(ban_user_list)}"
    msg += f"\n封禁组：{'、'.join(ban_group_list)}"
    await matcher.finish(msg)


config_ban_list = on_command("系统黑名单列表",
                             aliases={"系统封禁列表"},
                             block=True,
                             permission=SUPERUSER,
                             rule=only_command())


@config_ban_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher, cache: OnebotCache = OBCacheDepend()):
    if not config.os_ob_black_user_list and not config.os_ob_black_group_list:
        await matcher.finish("系统黑名单列表是空的！")
    msg = "注：此列表为配置文件中的强制封禁名单。"
    msg += f"\n封禁人：{'、'.join({cache.get_unit_nick(uid) + '(' + str(uid) + ')' for uid in config.os_ob_black_user_list})}"
    msg += f"\n封禁组：{'、'.join({cache.get_group_nick(gid) + '(' + str(gid) + ')' for gid in config.os_ob_black_group_list})}"
    await matcher.finish(msg)


@event_preprocessor
async def _(event: Union[v11.PrivateMessageEvent,
                         v11.FriendRecallNoticeEvent]):
    if config.os_ob_black_eachother_private:
        if f"{event.user_id}" in get_bots():
            logger.debug(
                f"已禁止处理连接到此后端其它bot发送的私聊消息 - {event.user_id} [{event.self_id}]")
            raise IgnoredException("")


@event_preprocessor
async def _(event: Union[v11.GroupMessageEvent, v11.GroupRecallNoticeEvent,
                         v11.PokeNotifyEvent]):
    if config.os_ob_black_eachother_group:
        if f"{event.user_id}" in get_bots():
            logger.debug(
                f"已禁止处理连接到此后端其它bot发送的群消息 - {event.group_id} - {event.user_id} [{event.self_id}]"
            )
            raise IgnoredException("")


@event_preprocessor
async def _(bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            session: BlackSession = SessionPluginDepend(BlackSession)):
    if config.os_ob_black_tmp:
        if event.sub_type in ("group", "other"):
            logger.debug(f"已禁止处理临时消息 - {event.user_id} [{event.self_id}]")
            raise IgnoredException("")
    if await SUPERUSER(bot, event):
        return
    if event.user_id in config.os_ob_black_user_list:
        logger.debug(f"已禁止私聊中当前用户{event.user_id}的任何操作(配置)[{event.self_id}]")
        raise IgnoredException("")
    if event.user_id in session.ban_user_list and session.ban_user_list[
            event.user_id].is_ban():
        logger.debug(f"已禁止私聊中当前用户{event.user_id}的任何操作(动态)[{event.self_id}]")
        raise IgnoredException("")


@event_preprocessor
async def _(bot: v11.Bot,
            event: v11.GroupMessageEvent,
            session: BlackSession = SessionPluginDepend(BlackSession)):
    if config.os_ob_black_anonymous:
        if event.sub_type == "anonymous":
            logger.debug(
                f"已禁止处理匿名消息 - {event.group_id} - {event.user_id} [{event.self_id}]"
            )
            raise IgnoredException("")
    if event.group_id in config.os_ob_black_group_list:
        logger.debug(f"已禁止群组{event.group_id}的任何操作(配置)[{event.self_id}]")
        raise IgnoredException("")
    if event.group_id in session.ban_group_list and session.ban_group_list[
            event.group_id].is_ban():
        logger.debug(f"已禁止群组{event.group_id}的任何操作(动态)[{event.self_id}]")
        raise IgnoredException("")
    if await SUPERUSER(bot, event):
        return
    if event.user_id in config.os_ob_black_user_list:
        logger.debug(
            f"已禁止群组{event.group_id}中当前用户{event.user_id}的任何操作(配置)[{event.self_id}]"
        )
        raise IgnoredException("")
    if event.user_id in session.ban_user_list and session.ban_user_list[
            event.user_id].is_ban():
        logger.debug(
            f"已禁止群组{event.group_id}中当前用户{event.user_id}的任何操作(动态)[{event.self_id}]"
        )
        raise IgnoredException("")


@Bot.on_calling_api
async def _(bot: Bot, api: str, data: Dict[str, Any]):
    """
        API 请求前
    """
    if not isinstance(bot, v11.Bot):
        return
    ban_result = {
        "status": "500",
        "retcode": 500,
        "msg": "此用户或群组已被禁用（hook）",
        "wording": "此用户或群组已被禁用（hook）",
    }
    if data.get("group_id"):
        session: BlackSession = await get_plugin_session(
            BlackSession)  # type: ignore
        if data.get("group_id") in config.os_ob_black_group_list:
            logger.info("尝试发起对被封禁群聊的操作（配置） {} -> {} | {}",
                        data.get("group_id"), api, data)
            raise MockApiException(ban_result)
        safe_api = ('set_group_leave', 'get_group_info',
                    'get_group_member_info', 'get_group_member_list',
                    'get_group_honor_info')
        if api not in safe_api and data.get(
                "group_id") in session.ban_group_list:
            logger.info("尝试发起对被封禁群聊的操作（动态） {} -> {} | {}",
                        data.get("group_id"), api, data)
            raise MockApiException(ban_result)
    if data.get("user_id"):
        session: BlackSession = await get_plugin_session(
            BlackSession)  # type: ignore
        if data.get("user_id") in config.os_ob_black_user_list:
            logger.info("尝试发起对被封禁用户的操作（配置） {} -> {} | {}",
                        data.get("group_id"), api, data)
            raise MockApiException(ban_result)
        safe_api = ('set_group_kick')
        if api not in safe_api and data.get(
                "user_id") in session.ban_user_list:
            logger.info("尝试发起对被封禁用户的操作（动态） {} -> {} | {}",
                        data.get("group_id"), api, data)
            raise MockApiException(ban_result)
