"""
    文本解析器
"""
from .field import Field
from .argmatch import ArgMatch
from .exception import MatchError, FieldMatchError, ValidationError, RequireMatchError


class PageArgMatch(ArgMatch):

    page: int = Field.Int("页数", min=1, default=1,
                          help="页码，大于等于1。")  # type: ignore

    def __init__(self) -> None:
        super().__init__([PageArgMatch.page])  # type: ignore


class IntArgMatch(ArgMatch):

    num: int = Field.Int("整数", help="任意整数")  # type: ignore

    def __init__(self) -> None:
        super().__init__([IntArgMatch.num])  # type: ignore
