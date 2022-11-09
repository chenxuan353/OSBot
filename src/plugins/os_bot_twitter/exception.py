from typing import Optional
from ..os_bot_base.exception import BaseException as OS_BaseException
from ..os_bot_base.exception import MatcherErrorFinsh


class BaseException(OS_BaseException):
    """
        基础异常

        当提供cause时，打印时会将异常信息附加至消息尾部。
    """


class RatelimitException(MatcherErrorFinsh):
    """
        速率限制
    """


class TwitterException(BaseException):
    """
        一些推特异常
    """


class TwitterPollingError(BaseException):
    """
        推特轮询错误
    """


class TwitterPollingSendError(BaseException):
    """
        推送错误
    """


class TwitterDatabaseException(BaseException):
    """
        数据库异常

        出现此异常可能意味着需要暂时停止推送服务
    """
