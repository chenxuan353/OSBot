from typing import Optional

from ..os_bot_base.exception import BaseException as OSBotBaseException, MatcherErrorFinsh


class BaseException(OSBotBaseException):
    """
        基础异常

        当提供cause时，打印时会将异常信息附加至消息尾部。
    """
