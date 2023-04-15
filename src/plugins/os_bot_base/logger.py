"""
    # 日志储存

    支持日志存储，会将日志输出至数据文件夹(默认`./data`)中的`log`目录中

    仅保留十五天内的日志
"""
import logging
import sys
import os
import nonebot
from nonebot import get_driver
from nonebot.log import LoguruHandler as NbLoguruHandler

from typing import TYPE_CHECKING
from pydantic import BaseSettings, Field

from .consts import BASE_PLUGIN_NAME, LOGGER_LEVEL_MAP

if TYPE_CHECKING:
    from loguru import Record


class Config(BaseSettings):
    os_data_path: str = Field(default=os.path.join(".", "data"))
    os_log_file_debug: bool = Field(default=False)
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
                                                      "log", "info.log"),
                                         level=nonebot.logger.level("INFO").no,
                                         diagnose=False,
                                         format=default_format,
                                         rotation="3:00",
                                         retention='15 days',
                                         compression="zip")
logger_file_warning_id = nonebot.logger.add(
    os.path.join(config.os_data_path, "log", "warning.log"),
    level=nonebot.logger.level("WARNING").no,
    diagnose=False,
    format=default_format,
    retention='15 days',
    rotation="3:00",
    compression="zip")
logger_file_error_id = nonebot.logger.add(
    os.path.join(config.os_data_path, "log", "error.log"),
    level=nonebot.logger.level("ERROR").no,
    diagnose=False,
    format=default_format,
    retention='15 days',
    rotation="3:00",
    compression="zip")

if config.os_log_file_debug or config.log_level == "DEBUG":
    logger_file_debug_id = nonebot.logger.add(
        os.path.join(config.os_data_path, "log", "debug.log"),
        level=nonebot.logger.level("DEBUG").no,
        diagnose=False,
        format=default_format,
        rotation="3:00",
        retention='15 days',
        compression="zip")

logger = nonebot.logger.bind()
logger = logger.patch(__path)


class LoguruHandler(logging.Handler):  # pragma: no cover
    """logging 与 loguru 之间的桥梁，将 logging 的日志转发到 loguru。"""

    def emit(self, record: logging.LogRecord):
        try:
            level = nonebot.logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        record.name
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        nonebot.logger.opt(depth=depth,
                   exception=record.exc_info).log(level, record.getMessage())


def __emit(self, record: logging.LogRecord):
    pass


NbLoguruHandler.emit = __emit

# 将logging中的日志转发至loguru(Info及以上)
logging.basicConfig(handlers=[LoguruHandler()], level=logging.INFO)
