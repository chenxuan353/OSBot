import os
import re
import codecs
from .config import config
from .logger import logger
from .exception import BaseException


class EmojiFilter:
    """
        Emoji过滤器
    """
    regex = None

    @classmethod
    def load(cls) -> None:
        if not os.path.isfile(config.trans_emoji_filter_file):
            raise BaseException(f"加载emoji过滤的正则表达式失败，emoji规则文件不存在:{config.trans_emoji_filter_file}")
        try:
            with codecs.open(config.trans_emoji_filter_file, 'r', encoding='utf8') as f:
                pat = f.readline()
                cls.regex = re.compile(pat, flags=re.UNICODE)
                logger.info("加载了emoji正则表达过滤 表达式长度 {}", len(pat))
        except Exception as e:
            raise BaseException("加载emoji过滤的正则表达式失败", cause=e)

    @classmethod
    def filter(cls, text: str) -> str:
        if not cls.regex:
            cls.load()
        if not cls.regex:
            logger.warning("过滤emoji失败，正则表达式为空！")
            return text
        return cls.regex.sub("", text)

EmojiFilter.load()
