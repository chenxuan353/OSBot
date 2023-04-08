"""
    # 限速
"""
import time
import asyncio
from ..exception import BaseException


class TokenBucketException(BaseException):
    """
        令牌桶异常
    """


class TokenBucketTimeout(TokenBucketException):
    """
        异步获取令牌等待超时
    """


class TokenBucketInitError(TokenBucketException):
    """
        令牌初始化异常
    """


class TokenBucket(object):
    r"""
        令牌桶算法

        修改自 https://juejin.im/post/5ab10045518825557005db65
    """

    def __init__(self,
                 num: float,
                 issuetime: float = 1,
                 initval: float = 0,
                 capacity: float = 0,
                 cumulative_time: float = 0,
                 cumulative_delay: int = 0):
        """
            num: float 发放数量

            issuetime: float 发放这些数量需要的时间(s)

            initval: float 桶中初始令牌数

            capacity: float 桶的最大容量，默认为发放数量

            cumulative_time: float 定义从什么时候开始累积令牌，默认当前时间。累积开始前每次成功的取令牌都将清空库存。

            cumulative_delay: int 累积延迟，单位秒，当前时间+累积延迟=开始累积的时间，与`cumulative_time`参数二选一。
        """
        self._rate = num * 1.0 / issuetime
        self._num = num
        self._issuetime = issuetime
        if capacity <= 0:
            self._capacity = num
        else:
            self._capacity = capacity
        if initval < 0 or initval > self._capacity:
            raise TokenBucketInitError("initval参数无效，必须小于等于桶容量且大于0！")
        # 当前剩余令牌数量
        self._current_amount = initval
        # 最近一次发放时间
        self._last_consume_time = time.time()

        if cumulative_time <= 0:
            cumulative_time = time.time()
            if cumulative_delay > 0:
                cumulative_time += cumulative_delay

        self._cumulative_time = cumulative_time

    # token_amount是发送数据需要的令牌数
    def _consume(self, token_amount: int = 1, take_token: bool = True) -> bool:
        now_time = time.time()
        increment = (now_time - self._last_consume_time
                     ) * self._rate  # 计算从上次发送到这次发送，新发放的令牌数量
        # print(F"increment:{increment} | current_amount:{self._current_amount} | last_consume_time:{self._last_consume_time}")
        self._current_amount = min(increment + self._current_amount,
                                   self._capacity)  # 令牌数量不能超过桶的容量
        self._last_consume_time = now_time
        if token_amount > self._current_amount:  # 如果没有足够的令牌，则不能发送数据
            return False
        if take_token:
            if self._cumulative_time > now_time:
                self._current_amount = 0
            else:
                self._current_amount -= token_amount
        return True

    def canConsume(self, token_amount: int = 1) -> bool:
        """
            判断令牌余量是否充足

            token_amount: int 需要的令牌数量
        """
        return self._consume(token_amount, take_token=False)

    def consume(self, token_amount: int = 1) -> bool:
        """
            获取令牌

            token_amount: int 需要的令牌数量
        """
        return self._consume(token_amount, take_token=True)


class AsyncTokenBucket(TokenBucket):
    r"""
        令牌桶算法的异步实现
    """

    def __init__(self,
                 num: float,
                 issuetime: float = 1,
                 initval: float = 0,
                 capacity: float = 0,
                 cumulative_time: float = 0,
                 cumulative_delay: int = 0):
        super().__init__(num, issuetime, initval, capacity, cumulative_time,
                         cumulative_delay)

    async def consume(self, token_amount: int = 1) -> bool:
        return super().consume(token_amount=token_amount)

    async def canConsume(self, token_amount: int = 1) -> bool:
        return super().canConsume(token_amount=token_amount)

    async def _wait_consume(self, token_amount: int = 1) -> bool:
        while True:
            if super().consume(token_amount):
                return True
            await asyncio.sleep(0.05)

    async def wait_consume(self,
                           token_amount: int = 1,
                           timeout: float = 15) -> bool:
        """
            等待令牌成功获取

            超时返回False

            token_amount: int 需要的令牌数量

            timeout: float 超时时间(s)
        """
        if timeout <= 0:
            return await self._wait_consume(token_amount)
        try:
            return await asyncio.wait_for(self._wait_consume(token_amount),
                                          timeout=timeout)
        except TimeoutError:
            return False
