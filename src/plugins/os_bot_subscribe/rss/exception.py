
from typing import Optional
from ...exception import BaseException


class RssRequestStatusError(BaseException):
    """
        Rss请求异常（状态码不正确）
    """


class RssRequestFailure(BaseException):
    """
        Rss请求失败（超时、网络异常等）
    """


class RssParserError(BaseException):
    """
        Rss解析异常
    """
    pass
