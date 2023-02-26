import abc
import re
from typing import Dict, List, Optional, Union
from ..langs import langs
from ..exception import EngineError
from ..emoji_filter import EmojiFilter
from loguru import logger

BASE_LANGUAGE_LIST = langs


def tool_reverse_dict(d: dict):
    """
        反向字典映射，最后声明的映射会将之前的声明覆盖
        {
            a:[a1,b1,c1],
            b:[b1]
        }=>{
            a1:a,
            b1:b,
            c1:a
        }
    """
    res = {}
    for k in d.keys():
        res[k] = k
        if type(d[k]) is list:
            for v in d[k]:
                res[v] = k
        else:
            res[res[k]] = k
    return res


class Engine(abc.ABC):
    """
        引擎基类及基准配置
        只有匹配了BASE_LANGUAGE的语言参数
        会使用check_lang及conversion_lang方法进行进一步转换
        转换完成后将调用trans函数
        例-腾讯引擎:
            allow_dict={"zh-cn":["zh-tw"]}
            change_list={ "zh-cn":"cn" }
            用户参数：简体 繁体
            (简体 繁体)->text_check->BASE_LANGUAGE转换为(zh-cn zh-tw)->在allow列表中->change_list转换为(cn zh-TW)->调用trans函数
    """
    BASE_LANGUAGE = tool_reverse_dict(BASE_LANGUAGE_LIST)

    def __init__(self, name: str, enable: bool,
                 allow_dict: Dict[str, Union[List[str], str]],
                 change_dict: Dict[str, str], alias: List[str]) -> None:
        """
            `name` 引擎名称

            `enable` 引擎是否启用

            `allow_dict` 支持的语言及语言支持翻译到的语言

            `change_list` 语言的识别名修正

            `alias` 引擎的别名列表
        """
        self.enable = enable
        self._name = name
        self._alias = alias if alias else list()
        self._allow_dict = allow_dict
        self._change_dict = change_dict

    def check_source_lang(self, source) -> bool:
        """
            检查源语言是否有效
        """
        return source in self._allow_dict

    def check_lang(self, source, target) -> bool:
        """
            检查源语言是否有效及源语言是否允许转换到目标语言
        """
        return self.check_source_lang(
            source) and target in self._allow_dict[source]

    def conversion_lang(self, lang: str) -> str:
        """
            语言标识转换函数

            用于适配不同引擎语言标识的不同
        """
        if lang in self.change_dict:
            return self.change_dict[lang]
        return lang

    @abc.abstractmethod
    async def trans(self, source: str, target: str, content: str) -> str:
        raise NotImplementedError

    def text_check(self, content: str) -> Optional[str]:
        """
            待翻译文本检查
            检查不通过返回不通过原因
            该原因文本会发送给用户
            返回None则表示检查通过
        """
        return None

    @property
    def name(self):
        return self._name

    @property
    def alias(self):
        return self._alias

    @property
    def allow_dict(self):
        return self._allow_dict

    @property
    def change_dict(self):
        return self._change_dict

http_match = re.compile(r'(((http|ftp|https):\/{2})?(([0-9a-z_-]+\.)+(aero|asia|biz|cat|com|coop|edu|gov|info|int|jobs|mil|mobi|museum|name|net|org|pro|tel|travel|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cu|cv|cx|cy|cz|cz|de|dj|dk|dm|do|dz|ec|ee|eg|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mn|mn|mo|mp|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|nom|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ra|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|sj|sk|sl|sm|sn|so|sr|st|su|sv|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw|arpa)(:[0-9]{1,5})?(\/(([~0-9a-zA-Z\#\+\%@\.\/_-]+))?(\?[0-9a-zA-Z\+\%@\/&\[\];=_-]+)?)?))', re.I)


def deal_trans_text(text):
    """
        移除翻译字符串中可能影响翻译结果的内容。
    """
    text = http_match.sub(' ', text)  # 移除网址
    text = text.strip()  # 移除空白字符串
    text = EmojiFilter.filter(text)  # 移除emoji
    return text
