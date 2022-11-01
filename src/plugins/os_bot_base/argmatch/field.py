import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, Union
from .exception import FieldInitMatchError, ValidationError
from .tool import ProcessTool

if TYPE_CHECKING:
    from .argmatch import ArgMatch


class Field:
    """
    ## 字段构造器

    构建用于消息验证的字段

    args:

        name 字段命名，用于内置错误信息的显示及帮助定位

        type 字段类型，用于类型检查与转换

        require 是否必要

        process 字段处理器，自定义处理及验证，参数为待处理字符串及参数设置，返回值为处理后剩余的字符串，抛出异常则验证不通过

        help 字段帮助信息

        `keys`关键词字典或列表，用于映射关键词与对应值

        `keys_generate` 关键词列表生成器，用于动态生成关键词列表（优先使用）

        hook_error 异常hook，给用户提示错误信息前的回调，可以替换原始消息，返回值为真实发送给用户的消息。

        min 最小值 数值限定范围，字符串限制长度

        max 最大值 数值限定范围，字符串限制长度

        strict 严格模式 严格模式会对参数进行更严格的匹配限制，例如必须以分隔符分隔参数

        default 字段默认值

        errmsg 错误信息覆盖

    """
    _key: str
    """
        用于标记字段属于哪个ArgMatch参数
    """

    _basic_regex_str = u"""(("(?:[^"\\\\]|\\\\.)*")|[^{sep}]+)"""
    # 参数类型地图，用于限制与转换参数类型说明
    _type_map: dict = {
        "int": "整数",
        "float": "数值",
        "bool": "布尔类型",
        "str": "字符串",
        "regex": "正则表达式",
        "keys": "关键词",
        "custom": "自定义",
    }

    def __init__(self,
                 *,
                 name: str,
                 type: str,
                 require: Optional[bool] = None,
                 process: Callable[[str, "Field", "ArgMatch"], Any],
                 keys: Optional[Union[Dict[str, List[str]], List[str]]] = None,
                 keys_generate: Optional[Callable[[], Dict[str, Any]]] = None,
                 help: Optional[str] = None,
                 hook_error: Optional[Callable[[str, Exception], str]] = None,
                 min: Optional[int] = None,
                 max: Optional[int] = None,
                 strict: Optional[bool] = None,
                 default: Any = None,
                 errmsg: Optional[str] = None,
                 **kws) -> None:
        """
            name 字段命名，用于内置错误信息的显示及帮助定位

            type 字段类型，用于类型检查与转换

            require 是否必要

            process 字段处理器，定义处理及验证，参数为待处理字符串及参数设置，返回值为处理后剩余的字符串，抛出异常则验证不通过

            help 字段帮助信息

            `keys`关键词字典或列表，用于映射关键词与对应值

            hook_error 异常hook，给用户提示错误信息前的回调，可以替换原始消息，返回值为真实发送给用户的消息。

            min 最小值 数值限定范围，字符串限制长度

            max 最大值 数值限定范围，字符串限制长度

            strict 严格模式 严格模式会对参数进行更严格的匹配限制，例如必须以分隔符分隔参数

            default 字段默认值

            errmsg 错误信息覆盖

            额外字段

            keys_include_self 关键字字典是否包含自身(默认包含)

            ignoreCase 是否在关键词匹配时忽略大小写 默认为假
        """
        if type.lower() not in self._type_map:
            raise FieldInitMatchError(f"构造字段时异常，数据类型{type}不合法！")

        self._name = name
        """
            标记字段名称
        """
        self._type = type
        self._require = require
        self._process = process
        self._help = help
        self._source_keys = keys
        self._hook_error = hook_error
        self._min = min
        self._max = max
        self._strict = strict
        self._default = default
        self._errmsg = errmsg
        self._config = kws
        self._keys_generate = keys_generate

        if self._require is None:
            if self._default is None:
                self._require = True
            else:
                self._require = False

        # 转换为标准字典
        stand_keys: Dict[str, Any] = {}
        if isinstance(keys, dict):
            for key in keys:
                val = keys[key]
                if isinstance(val, str):
                    if not isinstance(val, str):
                        raise FieldInitMatchError("关键词只能为文本类型")
                    stand_keys[val] = key
                elif isinstance(val, list):
                    if "keys_include_self" not in kws or kws[
                            "keys_include_self"]:
                        stand_keys[f"{key}"] = key
                    for item in val:
                        if not isinstance(item, str):
                            raise FieldInitMatchError("关键词只能为文本类型")
                        stand_keys[item] = key
                else:
                    raise FieldInitMatchError("参数类型标记异常")
            self._keys = stand_keys

        if isinstance(keys, list):
            for item in keys:
                if not isinstance(item, str):
                    raise FieldInitMatchError("关键词只能为文本类型")
                stand_keys[item] = item
            self._keys = stand_keys

    @property
    def am_config(self):
        return self._config

    @staticmethod
    def Keys(name,
             keys: Optional[Union[Dict[str, List[str]], List[str]]] = None,
             keys_generate: Optional[Callable[[], Dict[str, Any]]] = None,
             default: Any = None,
             **kws) -> "Field" and Any:
        """
            构造一个关键词类型参数匹配器

            `keys`关键词字典或列表，用于映射关键词与对应值

            当keys为list时匹配到的字符串会原样提供匹配到的字符串为值

            当keys为dict时，为了便于配置，字典(dict)的值为关键词列表(list)，字典的键为关键词列表对应的值。

            例：

            {

                "val":["key1", "key2"]

            }

            当匹配文本为key1或key2时此字段的值均为val

            具体可参见`class Field`构造器
        """

        def process(msg: str, field: "Field", am: "ArgMatch"):
            if field._keys_generate:
                keys = field._keys_generate()
            else:
                keys = field._keys
            for key in keys:
                t_msg = msg.strip()
                # 忽略大小写？
                if "ignoreCase" in field.am_config and field.am_config[
                        "ignoreCase"]:
                    t_msg = t_msg.lower()
                    key: str = key.lower()
                # 检查是否可以匹配
                if t_msg.startswith(
                        key + am.Meta.separator) or t_msg.startswith(key):
                    if ProcessTool.isStrict(field, am) and not (
                            key == t_msg
                            or t_msg.startswith(key + am.Meta.separator)):
                        continue
                    ProcessTool.setVal(keys[key], field, am)
                    if t_msg.startswith(key + am.Meta.separator):
                        return msg[len(key + am.Meta.separator):]
                    return msg[len(key):]
            raise ValidationError(msg="{name} 不在关键词列表中", field=field)

        return Field(name=name,
                     type="keys",
                     process=process,
                     default=default,
                     keys=keys,
                     keys_generate=keys_generate,
                     **kws)

    @staticmethod
    def Str(name,
            min: Optional[int] = None,
            max: Optional[int] = None,
            default: Optional[str] = None,
            **kws) -> "Field" and str:
        """
            构造一个字符串类型参数匹配器

            min 最小值 数值限定范围，字符串限制长度

            max 最大值 数值限定范围，字符串限制长度

            具体可参见`class Field`构造器
        """

        def process(msg: str, field: "Field", am: "ArgMatch"):
            t_msg, tail = ProcessTool.splitArg(msg, field, am)
            length = len(t_msg)
            strFlag: bool = False
            # 字符串转义
            if t_msg.startswith("\"") and t_msg.endswith("\""):
                strFlag = True
                t_msg = t_msg[1:-1]
                t_msg = t_msg.replace("\\\"", "\"")
            if field._min is not None and length < field._min:
                raise ValidationError(msg="{name} 参数最小长度为 " + f"{field._min}",
                                      field=field)

            if field._max is not None and length > field._max:
                if strFlag or ProcessTool.isStrict(field, am) or tail.strip():
                    raise ValidationError(msg="{name} 参数最大长度为 " +
                                          f"{field._max}",
                                          field=field)
                # 有长度限制且非严格模式，后续无参数的情况下则切分字符串
                tail = t_msg[field._max:]
                t_msg = t_msg[0:field._max]

            if t_msg.startswith("\"") and t_msg.endswith("\""):
                t_msg = t_msg[1:-1]
                t_msg = t_msg.replace("\\\"", "\"")
            ProcessTool.setVal(t_msg, field, am)
            return tail

        return Field(name=name,
                     type="int",
                     process=process,
                     min=min,
                     max=max,
                     default=default,
                     **kws)  # type: ignore

    @staticmethod
    def Regex(name, regex: str, default: Any = None, **kws) -> "Field" and Any:
        """
            构造一个正则表达式类型参数匹配器

            正则表达式会使用re.match方法进行匹配

            具体可参见`class Field`构造器
        """

        def process(msg: str, field: "Field", am: "ArgMatch"):
            t_msg, tail = ProcessTool.splitArg(msg, field, am)
            # 字符串转义
            strFlag: bool = False
            if t_msg.startswith("\"") and t_msg.endswith("\""):
                strFlag = True
                t_msg = t_msg[1:-1]
                t_msg = t_msg.replace("\\\"", "\"")
            if not strFlag and not tail and not ProcessTool.isStrict(
                    field, am):
                # 非严格模式、后续参数为空、参数不以双引号包裹则尝试二次分离参数
                result = re.match(regex, t_msg)
                if not result:
                    raise ValidationError(msg="{name} 参数正则不匹配！", field=field)
                t_msg = msg[0:result.end()]
                tail = msg[result.end():]
            else:
                result = re.match(regex, t_msg)
                if not result:
                    raise ValidationError(msg="{name} 参数正则不匹配！", field=field)
            ProcessTool.setVal(t_msg, field, am)
            return tail

        return Field(name=name,
                     type="regex",
                     process=process,
                     default=default,
                     **kws)

    @staticmethod
    def Int(name,
            min: Optional[int] = None,
            max: Optional[int] = None,
            default: Optional[int] = None,
            **kws) -> "Field" and int:
        """
            构造一个整数型参数匹配器

            min 最小值 限定范围，保证结果不小于min。

            max 最大值 限定范围，保证结果不大于max。

            具体可参见`class Field`构造器
        """

        def process(msg: str, field: "Field", am: "ArgMatch"):
            t_msg, tail = ProcessTool.splitArg(msg, field, am)
            if t_msg.startswith("\"") and t_msg.endswith("\""):
                raise ValidationError(msg="{name} 参数必须为合法整数", field=field)
            if not tail and not ProcessTool.isStrict(field, am):
                # 非严格模式、后续参数为空、参数不以双引号包裹则尝试二次分离参数
                # regex = u"""[0-9,]+\\.[0-9]*"""
                regex = u"""(\\+|-)?[0-9,]+"""
                result = re.match(regex, t_msg)
                if not result:
                    raise ValidationError(msg="{name} 参数必须为合法整数！", field=field)
                tail = t_msg[result.end():]
                t_msg = t_msg[0:result.end()]
            t_msg = t_msg.replace(",", "")
            try:
                val = int(float(t_msg))
            except Exception:
                raise ValidationError(msg="{name} 参数必须为合法整数", field=field)
            if field._min is not None and val < field._min:
                raise ValidationError(msg="{name} 参数需要大于 " + f"{field._min}",
                                      field=field)
            if field._max is not None and val > field._max:
                raise ValidationError(msg="{name} 参数需要小于 " + f"{field._max}",
                                      field=field)
            ProcessTool.setVal(val, field, am)
            return tail

        return Field(name=name,
                     type="int",
                     process=process,
                     min=min,
                     max=max,
                     default=default,
                     **kws)  # type: ignore

    @staticmethod
    def Float(name,
              min: Optional[int] = None,
              max: Optional[int] = None,
              default: Optional[float] = None,
              **kws) -> "Field" and float:
        """
            构造一个数值型参数匹配器

            min 最小值 数值限定范围，字符串限制长度

            max 最大值 数值限定范围，字符串限制长度

            具体可参见`class Field`构造器
        """

        def process(msg: str, field: "Field", am: "ArgMatch"):
            t_msg, tail = ProcessTool.splitArg(msg, field, am)
            if t_msg.startswith("\"") and t_msg.endswith("\""):
                raise ValidationError(msg="{name} 参数必须为合法整数", field=field)
            if not tail and not ProcessTool.isStrict(field, am):
                # 非严格模式、后续参数为空、参数不以双引号包裹则尝试二次分离参数
                regex = u"""(\\+|-)?([0-9,]+)?(\\.[0-9]*)?"""
                # regex = u"""[0-9,]+"""
                result = re.match(regex, t_msg)
                if not result or result.end() == 0:
                    raise ValidationError(msg="{name} 参数必须为合法数值！", field=field)
                tail = t_msg[result.end():]
                t_msg = t_msg[0:result.end()]
            try:
                val = float(t_msg)
            except Exception:
                raise ValidationError(msg="{name} 参数必须为合法数值", field=field)
            if field._min is not None and val < field._min:
                raise ValidationError(msg="{name} 参数需要大于 " + f"{field._min}",
                                      field=field)
            if field._max is not None and val > field._max:
                raise ValidationError(msg="{name} 参数需要小于 " + f"{field._max}",
                                      field=field)
            ProcessTool.setVal(val, field, am)
            return tail

        return Field(name=name,
                     type="float",
                     min=min,
                     max=max,
                     process=process,
                     default=default,
                     **kws)  # type: ignore

    @staticmethod
    def Bool(name,
             keys: Optional[Dict[Any, List[str]] or List[str]] = None,
             default: Optional[bool] = None,
             **kws) -> "Field" and bool:
        """
            构造一个布尔型参数匹配器

            `keys`关键词字典或列表，用于映射关键词与对应值

            具体可参见`class Field`构造器
        """
        if keys is None:
            keys = {
                True: [
                    "true", "开", "是", "t", "on", "开启", "真", "1", "允许", "启用",
                    "allow", "open", "授权"
                ],
                False: [
                    "false", "关", "否", "f", "off", "关闭", "假", "0", "禁止", "禁用",
                    "deny", "close", "拒绝"
                ]
            }

        def process(msg: str, field: "Field", am: "ArgMatch"):
            for key in field._keys:
                t_msg = msg
                # 忽略大小写？
                if "ignoreCase" in field.am_config and field.am_config[
                        "ignoreCase"]:
                    t_msg = t_msg.lower()
                    key: str = key.lower()
                # 检查是否可以匹配
                if t_msg.startswith(
                        key + am.Meta.separator) or t_msg.startswith(key):
                    if ProcessTool.isStrict(field, am) and not (
                            key == t_msg
                            or t_msg.startswith(key + am.Meta.separator)):
                        continue
                    ProcessTool.setVal(field._keys[key], field, am)
                    if t_msg.startswith(key + am.Meta.separator):
                        return msg[len(key + am.Meta.separator):]
                    return msg[len(key):]
            raise ValidationError(msg="{name} 无法转换为布尔类型", field=field)

        return Field(name=name,
                     type="bool",
                     keys=keys,
                     process=process,
                     default=default,
                     **kws)  # type: ignore

    @staticmethod
    def Custom(name,
               process: Callable[[str, "Field", "ArgMatch"], Awaitable[Any]],
               default: Any = None,
               **kws) -> "Field" and Any:
        """
            构造一个自定义参数匹配器

            process 字段处理器，自定义处理及验证，参数为待处理字符串及参数设置，返回值为处理后剩余的字符串，抛出异常则验证不通过

            具体可参见`class Field`构造器
        """
        return Field(name=name,
                     type="custom",
                     process=process,
                     default=default,
                     **kws)

    def _msg_info(self, merge: Optional[Dict[str, Any]] = None):
        """
            用于提供一个格式化用消息字典
            用以转换提示信息中的变量
        """
        if merge is None:
            merge = {}
        if not isinstance(merge, defaultdict):
            merge = defaultdict((lambda: "None"), merge)
        merge["name"] = self._name
        merge["type"] = self._type_map[self._type.lower()]
        merge["help"] = self._help
        return merge

    @property
    def help(self):
        """
            获取参数的帮助信息
        """
        if self._help:
            return self._help
        msg = "参数类型 {type}"
        if self._max or self._min:
            msg += f""" 大小 {self._min if self._min else "-∞"} ~ {self._max if self._max else "+∞"}"""
        if self._type == "keys":
            keys = self._keys
            msg += "\n可用值："
            if len(keys) < 10:
                for key in keys:
                    msg += f"{key}、"
                msg = msg[:-1]
            else:
                i = 0
                for key in keys:
                    if i > 8:
                        break
                    msg += f"{key}、"
                    i += 1
                msg += "等..."
        if self._type == "bool":
            msg += " 通过开、关、t、f等关键词设置"
        return msg.format_map(self._msg_info())
