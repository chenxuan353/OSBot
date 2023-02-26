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
        "relate_time": "相对时间",
        "custom": "自定义",
    }

    def __init__(self,
                 *,
                 name: str,
                 type: str,
                 require: Optional[bool] = None,
                 process: Callable[[str, "Field", "ArgMatch"], Any],
                 keys: Optional[Union[Dict[Union[str, int, bool], List[str]],
                                      List[str]]] = None,
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
             keys: Optional[Union[Dict[Union[str, int, bool], List[str]],
                                  List[str]]] = None,
             keys_generate: Optional[Callable[[], Dict[str, Any]]] = None,
             default: Any = None,
             **kws) -> Any:
        """
            构造一个关键词类型参数匹配器

            `keys`关键词字典或列表，用于映射关键词与对应值

            当keys为list时匹配到的字符串会原样提供匹配到的字符串为值

            当keys为dict时，为了便于配置，字典(dict)的值为关键词列表(list)，字典的键为关键词列表对应的值。

            当`keys_generate`方法存在时，每次执行前均会重新执行此方法用于获取keys，此keys的键被视为匹配值，值被视为最终返回值

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
                t_msg = msg.strip().replace("\r", "")
                # 忽略大小写？
                if "ignoreCase" in field.am_config and field.am_config[
                        "ignoreCase"]:
                    t_msg = t_msg.lower()
                    key: str = key.lower()
                # 检查是否可以匹配
                if t_msg.startswith(key):
                    if ProcessTool.isStrict(field, am) and not (
                            key == t_msg
                            or t_msg.startswith(key + am.Meta.separator)):
                        continue
                    ProcessTool.setVal(keys[key], field, am)
                    if t_msg.startswith(key + am.Meta.separator) or (
                            am.Meta.separator == ""
                            and t_msg.startswith(key + "\n")):
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
            **kws) -> Any:
        """
            构造一个字符串类型参数匹配器

            - `min` 最小值 数值限定范围，字符串限制长度
            - `max` 最大值 数值限定范围，字符串限制长度

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
                raise ValidationError(msg="{name}至少" + f"{field._min}个字符哦",
                                      field=field)

            if field._max is not None and length > field._max:
                if strFlag or ProcessTool.isStrict(field, am) or tail.strip():
                    raise ValidationError(msg="{name}最多" + f"{field._max}个字符哦",
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
    def Regex(name, regex: str, default: Any = None, **kws) -> Any:
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
                    raise ValidationError(msg="{name}正则不匹配！", field=field)
                t_msg = msg[0:result.end()]
                tail = msg[result.end():]
            else:
                result = re.match(regex, t_msg)
                if not result:
                    raise ValidationError(msg="{name}正则不匹配！", field=field)
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
            **kws) -> Any:
        """
            构造一个整数型参数匹配器

            - `min` 最小值 限定范围，保证结果不小于min。
            - `max` 最大值 限定范围，保证结果不大于max。

            具体可参见`class Field`构造器
        """

        def process(msg: str, field: "Field", am: "ArgMatch"):
            t_msg, tail = ProcessTool.splitArg(msg, field, am)
            if t_msg.startswith("\"") and t_msg.endswith("\""):
                raise ValidationError(msg="{name}需要是整数哦", field=field)
            if not tail and not ProcessTool.isStrict(field, am):
                # 非严格模式、后续参数为空、参数不以双引号包裹则尝试二次分离参数
                # regex = u"""[0-9,]+\\.[0-9]*"""
                regex = u"""(\\+|-)?[0-9,]+"""
                result = re.match(regex, t_msg)
                if not result:
                    raise ValidationError(msg="{name}需要是整数哦", field=field)
                tail = t_msg[result.end():]
                t_msg = t_msg[0:result.end()]
            t_msg = t_msg.replace(",", "")
            try:
                val = int(float(t_msg))
            except Exception:
                raise ValidationError(msg="{name}需要是整数哦", field=field)
            if field._min is not None and val < field._min:
                raise ValidationError(msg="{name}太小啦，至少要大于" +
                                      f"{field._min}哦！",
                                      field=field)
            if field._max is not None and val > field._max:
                raise ValidationError(msg="{name}太大了，需要小于" + f"{field._max}哦！",
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
              **kws) -> Any:
        """
            构造一个数值型参数匹配器

            - `min` 最小值 数值限定范围，字符串限制长度
            - `max` 最大值 数值限定范围，字符串限制长度

            具体可参见`class Field`构造器
        """

        def process(msg: str, field: "Field", am: "ArgMatch"):
            t_msg, tail = ProcessTool.splitArg(msg, field, am)
            if t_msg.startswith("\"") and t_msg.endswith("\""):
                raise ValidationError(msg="{name}要是数值哦。", field=field)
            if not tail and not ProcessTool.isStrict(field, am):
                # 非严格模式、后续参数为空、参数不以双引号包裹则尝试二次分离参数
                regex = u"""(\\+|-)?([0-9,]+)?(\\.[0-9]*)?"""
                # regex = u"""[0-9,]+"""
                result = re.match(regex, t_msg)
                if not result or result.end() == 0:
                    raise ValidationError(msg="{name}要是数值哦。", field=field)
                tail = t_msg[result.end():]
                t_msg = t_msg[0:result.end()]
            try:
                val = float(t_msg)
            except Exception:
                raise ValidationError(msg="{name}要是数值哦。", field=field)
            if field._min is not None and val < field._min:
                raise ValidationError(msg="{name}太小啦，至少要大于" +
                                      f"{field._min}哦！",
                                      field=field)
            if field._max is not None and val > field._max:
                raise ValidationError(msg="{name}太大了，需要小于" + f"{field._max}哦！",
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
             keys: Optional[Union[Dict[Any, List[str]], List[str]]] = None,
             default: Optional[bool] = None,
             **kws) -> Any:
        """
            构造一个布尔型参数匹配器

            - `keys`关键词字典或列表，用于映射关键词与对应值，默认使用内置参数

            具体可参见`class Field`构造器
        """
        if keys is None:
            keys = {
                True: [
                    "true", "开", "是", "t", "on", "开启", "真", "允许", "启用",
                    "allow", "open", "授权"
                ],
                False: [
                    "false", "关", "否", "f", "off", "关闭", "假", "禁止", "禁用",
                    "deny", "close", "拒绝"
                ]
            }

        def process(msg: str, field: "Field", am: "ArgMatch"):
            for key in field._keys:
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
                    ProcessTool.setVal(field._keys[key], field, am)
                    if t_msg.startswith(key + am.Meta.separator):
                        return msg[len(key + am.Meta.separator):]
                    return msg[len(key):]
            raise ValidationError(msg="哦呀，{name}需要是开关值哦，是或否之类的。", field=field)

        return Field(name=name,
                     type="bool",
                     keys=keys,
                     process=process,
                     default=default,
                     **kws)  # type: ignore

    @staticmethod
    def RelateTime(name,
                   min: Optional[int] = 0,
                   max: Optional[int] = None,
                   default: Optional[int] = None,
                   **kws) -> Any:
        """
            相对时间解析器，返回单位为秒

            - `keys`关键词字典或列表，用于映射关键词与对应值，默认使用内置参数
            - `min`最小值，默认从0开始
            - `max`最大值
            - `errmsg`错误信息，此类型推荐覆盖

            具体可参见`class Field`构造器
        """
        basic_regex = re.compile(
            u"[0-9〇一二三四五六七八九零壹贰叁肆伍陆柒捌玖貮两十拾百佰]+(y|year|年|mom|个月|月|d|day|天|h|hour|个小时|小时|时|m|min|分钟|分|s|sec|秒钟|秒)?"
        )
        convert_cndigit_regex = re.compile(
            r'[〇一二三四五六七八九零壹贰叁肆伍陆柒捌玖貮两十拾百佰千仟万萬亿億兆]+')
        time_parse_regex_y = re.compile(r'(-?[1-9][0-9]*)(?:y|year|年)')
        time_parse_regex_month = re.compile(r'([1-9][0-9]*)(?:mom|月|个月)')
        time_parse_regex_d = re.compile(r'(-?[1-9][0-9]*)(?:d|day|天)')
        time_parse_regex_h = re.compile(r'(-?[1-9][0-9]*)(?:h|hour|小时|个小时)')
        time_parse_regex_m = re.compile(r'(-?[1-9][0-9]*)(?:m|min|分钟|分)')
        time_parse_regex_s = re.compile(r'(-?[1-9][0-9]*)(?:s|sec|秒钟|秒)')
        time_parse_regex = re.compile(r'(-?[1-9][0-9]*)')

        def convert_cndigit(s: str):
            """
                将字符串起始部分可能存在的中文数字转换为阿拉伯数字，并返回转换后的结果
            """
            CN_NUM = {
                '〇': 0,
                '一': 1,
                '二': 2,
                '三': 3,
                '四': 4,
                '五': 5,
                '六': 6,
                '七': 7,
                '八': 8,
                '九': 9,
                '零': 0,
                '壹': 1,
                '贰': 2,
                '叁': 3,
                '肆': 4,
                '伍': 5,
                '陆': 6,
                '柒': 7,
                '捌': 8,
                '玖': 9,
                '貮': 2,
                '两': 2,
            }

            CN_UNIT = {
                '十': 10,
                '拾': 10,
                '百': 100,
                '佰': 100,
                '千': 1000,
                '仟': 1000,
                '万': 10000,
                '萬': 10000,
                '亿': 100000000,
                '億': 100000000,
                '兆': 1000000000000,
            }

            regex_result = convert_cndigit_regex.search(s.lstrip())
            if regex_result:
                wd_str = regex_result.group()
            else:
                return s
            result = 0
            result_list = []
            unit = 0
            control = 0
            for i, d in enumerate(wd_str):
                if d in '零百佰千仟万萬亿億兆〇' and i == 0:
                    return s
                if d in CN_NUM:  # 如果为单个数字直接赋值
                    result += CN_NUM[d]
                elif d in CN_UNIT:
                    if unit == 0:
                        unit_1 = CN_UNIT[d]
                        # 这里的处理主要是考虑到类似于二十三亿五千万这种数
                        if result == 0:
                            result = CN_UNIT[d]
                        else:
                            result *= CN_UNIT[d]
                        unit = CN_UNIT[d]
                        result_1 = result
                    elif unit > CN_UNIT[d]:
                        result -= CN_NUM[wd_str[i - 1]]
                        result += CN_NUM[wd_str[i - 1]] * CN_UNIT[d]
                        unit = CN_UNIT[d]
                    elif unit <= CN_UNIT[d]:
                        if (CN_UNIT[d] < unit_1) and (len(  # type: ignore
                                result_list) == control):
                            result_list.append(result_1)  # type: ignore
                            result = (result -
                                      result_1) * CN_UNIT[d]  # type: ignore
                            control += 1
                        else:
                            result *= CN_UNIT[d]
                        unit = CN_UNIT[d]
                        # 处理二十三亿五千万和壹兆零六百二十三亿五千五百万五百这种数，及时截断
                        if len(result_list) == control:
                            unit_1 = unit
                            result_1 = result
                else:
                    return s
            return f"{sum(result_list) + result}{s.lstrip()[regex_result.span()[1]:]}"

        def time_parse(s: str) -> int:
            s = s.strip()
            if not s:
                return 0
            if s == "永久":
                return 0
            if s == "半年":
                return int(365 * 86400 / 2)
            if s == "半个月":
                return 86400 * 15
            if s == "半天":
                return 12 * 3600
            if s == "半小时":
                return 1800
            if s == "半分钟":
                return 30
            s = convert_cndigit(s)
            result = time_parse_regex_y.match(s)
            if result:
                num = int(result.group(1))
                return num * 86400 * 365
            result = time_parse_regex_month.match(s)
            if result:
                num = int(result.group(1))
                return num * 86400 * 30
            result = time_parse_regex_d.match(s)
            if result:
                num = int(result.group(1))
                return num * 86400
            result = time_parse_regex_h.match(s)
            if result:
                num = int(result.group(1))
                return num * 3600
            result = time_parse_regex_m.match(s)
            if result:
                num = int(result.group(1))
                return num * 60
            result = time_parse_regex_s.match(s)
            if result:
                num = int(result.group(1))
                return num
            result = time_parse_regex.match(s)
            if result:
                num = int(result.group(1))
                return num
            return 0

        def process(msg: str, field: "Field", am: "ArgMatch"):
            t_msg, tail = ProcessTool.splitArg(msg, field, am)

            result = basic_regex.search(t_msg.strip())
            if not result:
                raise ValidationError(msg="{name}需要一个正常的时间描述哦(1天、一分钟等)",
                                      field=field)

            if ProcessTool.isStrict(field, am):
                # 严格模式下禁止二次分离
                if result.span()[1] != len(t_msg.strip()):
                    raise ValidationError(msg="{name}需要一个正常的时间描述哦(1天、一分钟等)",
                                          field=field)

            if result.span()[1] != len(t_msg.lstrip()):
                tail = t_msg[result.span()[1]:] + tail
                t_msg = t_msg[:result.span()[1]]

            t_msg = t_msg.strip()

            try:
                val = time_parse(t_msg)
            except Exception:
                raise ValidationError(msg="{name}需要一个正常的时间描述哦(1天、一分钟等)",
                                      field=field)
            if field._min is not None and val < field._min:
                raise ValidationError(msg="{name}太小啦，至少要大于" +
                                      f"{field._min}秒哦！",
                                      field=field)
            if field._max is not None and val > field._max:
                raise ValidationError(msg="{name}太大了，需要小于" +
                                      f"{field._max}秒哦！",
                                      field=field)
            ProcessTool.setVal(val, field, am)
            return tail

        return Field(name=name,
                     type="relate_time",
                     process=process,
                     min=min,
                     max=max,
                     default=default,
                     **kws)  # type: ignore

    @staticmethod
    def Custom(name,
               process: Callable[[str, "Field", "ArgMatch"], Awaitable[Any]],
               default: Any = None,
               **kws) -> Any:
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
