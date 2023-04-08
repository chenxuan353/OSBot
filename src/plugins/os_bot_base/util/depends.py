from typing import Any
from nonebot.matcher import Matcher
from nonebot.params import Depends
from nonebot.adapters import Bot, Event, Message
from .token_bucket import AsyncTokenBucket
from ..exception import MatcherErrorFinsh


def RateLimitDepend(bucket: AsyncTokenBucket, prompt: str = "操作太频繁了哦，休息一会吧！") -> Any:
    """
        速率限制

        bucket 速率限制容器
        prompt 提示
    """

    async def _depend(bot: Bot, matcher: Matcher, event: Event):
        if not await bucket.consume(1):
            await matcher.finish(prompt)
        return 

    return Depends(_depend)

class RateLimitRule:
    @staticmethod
    def QPS(qps: float):
        """每秒允许的请求数"""
        return AsyncTokenBucket(qps, 1, initval=1, capacity=max(qps, 1))

    @staticmethod
    def PER_DAY(num: int):
        """每天允许的请求数"""
        return AsyncTokenBucket(num, 86400, initval=num)

    @staticmethod
    def PER_15M(num: int):
        """每15分钟允许的请求数"""
        return AsyncTokenBucket(num, 15*60, initval=num)

    @staticmethod
    def PER_M(num: int, minutes: float = 1):
        """每x分钟允许的请求数"""
        return AsyncTokenBucket(num, minutes*60, initval=num)
