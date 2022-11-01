"""
    依赖注入工具
"""
from typing import Any, Optional, Type
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.params import Depends
from nonebot.plugin import Plugin
from nonebot.typing import T_State
from nonebot.adapters.onebot import v11

from .session import SessionManage, Session as BaseSession
from .adapter import AdapterFactory, BaseAdapter
from .consts import META_SESSION_KEY, SESSION_SCOPE_PLUGIN, STATE_ARGMATCH_RESULT
from .cache.onebot import OnebotCache, BotRecord, GroupRecord, UnitRecord as UserRecord
from .argmatch import ArgMatch as ArgMatchCls


def __session_check(matcher: Matcher) -> bool:
    plugin: Optional[Plugin] = matcher.plugin
    return (not plugin or not plugin.metadata or not not plugin.metadata.extra
            or META_SESSION_KEY not in plugin.metadata.extra or not issubclass(
                plugin.metadata.extra[META_SESSION_KEY], BaseSession))


async def __session_get(mark: str, matcher: Matcher) -> Optional[BaseSession]:
    """
        获取基于插件`SessionType`的`Session`

        通过`mark`参数指定作用域
    """
    if not __session_check(matcher):
        return None
    assert matcher.plugin
    plugin: Plugin = matcher.plugin
    assert plugin.metadata
    SessionType: Type[BaseSession] = plugin.metadata.extra[META_SESSION_KEY]
    sm = SessionManage.get_instance()
    domain = SessionType.domain() or plugin.name
    return await sm.get(mark, domain, SessionType)


def Session(SessionType: Type[BaseSession] = BaseSession) -> Any:
    """
        获取当前事件`session`，组粒度。
    """

    async def _depend(bot: Bot, matcher: Matcher,
                      event: Event) -> "SessionType":
        adapter = AdapterFactory.get_adapter(bot)
        return await __session_get(await adapter.mark_group(bot, event),
                                   matcher)  # type: ignore

    return Depends(_depend)


def SessionUnit() -> Any:
    """
        获取当前事件`session`，源粒度。
    """

    async def _depend(bot: Bot, matcher: Matcher, event: Event) -> Any:
        adapter = AdapterFactory.get_adapter(bot)
        return await __session_get(await adapter.mark(bot, event), matcher)

    return Depends(_depend)


def SessionDrive() -> Any:
    """
        获取当前适配器`session`。
    """

    async def _depend(bot: Bot, matcher: Matcher, event: Event) -> Any:
        adapter = AdapterFactory.get_adapter(bot)
        return await __session_get(await adapter.mark_drive(bot, event),
                                   matcher)

    return Depends(_depend)


def SessionPlugin() -> Any:
    """
        获取当前插件`session`
    """

    async def _depend(bot: Bot, matcher: Matcher, event: Event) -> Any:
        adapter = AdapterFactory.get_adapter(bot)
        return await __session_get(SESSION_SCOPE_PLUGIN, matcher)

    return Depends(_depend)


def Adapter() -> Any:
    """
        获取BB插件的适配器
    """

    async def _depend(bot: Bot) -> BaseAdapter:
        return AdapterFactory.get_adapter(bot)

    return Depends(_depend)


def OBCache() -> Any:
    """
        获取缓存实例
    """

    async def _depend() -> OnebotCache:
        return OnebotCache.get_instance()

    return Depends(_depend)


def OBCacheBot() -> Any:
    """
        获取缓存实例
    """

    async def _depend(bot: v11.Bot) -> Optional[BotRecord]:
        cache = OnebotCache.get_instance()
        return cache.get_bot_record(int(bot.self_id))

    return Depends(_depend)


def OBCacheOBGroup() -> Any:
    """
        获取缓存实例
    """

    async def _depend(bot: v11.Bot,
                      event: "v11.GroupMessageEvent") -> Optional[GroupRecord]:
        cache = OnebotCache.get_instance()
        bot_record = cache.get_bot_record(int(bot.self_id))
        if not bot_record:
            return
        return bot_record.get_group_record(event.group_id)

    return Depends(_depend)


def OBCacheGroupUser() -> Any:
    """
        获取群缓存实例
    """

    async def _depend(bot: v11.Bot,
                      event: "v11.GroupMessageEvent") -> Optional[UserRecord]:
        cache = OnebotCache.get_instance()
        bot_record = cache.get_bot_record(int(bot.self_id))
        if not bot_record:
            return
        group_record = bot_record.get_group_record(event.group_id)
        if not group_record:
            return
        return group_record.get_user_record(event.user_id)

    return Depends(_depend)


def OBCachePrivateUser() -> Any:
    """
        获取好友缓存实例
    """

    async def _depend(bot: v11.Bot,
                      event: v11.PrivateMessageEvent) -> Optional[UserRecord]:
        cache = OnebotCache.get_instance()
        bot_record = cache.get_bot_record(int(bot.self_id))
        if not bot_record:
            return
        return bot_record.get_friend_record(event.user_id)

    return Depends(_depend)


def OBCacheGlobalGroup() -> Any:
    """
        获取缓存实例
    """

    async def _depend(event: v11.GroupMessageEvent) -> Optional[GroupRecord]:
        cache = OnebotCache.get_instance()
        return cache.get_group_record(event.group_id)

    return Depends(_depend)


def OBCacheGlobalGroupUser() -> Any:
    """
        获取全局群缓存实例
    """

    async def _depend(event: v11.GroupMessageEvent) -> Optional[UserRecord]:
        cache = OnebotCache.get_instance()
        group_record = cache.get_group_record(event.group_id)
        if not group_record:
            return
        return group_record.get_user_record(event.user_id)

    return Depends(_depend)


def OBCacheGlobalUser() -> Any:
    """
        获取全局用户缓存实例
    """

    async def _depend(event: v11.PrivateMessageEvent) -> Optional[UserRecord]:
        cache = OnebotCache.get_instance()
        return cache.get_unit_record(event.user_id)

    return Depends(_depend)


def ArgMatch() -> Any:
    """
        获取参数解析器实例
    """

    async def _depend(state: T_State) -> Optional[ArgMatchCls]:
        return state.get(STATE_ARGMATCH_RESULT)  # type: ignore

    return Depends(_depend)
