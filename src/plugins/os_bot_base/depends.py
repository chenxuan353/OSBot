"""
    依赖注入工具
"""
from typing import Any, Optional, Type
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event, Message
from nonebot.params import Depends, CommandArg
from nonebot.plugin import Plugin, PluginMetadata
from nonebot.adapters.onebot import v11

from .session import SessionManage, Session
from .adapter import AdapterFactory, Adapter
from .consts import META_SESSION_KEY, SESSION_SCOPE_PLUGIN
from .cache.onebot import OnebotCache, BotRecord, GroupRecord, UnitRecord as UserRecord
from .argmatch import ArgMatch
from .argmatch.exception import MatchError, FieldMatchError
from .exception import DependException
from .logger import logger


def __session_check(matcher: Matcher) -> bool:
    plugin: Optional[Plugin] = matcher.plugin
    return (not plugin or not plugin.metadata or not not plugin.metadata.extra
            or META_SESSION_KEY not in plugin.metadata.extra or
            not issubclass(plugin.metadata.extra[META_SESSION_KEY], Session))


async def get_session(mark: str, SessionType: Type[Session],
                      plugin_name: str) -> Session:
    """
        获取基于插件`SessionType`的`Session`

        通过`mark`参数指定作用域
    """
    sm = SessionManage.get_instance()
    domain = SessionType.domain() or plugin_name
    return await sm.get(mark, domain, SessionType)


async def __session_get(mark: str, matcher: Matcher,
                        SessionType: Optional[Type[Session]]) -> Session:
    """
        获取基于插件`SessionType`的`Session`

        通过`mark`参数指定作用域
    """
    if not __session_check(matcher):
        return None  # type: ignore
    assert matcher.plugin
    plugin: Plugin = matcher.plugin
    assert plugin.metadata
    if not SessionType:
        SessionType = plugin.metadata.extra.get(META_SESSION_KEY)
        if not SessionType:
            raise DependException("缺少`Session`定义，请检查是否提供此资源。")
    sm = SessionManage.get_instance()
    domain = SessionType.domain() or plugin.name
    return await sm.get(mark, domain, SessionType)


async def get_session_depend(matcher: Matcher, bot: Bot, event: Event,
                             SessionType: Type[Session]):
    adapter = AdapterFactory.get_adapter(bot)
    return await __session_get(
        await adapter.mark_group_without_drive(bot, event), matcher,
        SessionType)


def SessionDepend(SessionType: Optional[Type[Session]] = None) -> Any:
    """
        获取当前事件`session`，组粒度。
    """

    async def _depend(bot: Bot, matcher: Matcher, event: Event):
        adapter = AdapterFactory.get_adapter(bot)
        return await __session_get(
            await adapter.mark_group_without_drive(bot, event), matcher,
            SessionType)

    return Depends(_depend)


def SessionUnitDepend(SessionType: Optional[Type[Session]] = None) -> Any:
    """
        获取当前事件`session`，源粒度。
    """

    async def _depend(bot: Bot, matcher: Matcher, event: Event) -> Any:
        adapter = AdapterFactory.get_adapter(bot)
        return await __session_get(
            await adapter.mark_without_drive(bot, event), matcher, SessionType)

    return Depends(_depend)


def SessionDriveDepend(SessionType: Type[Session]) -> Any:
    """
        获取当前适配器`session`。
    """

    async def _depend(bot: Bot, matcher: Matcher, event: Event) -> Any:
        adapter = AdapterFactory.get_adapter(bot)
        return await __session_get(await adapter.mark_drive(bot, event),
                                   matcher, SessionType)

    return Depends(_depend)


async def get_plugin_session(SessionType: Type[Session]) -> Any:
    sm = SessionManage.get_instance()
    domain = SessionType.domain() or SessionType.__module__
    return await sm.get(SESSION_SCOPE_PLUGIN, domain, SessionType)


def SessionPluginDepend(SessionType: Type[Session]) -> Any:
    """
        获取当前插件`session`
    """

    async def _depend() -> Any:
        return await get_plugin_session(SessionType)

    return Depends(_depend)


def AdapterDepend() -> Any:
    """
        获取BB插件的适配器
    """

    async def _depend(bot: Bot) -> Adapter:
        return AdapterFactory.get_adapter(bot)

    return Depends(_depend)


def OBCacheDepend() -> Any:
    """
        获取缓存实例
    """

    async def _depend() -> OnebotCache:
        return OnebotCache.get_instance()

    return Depends(_depend)


def ArgMatchDepend(ArgMatchChild: Type[ArgMatch]) -> Any:
    """
        获取参数解析器实例
    """

    async def _depend(
        matcher: Matcher,
        bot: Bot,
        event: Event,
        message: Message = CommandArg()) -> ArgMatchChild:
        if not issubclass(ArgMatchChild, ArgMatch):
            raise MatchError(
                f"解析参数时发现问题，解析器`{ArgMatchChild.__name__}`未继承`ArgMatch`类")
        try:
            argmatch_ins = ArgMatchChild()  # type: ignore
        except Exception as e:
            logger.warning(
                f"解析参数时异常，实例化参数解析器`{ArgMatchChild.__name__}`时错误，可能的原因：未覆写init方法。"
            )
            raise e
        # 进行消息转换
        msg_str = ArgMatch.message_to_str(message)
        try:
            argmatch_ins(msg_str)
        except FieldMatchError as e:
            logger.debug(
                f"解析参数不成功，{e.msg} 源 [{bot.self_id}-{event.get_session_id()}] - {event.get_plaintext()}"
            )
            await matcher.finish(f"{e.msg}")
        except Exception as e:
            logger.warning(
                f"解析参数时异常，参数解析器解析错误 [{bot.self_id}-{event.get_session_id()}] - {event.get_plaintext()}"
            )
            raise e
        return argmatch_ins  # type: ignore

    return Depends(_depend)
