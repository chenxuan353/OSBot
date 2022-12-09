import asyncio
from collections import deque
from functools import wraps
from typing import Any, Awaitable, Callable, Coroutine, Deque, Dict, Optional, Tuple, Union
from time import time
import math
from ..logger import logger
from ..exception import QueueFullException




class AsyncWaitQueue:

    def __init__(self,
                 concurrent: int = 1,
                 queue_size: int = 5,
                 name: str = "") -> None:
        """
            concurrent  并行处理数
            queue_size  队列大小
            name  处理循环名称（用于日志记录）
        """
        if concurrent <= 0:
            concurrent = 1
        if queue_size <= 0:
            queue_size = 1
        self.name = name or f"{int(time())}"
        self.concurrent = concurrent
        self.queue_size = queue_size
        self.queue_status: Dict[Union[str, int], bool] = {}
        """队列状态，true忙碌false空闲"""
        self.queue: asyncio.Queue[Awaitable] = asyncio.Queue(self.queue_size)
        self.statistics: Deque[float] = deque(maxlen=100)  # 统计千次内的平均时间，计算等待时间。
        self.future: Optional[asyncio.Future] = None

    def avg_deal_ms(self):
        all = 0
        count = 0
        for t in self.statistics:
            count += 1
            all += t
        if count == 0:
            return 0
        return all * 1000 / count

    async def _deal_loop(self, deal_num: Union[str, int]):
        """
            处理循环

            deal_num 处理序号
        """
        logger.debug("处理循环 {}-{} 启动", self.name, deal_num)
        self.queue_status[deal_num] = False
        while True:
            try:
                asyncfunc = await self.queue.get()
                self.queue_status[deal_num] = True
                logger.debug(
                    f"处理循环 {{}}-{{}} 取得了一个任务 剩余 {{}}", self.name, deal_num, self.queue.qsize())
                start_time = time()
                await asyncfunc
                deal_time = time() - start_time
                logger.debug(
                    f"处理循环 {{}}-{{}} 处理了一个任务 耗时{deal_time:.2f}s  剩余队列 {{}}",
                    self.name, deal_num, self.queue.qsize())
                self.statistics.append(deal_time)
                self.queue_status[deal_num] = False
                self.queue.task_done()
            except Exception as e:
                logger.opt(exception=True).error("处理循环异常！")
    def wrapper_submit(self, func: Callable[..., Coroutine]):
        """
            自动提交返回可等待对象的装饰器
        """

        @wraps(func)
        def wrap(*args, **kws):
            loop = asyncio.get_event_loop()
            waiter: asyncio.Future = loop.create_future()

            async def callback():
                try:
                    waiter.set_result(await func(*args, **kws))
                except Exception as e:
                    waiter.set_exception(e)

            await_func = callback()
            try:
                self.queue.put_nowait(await_func)
                return waiter
            except asyncio.QueueFull as e:
                await_func.close()
                raise QueueFullException("队列已满", cause=e)

        return wrap

    def submit(
            self, func: Coroutine[Any, Any,
                                  Any]) -> Tuple[asyncio.Future, int, float]:
        """
            提交任务

            返回值 可等待对象，需等待的队伍数量，预计等待时间
            异常 QueueFullException
        """
        loop = asyncio.get_event_loop()
        waiter: asyncio.Future = loop.create_future()

        async def callback():
            try:
                waiter.set_result(await func)
            except Exception as e:
                waiter.set_exception(e)

        await_func = callback()
        try:
            self.queue.put_nowait(await_func)
            queue_size = self.queue.qsize() or 1
            wait_time = self.avg_deal_ms(
            ) / 1000 * math.ceil(queue_size / self.concurrent)
            return waiter, queue_size - 1, wait_time
        except asyncio.QueueFull as e:
            await_func.close()
            func.close()
            raise QueueFullException("队列已满", cause=e)

    async def startup(self):
        """启动"""
        if self.future:
            self.future.cancel()
        coroutines = []
        for i in range(self.concurrent):
            coroutines.append(self._deal_loop(i + 1))
        self.future = asyncio.gather(*coroutines)

    async def restart(self):
        """重启"""
        await self.startup()

    async def close(self):
        """关闭"""
        if self.future:
            self.future.cancel()
            self.future = None

    async def get_free_loop_count(self) -> int:
        count = 0
        for key in self.queue_status:
            if not self.queue_status[key]:
                count += 1

        return count
