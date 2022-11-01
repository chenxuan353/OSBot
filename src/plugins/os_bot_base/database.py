"""
    数据库统一初始化中心
"""
from typing import Any, Dict, Optional, Set, Type
import os
from typing_extensions import Self
from nonebot import get_driver
from tortoise import Tortoise
from tortoise.models import Model
from .config import config

driver = get_driver()


class DatabaseManage:
    """
        数据库管理器
    """
    databaseManage: Optional[Self] = None

    def __init__(self) -> None:
        self.base_path: str = os.path.join(config.bb_data_path, "database")
        self.models: Set[str] = set()
        self.db_url: str = f"sqlite://{os.path.join(self.base_path, 'data.sqlite3')}"
        if config.bb_database:
            self.db_url = config.bb_database
        self.__kws: Dict[str, Any] = {
            "db_url": self.db_url,
            "modules": {
                'models': []
            }
        }
        if not os.path.isdir(self.base_path):
            os.makedirs(self.base_path)

    def add_model(self, model: Type[Model]) -> None:
        """
            添加一个model到db模型库中
        """
        self.models.add(model.__module__)

    def add_model_path(self, model: str) -> None:
        """
            添加一个model路径到db模型库中
        """
        self.models.add(model)

    async def _init_(self) -> None:
        """
            启动初始化
        """
        self.__kws['modules']['models'] = list(self.models)
        await Tortoise.init(**self.__kws)
        await Tortoise.generate_schemas(safe=True)

    async def _close_(self) -> None:
        await Tortoise.close_connections()

    @classmethod
    def get_instance(cls) -> Self:
        if not cls.databaseManage:
            cls.databaseManage = cls()
        return cls.databaseManage
