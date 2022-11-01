from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .field import Field


class MatchError(Exception):

    def __init__(self,
                 *args: object,
                 cause: Optional[Exception] = None,
                 msg: Optional[str] = None) -> None:
        self._cause = cause
        self._msg = msg
        super().__init__(*args)

    @property
    def msg(self):
        return self._msg


class FieldInitMatchError(MatchError):

    def __init__(self, *args: object, **kws) -> None:
        super().__init__(*args, msg="字段初始化异常！", **kws)


class FieldMatchError(MatchError):
    """
        字段match异常
    """

    def __init__(self,
                 *args: object,
                 field: "Field",
                 msg: str = "{name} 参数异常！",
                 **kws) -> None:
        self._field = field
        if field._errmsg is not None:
            msg = field._errmsg.format_map(field._msg_info())
        else:
            msg = msg.format_map(field._msg_info())
        super().__init__(*args, msg=msg, **kws)

    @property
    def field(self):
        return self._field


class RequireMatchError(FieldMatchError):

    def __init__(self,
                 *args: object,
                 field: "Field",
                 msg: str = "{name} 不能为空！",
                 **kws) -> None:
        super().__init__(*args, msg=msg, field=field, **kws)


class ValidationError(FieldMatchError):

    def __init__(self,
                 *args: object,
                 field: "Field",
                 msg: str = "{name} 无法通过验证！",
                 **kws) -> None:
        super().__init__(*args, msg=msg, field=field, **kws)


class NoneValidationError(FieldMatchError):

    def __init__(self,
                 *args: object,
                 field: "Field",
                 msg: str = "{name} 参数为空！",
                 **kws) -> None:
        super().__init__(*args, msg=msg, field=field, **kws)
