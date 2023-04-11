from dataclasses import asdict, dataclass, field
import random
from typing import Any, Dict, List
from nonebot.matcher import Matcher
from nonebot.params import Depends
from nonebot.permission import SUPERUSER
from nonebot.adapters import Bot, Event
from cacheout import LRUCache
from .token_bucket import AsyncTokenBucket
from ..exception import MatcherErrorFinsh, DependException
from ..adapter import AdapterFactory


@dataclass
class BucketKw:
    num: float
    """令牌发放数量"""
    issuetime: float = field(default=1)
    """发放这些数量需要的时间(s)"""
    initval: float = field(default=0)
    """桶中初始令牌数"""
    capacity: float = field(default=0)
    """桶的最大容量，小于等于0时默认为发放数量"""
    cumulative_time: float = field(default=0)
    """定义从什么时候开始累积令牌，默认当前时间。累积开始前每次成功的取令牌都将清空库存。"""
    cumulative_delay: int = field(default=0)
    """累积延迟，单位秒，当前时间+累积延迟=开始累积的时间，与`cumulative_time`参数二选一。"""


class RateLimitUtil:
    SCOPE_UNIT: str = "SCOPE_UNIT"
    """速率限制应用于用户"""
    SCOPE_PRIVATE: str = "SCOPE_GROUP_PRIVATE"
    """速率限制应用于私聊"""
    SCOPE_GROUP_AND_PRIVATE: str = "SCOPE_GROUP_PRIVATE"
    """速率限制应用于群组或私聊"""
    SCOPE_GROUP: str = "SCOPE_GROUP"
    """速率限制应用于群组"""
    SCOPE_GROUP_UNIT: str = "SCOPE_GROUP_UNIT"
    """速率限制应用于群组成员"""
    SCOPE_HANDLE: str = "SCOPE_HANDLE"
    """速率限制对该响应器有效"""

    @staticmethod
    def QPS(qps: float) -> BucketKw:
        """每秒允许的请求数"""
        return BucketKw(qps, 1, initval=1, capacity=max(qps, 1))

    @staticmethod
    def PER_15M(num: float):
        """每15分钟允许的请求数"""
        return BucketKw(num, 15 * 60, initval=num)

    @staticmethod
    def PER_M(num: float, minutes: float = 1):
        """每x分钟允许的请求数"""
        return BucketKw(num, minutes * 60, initval=num)


def RateLimitDepend(bucket_kw: BucketKw,
                    prompts: List[str] = ["指令超速咯~", "休息一会吧！", "不要滥用指令哦"],
                    scope: str = RateLimitUtil.SCOPE_GROUP_AND_PRIVATE) -> Any:
    """
        动态速率限制（对超级管理员无效）

        bucket_kws 速率限制参数，通过`RateLimitUtil`快速创建
        prompts 提示组，随机选取一条消息回复，为空时不回复消息
        scope 作用范围，默认为群组或私聊
    """
    cache_buckets = LRUCache(maxsize=256, ttl=86400)

    async def _depend(bot: Bot, matcher: Matcher, event: Event):
        if await SUPERUSER(bot, event):
            return
        adapter = AdapterFactory.get_adapter(bot)
        if scope == RateLimitUtil.SCOPE_GROUP_AND_PRIVATE:
            mark = await adapter.mark_group_without_drive(bot, event)
        elif scope == RateLimitUtil.SCOPE_GROUP:
            # 非群组不做处理
            if not await adapter.msg_is_multi_group(bot, event):
                return
            mark = await adapter.mark_group_without_drive(bot, event)
        elif scope == RateLimitUtil.SCOPE_GROUP_UNIT:
            # 非群组不做处理
            if not await adapter.msg_is_multi_group(bot, event):
                return
            mark = await adapter.mark_without_drive(bot, event)
        elif scope == RateLimitUtil.SCOPE_PRIVATE:
            # 非私聊不做处理
            if not await adapter.msg_is_private(bot, event):
                return
            mark = await adapter.mark_without_drive(bot, event)
        elif scope == RateLimitUtil.SCOPE_UNIT:
            mark = await adapter.mark_only_unit_without_drive(bot, event)
        elif scope == RateLimitUtil.SCOPE_HANDLE:
            mark = "func"
        else:
            raise DependException(f"不支持的速率限制范围 {scope}")

        bucket = cache_buckets.get(mark, None)

        if not bucket:
            bucket = AsyncTokenBucket(**asdict(bucket_kw))
            cache_buckets.add(mark, bucket)
        if not await bucket.consume(1):
            if not prompts:
                await matcher.finish()
            prompt = prompts[random.randint(0, len(prompts) - 1)]
            await matcher.finish(prompt)
        return

    return Depends(_depend)
