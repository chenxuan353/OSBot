"""
    文本解析器
"""
from typing import Union
from nonebot.message import run_preprocessor
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot.adapters import Bot
from nonebot.adapters.onebot import v11, v12
from nonebot.exception import IgnoredException
from nonebot.params import CommandArg

from .exception import MatchError, ValidationError, RequireMatchError, FieldMatchError
from .field import Field
from .argmatch import ArgMatch
from ..logger import logger
from ..consts import STATE_ARGMATCH, STATE_ARGMATCH_RESULT


class PageArgMatch(ArgMatch):

    page: int = Field.Int("页数", min=1, default=1,
                          help="页码，大于等于1。")  # type: ignore

    def __init__(self) -> None:
        super().__init__([PageArgMatch.page])  # type: ignore


class IntArgMatch(ArgMatch):

    num: int = Field.Int("整数", help="任意整数")  # type: ignore

    def __init__(self) -> None:
        super().__init__([PageArgMatch.num])  # type: ignore


@run_preprocessor
async def __run_preprocessor(matcher: Matcher,
                             bot: Bot,
                             event: v11.MessageEvent,
                             state: T_State,
                             message: "v11.Message" = CommandArg()):
    argmatch = matcher.state.get(STATE_ARGMATCH)
    if not argmatch:
        return
    if not issubclass(argmatch, ArgMatch):
        logger.warning(f"解析参数时发现问题，解析器`{argmatch.__name__}`未继承`ArgMatch`类")
        return
    try:
        argmatch_ins = argmatch()  # type: ignore
    except Exception as e:
        logger.warning(
            f"解析参数时异常，实例化参数解析器`{argmatch.__name__}`时错误，可能的原因：未覆写init方法。")
        raise e
    try:
        argmatch_ins(message.extract_plain_text())
    except FieldMatchError as e:
        logger.debug(
            f"解析参数不成功，{e.msg} 源 [{bot.self_id}-{event.user_id}-{event.message_id}] - {event.get_plaintext()}"
        )
        await bot.send(event, f"{e.msg}")
        raise IgnoredException("参数解析失败")
    except Exception as e:
        logger.warning(
            f"解析参数时异常，参数解析器解析错误 [{bot.self_id}-{event.user_id}-{event.message_id}] - {event.get_plaintext()}"
        )
        raise e

    state[STATE_ARGMATCH_RESULT] = argmatch_ins
