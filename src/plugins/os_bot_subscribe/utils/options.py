import re
from typing import Any, Dict, List, Optional, Tuple, Union
from typing_extensions import Self
from ..exception import BaseException
from ...os_bot_base.session import StoreSerializable


class Option:
    """
        选项
    """

    def __init__(self,
                 default: bool,
                 names: Union[str, List[str], Tuple[str]],
                 des: Optional[str] = None) -> None:
        """
            default 默认值

            names 命名列表，填一个字符串时会自动转换为单字符串列表

            des 描述，为空时默认为命名列表首位
        """
        if isinstance(names, str):
            names = [names]
        self.default = default
        self.names = names
        self.des = des

    @classmethod
    def new(cls,
            default: bool,
            names: Union[str, List[str], Tuple[str]],
            des: Optional[str] = None) -> Self and bool:
        """
            default 默认值

            names 命名列表，填一个字符串时会自动转换为单字符串列表

            des 描述，为空时默认为命名列表首位
        """
        return cls(default, names, des)  # type: ignore


class Options(StoreSerializable):
    """
        选项解析器
    """

    def __init__(self) -> None:
        self.tag_map: Dict[str, Union[str, List[str], Tuple[str]]] = {}
        self._tag_map: Dict[str, str] = {}
        """tag 映射，请勿覆盖"""
        self._regex = re.compile(r"""^(?:([+-]{0,1}[^+-,\s]+)[,\s]{0,1})+""")
        self._option_regex = re.compile(
            r"""([+-]{0,1}[^+-\,\s]+)[\,\s]{0,1}""")
        for key in self.__class__.__dict__:
            val = self.__class__.__dict__[key]
            if not isinstance(val, Option):
                continue
            self.tag_map[key] = val.names
            setattr(self, key, val.default)

    @property
    def property_tag_map(self):
        """
            获取标签映射，用于解析选项

            {
                tag1: property1,
                tag2: property2,
                ...
            }
        """
        if self._tag_map:
            return self._tag_map
        for key in self.tag_map:
            value = self.tag_map[key]
            if isinstance(value, str):
                self._tag_map[value] = key
            elif isinstance(value, list):
                for v in value:  # type: ignore
                    self._tag_map[v] = key
            else:
                raise BaseException("不受支持的选项配置")
        return self._tag_map

    def __str__(self) -> str:
        msgs = []
        for key in self.__dict__:
            val = self.__dict__[key]
            if isinstance(val, bool) and val and key in self.tag_map:
                tag_val = self.tag_map[key]
                if isinstance(tag_val, str):
                    msgs.append(tag_val)
                elif isinstance(tag_val, list):
                    msgs.append(tag_val[0])
                else:
                    raise BaseException("不受支持的选项配置")

        return "、".join(msgs)

    def set_all(self, bool_val: bool = False):
        for key in self.__dict__:
            val = self.__dict__[key]
            if isinstance(val, bool) and key in self.tag_map:
                self.__dict__[key] = bool_val

    def set_default(self):
        for key in self.__class__.__dict__:
            val = self.__class__.__dict__[key]
            if not isinstance(val, Option):
                continue
            setattr(self, key, val.default)

    def matcher_option_hook(self, key: str, value: bool,
                            source_option: str) -> bool:
        """
            option钩子

            可以针对性处理特定选项，返回True表明拦截默认操作。
        """
        return False

    def matcher_options(self, text: str):
        result = self._regex.match(text)
        if not result:
            return
        result_all: List[str] = self._option_regex.findall(text)
        property_tag_map = self.property_tag_map

        for option in result_all:
            key = option
            value = True
            if not key:
                return

            if option.startswith("-"):
                key = key[1:]
                value = False
            elif option.startswith("+"):
                key = key[1:]

            if option in ("全部", "all", "*"):
                self.set_all(value)
                continue
            elif value and option in ("默认", "重置"):
                self.set_default()
                continue

            if self.matcher_option_hook(key, value, option):
                continue

            if key in property_tag_map:
                key = property_tag_map[key]
                setattr(self, key, value)

    def _serializable(self) -> Dict[str, Any]:
        """
            序列化选项
        """
        save_dict = {}
        for key in self.__dict__:
            val = self.__dict__[key]
            if isinstance(val, bool) and key in self.tag_map:
                save_dict[key] = val
        return save_dict
