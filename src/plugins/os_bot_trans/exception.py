class EngineError(Exception):
    """
        引擎错误的基类
    """

    def __init__(self, *args: object, replay: str = "引擎错误，请联系维护者！") -> None:
        super().__init__(*args)
        self._replay = replay

    @property
    def replay(self) -> str:
        return self._replay


class InitError(Exception):
    """
        插件初始化错误
    """
    pass
