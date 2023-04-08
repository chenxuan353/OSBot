from typing import Optional
from nonebot.adapters import Message
from nonebot.rule import Rule
from nonebot.params import CommandArg
from .token_bucket import AsyncTokenBucket
from ..exception import MatcherErrorFinsh


def only_command():
    """
        匹配无参数命令
    """

    async def checker(msg: Message = CommandArg()) -> bool:
        return not msg

    return Rule(checker)


class RateLimitRule:

    def __init__(self, unit_bucket: Optional[AsyncTokenBucket],
                 group_limit: Optional[AsyncTokenBucket],
                 plugin_limit: Optional[AsyncTokenBucket]) -> None:
        self.unit_bucket = unit_bucket
        self.group_limit = group_limit
        self.plugin_limit = plugin_limit

    @staticmethod
    def generate_bucket():
        return AsyncTokenBucket(30, 86400, initval=30)

def rate_limit(limit: int, plugin_limit: int = 0, unit_limit: int = 0):
    """
        进行QPS限制

        
    """
    
