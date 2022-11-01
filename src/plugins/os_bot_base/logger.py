import nonebot
from typing import TYPE_CHECKING
from .consts import BASE_PLUGIN_NAME

if TYPE_CHECKING:
    from loguru import Record


def __path(record: "Record"):
    record["name"] = BASE_PLUGIN_NAME  # type: ignore


logger = nonebot.logger.bind()
logger = logger.patch(__path)
