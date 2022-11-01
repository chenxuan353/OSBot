from typing import Optional


class BaseException(Exception):
    """
        基础异常

        当提供cause时，打印时会将异常信息附加至消息尾部。
    """

    def __init__(self, info: str, cause: Optional[Exception] = None) -> None:
        super().__init__()
        self.info: str = info
        self.cause: Optional[Exception] = cause

    def __str__(self) -> str:
        if self.cause:
            return f"{self.info} - ({type(self.cause).__name__}) {self.cause}"
        return f"{self.info}"


class StoreException(BaseException):
    """
        存储异常
    """


class AdapterException(BaseException):
    """
        适配器异常
    """


class InfoCacheException(BaseException):
    """
        信息缓存异常
    """


class MatcherErrorFinsh(BaseException):
    """
        Matcher错误消息

        应当触发错误提示
    """
