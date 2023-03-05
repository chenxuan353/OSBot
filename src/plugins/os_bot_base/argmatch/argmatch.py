import abc
import traceback
from nonebot.adapters.onebot import v11
from nonebot.adapters import Message
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Self
from .exception import NoneValidationError, RequireMatchError, MatchError, ValidationError
from .tool import ProcessTool
from .field import Field
from ..logger import logger


class ArgMatch(abc.ABC):
    """
        ### 消息分离器

        用于指令式分离文本中的参数

        使用消息分离器前需要继承，并调用初始化方法并提供参数顺序，用于保证参数顺序正常。

        例：

    """

    _tail: str  # 匹配后剩余的字符串
    _args: List["Field"]  # 参数顺序列表
    _kws: Dict[str, "Field"]  # 参数列表 键：参数名 值：Field定义

    class Meta:
        name: Optional[str] = None  # 匹配器名称
        des: Optional[str] = None  # 匹配器描述
        separator: str = " "  # 分隔符 用于进行参数分隔，尽量不使用$作为分隔符，只支持单个字符。
        strict: bool = False  # 严格匹配(通过分隔符进行严格匹配)
        debug: bool = False
        """
            开启时会强制通过分隔符分割参数

            分隔后的参数依次提供给字段处理器

            处理器返回的字符串不为空时将认为参数不匹配

            分割符转义 $sep$
        """

    def __init__(self, args: List[Union["Field", Any]] = []) -> None:
        super().__init__()
        self._args = args  # type: ignore
        self._kws = {}
        for key in self.__class__.__dict__:
            val = self.__class__.__dict__[key]
            if not isinstance(val, Field):
                continue
            # 初始化参数匹配器
            val._key = key
            self._kws[key] = val
            self.__dict__[key] = None
        self._kws["tail"] = Field.Str("剩余字符串")  # type: ignore
        self._kws["tail"]._key = "_tail"  # type: ignore

    @staticmethod
    def v11_message_to_str(message: v11.Message) -> str:
        msg_str = ""
        for msgseg in message:
            if msgseg.is_text():
                msg_str += msgseg.data.get("text")  # type: ignore
            elif msgseg.type == "at":
                msg_str += f" {msgseg.data.get('qq')} "  # type: ignore
            elif msgseg.type == "image":
                msg_str += f"[图片]"
            else:
                msg_str += f"[{msgseg.type}]"
        return msg_str

    @classmethod
    def message_to_str(cls, message: Message) -> str:
        if isinstance(message, v11.Message):
            return cls.v11_message_to_str(message)
        raise MatchError("参数处理器不支持的消息类型")

    @property
    def am_args(self) -> List["Field"]:
        """
            参数匹配顺序

            例：[ self.msgtype, self.userid, self.msg ]
        """
        return self._args

    @property
    def am_kws(self) -> Dict[str, "Field"]:
        """
            参数命名映射列表
        """
        return self._kws

    @property
    def am_help(self) -> str:
        """
            获取当前命令的参数描述
        """
        msg = ""
        for arg in self.am_args:
            if arg._require:
                msg += f"[{arg._name}] "
            else:
                msg += f"<{arg._name}> "
        return msg.strip()

    def am_field_help(self, field: str) -> Optional[str]:
        """
            通过字段名查询字段帮助信息
        """
        if field is None:
            return self.am_help
        for arg in self.am_args:
            if arg._name == field:
                return arg.help
        return None

    @property
    def tail(self):
        """
            匹配后剩余的字符串
        """
        return self._tail

    def am_todict(self) -> Dict[str, Any]:
        """
            将匹配结果转换为字典返回
        """
        result = {}
        for key in self.am_kws:
            result[key] = self.__getattribute__(key)
        result["tail"] = self.tail
        return result

    def __call__(self, text: str) -> Self:
        """
            运行消息分离器
        """
        now_text = text.replace("\r", "")  # 移除干扰项
        args = self._args
        for arg in args:
            try:
                if not now_text:
                    raise NoneValidationError(field=arg)
                now_text = arg._process(now_text, arg, self)
            except NoneValidationError as e:
                pass
            except MatchError as e:
                if arg._require:
                    raise e
            except Exception as e:
                if self.Meta.debug:
                    print(traceback.format_exc())
                logger.opt(exception=True).debug("参数解析器内部函数异常，请联系管理员")
                raise ValidationError(msg="参数解析器内部函数异常，请联系管理员",
                                      field=arg,
                                      cause=e)

            # 对必须字段进行处理
            if ProcessTool.getVal(arg, self) is None:
                if arg._require:
                    raise RequireMatchError(field=arg)
                ProcessTool.setVal(arg._default, arg, self)
        ProcessTool.setVal(now_text, self._kws["tail"], self)
        return self
