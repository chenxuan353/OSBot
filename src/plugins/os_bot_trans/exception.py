from ..os_bot_base.exception import MatcherErrorFinsh, BaseException as OSBotBaseException

class BaseException(OSBotBaseException):
    pass


class RatelimitException(MatcherErrorFinsh):
    """
        速率限制
    """


class EngineError(MatcherErrorFinsh):
    """
        引擎错误的基类
    """

    def __init__(self, *_: object, replay: str = "引擎错误，请联系维护者！") -> None:
        super().__init__(info=replay)
        self._replay = replay

    @property
    def replay(self) -> str:
        return self._replay


class InitError(BaseException):
    """
        插件初始化错误
    """
    pass
