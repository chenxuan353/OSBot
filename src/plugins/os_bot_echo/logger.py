import nonebot
from typing import TYPE_CHECKING
from .config import __plugin_meta__

if TYPE_CHECKING:
    from loguru import Record


def __path(record: "Record"):
    record["name"] = __plugin_meta__.name  # type: ignore


logger = nonebot.logger.bind()
logger = logger.patch(__path)
