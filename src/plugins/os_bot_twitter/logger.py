import nonebot
from typing import TYPE_CHECKING
from .config import __plugin_meta__

from ..os_bot_base.consts import LOGGER_LEVEL_MAP

if TYPE_CHECKING:
    from loguru import Record


def __path(record: "Record"):
    if LOGGER_LEVEL_MAP not in record["extra"]:
        record["extra"][LOGGER_LEVEL_MAP] = {}
    record["extra"][LOGGER_LEVEL_MAP][__plugin_meta__.name] = "INFO"
    record["name"] = __plugin_meta__.name  # type: ignore


logger = nonebot.logger.bind()
logger = logger.patch(__path)
