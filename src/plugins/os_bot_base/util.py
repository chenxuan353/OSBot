import difflib
from typing import List, Tuple
from functools import wraps
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.adapters.onebot import v11
from nonebot.params import CommandArg
from nonebot.exception import NoneBotException
from .exception import MatcherErrorFinsh
from .argmatch import FieldMatchError
from .logger import logger
from .model import PluginModel, PluginSwitchModel
from .cache import OnebotCache


async def plug_is_disable(name: str, group_mark: str) -> bool:
    """
        用于获取指定插件是否被禁用

        被禁用则返回`False`

        - `name` 插件标识名
        - `group_mark` 需要判断的组标识(一般通过`adapter.mark_group_without_drive(bot, event)`获取)
    """
    try:
        plugModel = await PluginModel.get_or_none(name=name)
        if not plugModel:
            return False
        if not plugModel.load:
            return True
        plugSwitchModel = await PluginSwitchModel.get_or_none(
            **{
                "name": name,
                "group_mark": group_mark
            })
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
