import difflib
from typing import List, Tuple
from functools import wraps
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.exception import NoneBotException
from .exception import MatcherErrorFinsh
from .argmatch import FieldMatchError
from .logger import logger


def matcher_exception_try():

    def decorator(func):

        @wraps(func)
        async def wrap(*args, **kws):
            try:
                await func(*args, **kws)
            except NoneBotException as e:
                raise e
            except FieldMatchError as e:
                logger.opt(exception=True).debug(f"解析参数失败，{e.msg}")
                await Matcher.finish(e.msg)
            except MatcherErrorFinsh as e:
                logger.opt(exception=True).debug(f"Matcher错误：{e.info}")
                await Matcher.finish(e.info)
            except Exception as e:
                logger.opt(exception=True).warning(f"Matcher异常！")
                await Matcher.finish("看起来出了问题，找管理员问问吧。")

        return wrap

    return decorator


def match_suggest(strs: List[str],
                  search: str,
                  ratio_limit: float = 0.6) -> List[str]:
    """
        通过字符串列表获取输入建议

        `ratio_limit`将限制字符串最低匹配度，默认为`0.6`
    """
    matchs: List[Tuple[str, float]] = []
    for s in strs:
        ratio = difflib.SequenceMatcher(None, s, search).quick_ratio()
        if ratio > ratio_limit:
            matchs.append((s, ratio))
    matchs.sort(reverse=True, key=lambda t: t[1])
    return [elem[0] for elem in matchs]


def only_command():
    """
        匹配无参数命令
    """

    async def checker(msg: Message = CommandArg()) -> bool:
        return not msg

    return checker
