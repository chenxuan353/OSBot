import os
from nonebot import get_driver
from enum import Enum
from pydantic import BaseSettings, Field


class DriveEnum(str, Enum):
    file = "file"
    database = 'database'


class Config(BaseSettings):
    """
        # 基础配置

        - `bb_data_path` 基础数据路径
        - `bb_database` 数据库地址，默认使用sqlite3，规范为sql数据库规范。
        - `bb_session_save_model` session存储方式 支持：file(本地json)、database(使用db服务)
        - `bb_session_timeout` session超时时间（分钟），超过此时间未被调用将自动回收，小于1时视为关闭。
    """
    bb_data_path: str = Field(default=os.path.join(".", "data"))
    bb_database: str = Field(default="")
    bb_session_save_model: DriveEnum = DriveEnum.file
    bb_session_timeout: int = Field(default=300)

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())
