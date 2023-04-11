import difflib
from typing import List, Tuple
from functools import wraps
from nonebot.matcher import Matcher
from nonebot.adapters.onebot import v11
from nonebot.exception import NoneBotException
from ..exception import MatcherErrorFinsh
from ..argmatch import FieldMatchError
from ..logger import logger
from ..cache import OnebotCache


async def plug_is_disable(name: str, group_mark: str) -> bool:
    """
        用于获取指定插件是否被禁用

        被禁用则返回`False`

        - `name` 插件标识名
        - `group_mark` 需要判断的组标识(一般通过`adapter.mark_group_without_drive(bot, event)`获取)
    """
    from ..plugin_manage import _get_plug_model, _get_plug_switch_model
    try:
        plugModel = await _get_plug_model(name)
        if not plugModel:
            return False
        if not plugModel.load:
            return True
        plugSwitchModel = await _get_plug_switch_model(name, group_mark)
        if plugModel and not plugModel.switch:
            return True

        if plugSwitchModel:
            if plugSwitchModel.switch:
                return False
            else:
                return True
        if plugModel and not plugModel.default_switch:
            return True
        return False
    except Exception as e:
        logger.opt(exception=True).debug(f"在检查{name} - {group_mark}是否被禁用时异常。")
        raise e


def matcher_exception_try():

    def decorator(func):

        @wraps(func)
        async def wrap(*args, **kws):
            try:
                return await func(*args, **kws)
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


def inhibiting_exception(task_name: str = "", logger=logger):
    """
        抑制异常并输出到日志中，适用于`gather`方法以及所有不需要抛出异常的方法。
    """

    def decorator(func):

        @wraps(func)
        async def wrap(*args, **kws):
            try:
                return await func(*args, **kws)
            except (MatcherErrorFinsh, NoneBotException, FieldMatchError) as e:
                if task_name:
                    logger.opt(exception=True).debug("执行异步函数`{}.{}`时异常！",
                                                     func.__module__,
                                                     func.__name__)
                else:
                    logger.opt(exception=True).debug("执行异步函数`{}`时异常！",
                                                     task_name)
            except Exception as e:
                if task_name:
                    logger.opt(exception=True).error("执行异步函数`{}.{}`时异常！",
                                                     func.__module__,
                                                     func.__name__)
                else:
                    logger.opt(exception=True).error("执行异步函数`{}`时异常！",
                                                     task_name)

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


def message_to_str(message: v11.Message) -> str:
    msg_str = ""
    for msgseg in message:
        if msgseg.is_text():
            msg_str += msgseg.data.get("text")  # type: ignore
        elif msgseg.type == "at":
            msg_str += f"@{OnebotCache.get_instance().get_unit_nick(msgseg.data.get('qq'))} "  # type: ignore
        elif msgseg.type == "image":
            msg_str += f"[图片]"
        else:
            msg_str += f"[{msgseg.type}]"
    return msg_str


def seconds_to_dhms(seconds: float, compact: bool = False) -> str:
    """
        秒 转 天、时、分、秒字符串
    """

    def _days(day):
        if compact:
            if not day:
                return ""
            return "{}天".format(day)
        else:
            return "{} 天 ".format(day)

    def _hours(hour):
        if compact:
            if not hour:
                return ""
            return "{}时".format(hour)
        else:
            return "{} 时 ".format(hour)

    def _minutes(minute):
        if compact:
            if not minute:
                return ""
            return "{}分".format(minute)
        else:
            return "{} 分 ".format(minute)

    def _seconds(second):
        if compact:
            if not second:
                return ""
            if isinstance(seconds, int):
                return f"{second}秒"
            else:
                return f"{second:.2f}秒"
        else:
            if isinstance(seconds, int):
                return f"{second} 秒"
            else:
                return f"{second:.2f} 秒"

    days = seconds // (3600 * 24)
    hours = (seconds // 3600) % 24
    minutes = (seconds // 60) % 60
    seconds = seconds % 60
    if days > 0:
        return _days(days) + _hours(hours) + _minutes(minutes) + _seconds(
            seconds)
    if hours > 0:
        return _hours(hours) + _minutes(minutes) + _seconds(seconds)
    if minutes > 0:
        return _minutes(minutes) + _seconds(seconds)
    return _seconds(seconds)
