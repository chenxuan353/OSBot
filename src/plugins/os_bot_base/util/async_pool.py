import asyncio
from asyncio.futures import Future
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import Future as ThreadFuture
from typing import Awaitable, Callable, Tuple, Union


class AsyncPool:
    """
        线程池或进程池的异步封装
    """

    def __init__(self, pool: Union[ProcessPoolExecutor,
                                   ThreadPoolExecutor]) -> None:
        self._pool = pool

    def _pkg_callback(self) -> Tuple[Awaitable, Callable]:
        loop = asyncio.get_event_loop()
        waiter: Future = loop.create_future()

        def poolrun(thread_future: ThreadFuture):

            async def setRes(waiter: Future, thread_future: ThreadFuture):
                exp = thread_future.exception()
                if exp:
                    waiter.set_exception(
                        thread_future.exception())  # type: ignore
                    return
                waiter.set_result(thread_future.result())

            asyncio.run_coroutine_threadsafe(setRes(waiter, thread_future),
                                             loop)

        return waiter, poolrun

    def submit(self, fn, *args, **kws) -> Awaitable:
        thread_future = self._pool.submit(fn, *args, **kws)
        waiter, call_back = self._pkg_callback()
        thread_future.add_done_callback(call_back)
        return waiter


class AsyncPoolSimple:
    """
        线程池或进程池的简单异步封装
    """

    def __init__(self, pool: Union[ProcessPoolExecutor,
                                   ThreadPoolExecutor]) -> None:
        self._pool = pool

    async def _wait(self, thread_future: ThreadFuture):
        while not thread_future.done():
            await asyncio.sleep(0.05)
        e = thread_future.exception()
        if e:
            raise e
        return thread_future.result()

    def submit(self, fn, *args, **kws) -> Future:
        f = self._pool.submit(fn, *args, **kws)
        return self._wait(f)  # type: ignore
