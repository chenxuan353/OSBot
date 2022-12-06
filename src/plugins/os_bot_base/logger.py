import sys
import os
import nonebot
from nonebot import get_driver

from typing import TYPE_CHECKING
from pydantic import BaseSettings, Field

from .consts import BASE_PLUGIN_NAME, LOGGER_LEVEL_MAP

if TYPE_CHECKING:
    from loguru import Record


class Config(BaseSettings):
    os_data_path: str = Field(default=os.path.join(".", "data"))
    log_level: str = Field(default="INFO")

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())


def __path(record: "Record"):
    record["name"] = BASE_PLUGIN_NAME  # type: ignore


def default_filter(record: "Record"):
    """默认的日志过滤器，根据 `config.log_level` 配置改变日志等级。"""
    log_level = record["extra"].get("nonebot_log_level", "INFO")
    if record["extra"].get(LOGGER_LEVEL_MAP, {}).get(record["name"], None):
        log_level = record["extra"].get(LOGGER_LEVEL_MAP,
                                        {}).get(record["name"], "INFO")
    levelno = logger.level(log_level).no if isinstance(log_level,
                                                       str) else log_level
    if record["name"] == "apscheduler":
        # 过滤所有aps的日志
        return False
    return record["level"].no >= levelno


default_format: str = (
    "<g>{time:MM-DD HH:mm:ss}</g> "
    "[<lvl>{level}</lvl>] "
    "<c><u>{name}</u></c> | "
    # "<c>{function}:{line}</c>| "
    "{message}")
"""默认日志格式"""

nonebot.logger.remove()
logger_id = nonebot.logger.add(
    sys.stdout,
    level=0,
    diagnose=False,
    filter=default_filter,
    format=default_format,
)
logger_file_info_id = nonebot.logger.add(os.path.join(config.os_data_path,
                                                      "log",
                                                      "info.log"),
                                         level=nonebot.logger.level("INFO").no,
                                         diagnose=False,
                                         format=default_format,
                                         rotation="3:00",
                                         compression="zip")
logger_file_warning_id = nonebot.logger.add(
    os.path.join(config.os_data_path, "log", "warning.log"),
    level=nonebot.logger.level("WARNING").no,
    diagnose=False,
    format=default_format,
    rotation="3:00",
    compression="zip")
logger_file_error_id = nonebot.logger.add(
    os.path.join(config.os_data_path, "log", "error.log"),
    level=nonebot.logger.level("ERROR").no,
    diagnose=False,
    format=default_format,
    rotation="3:00",
    compression="zip")

if config.log_level == "DEBUG":
    logger_file_debug_id = nonebot.logger.add(
        os.path.join(config.os_data_path, "log", "debug.log"),
        level=nonebot.logger.level("DEBUG").no,
        diagnose=False,
        format=default_format,
        rotation="3:00",
        compression="zip")

logger = nonebot.logger.bind()
logger = logger.patch(__path)
