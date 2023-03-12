"""
    # 命令文本解析器

    支持对命令参数进行自动化解析，以半固定格式从文本中分离参数。
"""
from .field import Field
from .argmatch import ArgMatch
from .exception import MatchError, FieldMatchError, ValidationError, RequireMatchError


class PageArgMatch(ArgMatch):

    page: int = Field.Int("页数", min=1, default=1,
                          help="页码，大于等于1。")
    def __init__(self) -> None:
        super().__init__([PageArgMatch.page])


class IntArgMatch(ArgMatch):

    num: int = Field.Int("整数", help="任意整数")

    def __init__(self) -> None:
        super().__init__([IntArgMatch.num])
