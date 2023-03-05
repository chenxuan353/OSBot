import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .argmatch import ArgMatch
    from .field import Field


class ProcessTool:

    _basic_regex_str_cache = None

    @staticmethod
    def isStrict(field: "Field", am: "ArgMatch"):
        # 检查是否为严格模式 isStrict(field, am)
        if field._strict is None:
            return am.Meta.strict
        return field._strict

    @classmethod
    def splitArg(cls, msg: str, field: "Field", am: "ArgMatch"):
        """
            分离参数
            split

            返回值：[分离出的参数,剩余的文本]
        """
        if not msg:
            return ["", ""]
        if not cls._basic_regex_str_cache:
            cls._basic_regex_str_cache = re.compile(
                field._basic_regex_str.format(
                    sep=am.Meta.separator if am.Meta.separator != " " else "\\s"
                ))
        res = cls._basic_regex_str_cache.split(msg, maxsplit=1)
        if len(res) < 3:
            return [msg, ""]
        return [res[1], res[3]]

    @staticmethod
    def setVal(val: Any, field: "Field", am: "ArgMatch"):
        """
            设置参数解析值
        """
        am.__setattr__(field._key, val)

    @staticmethod
    def getVal(field: "Field", am: "ArgMatch") -> Any:
        """
            获取参数解析值
        """
        return am.__getattribute__(field._key)
