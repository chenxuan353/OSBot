import nonebot
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Record


def __path(record: "Record"):
    record["name"] = "B站"  # type: ignore


logger = nonebot.logger.bind()
logger = logger.patch(__path)
