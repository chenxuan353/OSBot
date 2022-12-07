"""
    进行一些统计

    例如 运行时间、处理时间
"""
import asyncio
from time import time
import psutil
from typing import Any, Deque, Dict, List, Optional, Union
from typing_extensions import Self
from collections import deque
from nonebot import get_driver, get_bots, on_command
from nonebot.message import run_preprocessor, run_postprocessor, event_preprocessor, event_postprocessor
from nonebot.adapters.onebot import v11, v12
from nonebot.adapters import Event, Bot
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot_plugin_apscheduler import scheduler
from .consts import STATE_STATISTICE_DEAL
from .logger import logger
from .util import seconds_to_dhms, matcher_exception_try, only_command
from .notice import UrgentNotice

driver = get_driver()


class StatisticsRecord:
    """
        统计数据

        此数据暂不保存
    """

    instance: Optional[Self] = None

    def __init__(self) -> None:
        self.init_time = time()
        self.startup_time = 0.0
        self.event_count = 0
        self.event_message_count = 0
        self.event_recent_deal_time: Deque[float] = deque(maxlen=1000)
        """
            事件近期的处理时间(仅消息事件)

            仅记录最近1000次处理
        """
        self.matcher_recent_deal_time: Deque[float] = deque(maxlen=1000)
        """
            Matcher近期的处理时间

            仅记录最近1000次处理
        """
        self.api_call_start_time: Deque[float] = deque(maxlen=128)
        """
            Api 请求时间，用于计算平均响应时间
        """
        self.api_call_response_time: Deque[float] = deque(maxlen=1000)
        """
            Api响应时间（仅计算平均时间时有效）

            仅记录最近1000次处理
        """
        self.api_call_error_count = 0
        self.api_call_count = 0
        self.bot_disconnect_count = 0

    def clear_count(self, reason: str):
        logger.warning(f"[数据分析] 清空计数 {reason}")
        self.event_count = 0
        self.event_message_count = 0
        self.api_call_error_count = 0
        self.api_call_count = 0
        self.bot_disconnect_count = 0

    def add_api_call_count(self):
        self.api_call_count += 1
        self.api_call_start_time.append(time())
        if self.api_call_count > 9999999999:
            self.clear_count("Api计数达到上限")

    def add_api_call_error_count(self):
        self.api_call_error_count += 1
        if self.api_call_error_count > 9999999999:
            self.clear_count("Api错误计数达到上限")

    def add_event_count(self):
        self.event_count += 1
        if self.event_count > 9999999999:
            self.clear_count("事件计数达到上限")

    def add_bot_disconnect_count(self):
        self.bot_disconnect_count += 1
        if self.bot_disconnect_count > 9999999999:
            self.clear_count("bot断开计数达到上限")

    def add_event_message_count(self):
        self.event_message_count += 1

    def add_event_deal_time(self, deal_time: float):
        self.event_recent_deal_time.append(deal_time)

    def add_matcher_deal_time(self, deal_time: float):
        self.matcher_recent_deal_time.append(deal_time)

    def add_api_call_response_time(self):
        try:
            start_time = self.api_call_start_time.pop()
            self.api_call_response_time.append(time() - start_time)
        except IndexError:
            pass

    def avg_matcher_deal_ms(self):
        all = 0
        count = 0
        for t in self.matcher_recent_deal_time:
            count += 1
            all += t
        if count == 0:
            return 0
        return all * 1000 / count

    def avg_event_deal_ms(self):
        all = 0
        count = 0
        for t in self.event_recent_deal_time:
            count += 1
            all += t
        if count == 0:
            return 0
        return all * 1000 / count

    def avg_api_call_response_ms(self):
        all = 0
        count = 0
        for t in self.api_call_response_time:
            count += 1
            all += t
        if count == 0:
            return 0
        return all * 1000 / count

    def run_seconds(self):
        return round(time() - self.startup_time, 3)

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance


statistics_record = StatisticsRecord.get_instance()


def get_statistics_info():
    return (
        f"已启动：{seconds_to_dhms(int(statistics_record.run_seconds()))}\n"
        f"活跃Bot计数:{len(get_bots())}\n"
        f"平均事件响应时(近期)：{statistics_record.avg_event_deal_ms():.3f}ms\n"
        f"平均Matcher响应时(近期)：{statistics_record.avg_matcher_deal_ms():.3f}ms\n"
        f"Api平均响应时间(近期):{statistics_record.avg_api_call_response_ms():.3f}ms\n"
        f"事件计数(消息/总数)：{statistics_record.event_message_count}/{statistics_record.event_count}\n"
        f"Api请求 错误数/总计数 (错误率):{statistics_record.api_call_error_count}/{statistics_record.api_call_count} "
        f"({(statistics_record.api_call_error_count/(statistics_record.api_call_count or 1))*100:.5f}%)\n"
        f"Bot断开计数:{statistics_record.bot_disconnect_count}")


statistics_info = on_command(
    "运行数据统计",
    aliases={"数据统计", "数据分析统计"},
    block=True,
    rule=only_command(),
    permission=SUPERUSER,
)


@statistics_info.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: v11.Bot, event: v11.PrivateMessageEvent):
    await matcher.finish(f"数据分析统计>>\n{get_statistics_info()}")


def get_statistics_system_info():
    disks = psutil.disk_partitions()
    disk_usage_str = ""
    for disk in disks:
        disk_usage = psutil.disk_usage(disk.mountpoint)
        disk_usage_str += f"\n  {disk.mountpoint} {disk_usage.percent:.2f}%"

    return (f"系统运行时间：{seconds_to_dhms(int(time() - psutil.boot_time()))}\n"
            f"CPU利用率：{psutil.cpu_percent(interval=1):.2f}%\n"
            f"内存利用率：{psutil.virtual_memory().percent:.2f}%\n"
            f"交换内存利用率：{psutil.swap_memory().percent:.2f}%\n"
            f"磁盘信息：{disk_usage_str}")


statistics_system_info = on_command(
    "系统状态",
    aliases={"系统运行状态", "当前系统状态", "当前系统运行状态", "运行状态"},
    block=True,
    rule=only_command(),
    permission=SUPERUSER,
)


@statistics_system_info.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: v11.Bot, event: v11.PrivateMessageEvent):
    await matcher.finish(f"系统运行状态>>\n{get_statistics_system_info()}")


@scheduler.scheduled_job("interval", minutes=10, name="数据分析输出")
async def print_statistics_info():
    """
        每十分钟输出一次统计信息
    """
    logger.info(f"===[数据分析] 统计信息==="
                f"\n{get_statistics_info()}"
                f"\n{get_statistics_system_info()}")


@scheduler.scheduled_job("interval", minutes=5 * 3600, name="运行状态检查")
async def statistics_info_check():
    disks = psutil.disk_partitions()
    disk_usage_totel = 0
    for disk in disks:
        disk_usage = psutil.disk_usage(disk.mountpoint)
        disk_usage_totel += disk_usage.percent
    disk_usage_percent = disk_usage_totel / len(disks)
    if disk_usage_percent > 90:
        logger.warning("磁盘使用量超过90%")
    if disk_usage_percent > 95:
        logger.warning("磁盘使用量超过95%")
        await UrgentNotice.send("磁盘用量超过95%了哦")

    await asyncio.sleep(10)

    if psutil.virtual_memory().percent > 90:
        await UrgentNotice.send("内存用量超过90%了哦")


@driver.on_startup
async def _():
    """
        NoneBot2 启动时运行
    """
    statistics_record.startup_time = time()
    logger.info("[数据分析] 开始统计数据……")


@driver.on_bot_disconnect
async def _(_: Bot):
    statistics_record.add_bot_disconnect_count()


@Bot.on_calling_api
async def handle_api_call(bot: Bot, api: str, data: Dict[str, Any]):
    statistics_record.add_api_call_count()


@Bot.on_called_api
async def handle_api_result(bot: Bot, exception: Optional[Exception], api: str,
                            data: Dict[str, Any], result: Any):
    statistics_record.add_api_call_response_time()
    if exception:
        statistics_record.add_api_call_error_count()


@event_preprocessor
async def _(_: Event):
    """
        Event 上报到 NoneBot2 时运行
    """
    statistics_record.add_event_count()


@event_preprocessor
async def _(event: Union[v11.MessageEvent, v12.MessageEvent]):
    """
        Event 上报到 NoneBot2 时运行
    """
    statistics_record.add_event_message_count()
    setattr(event, "statistics_deal_time", time())


@run_preprocessor
async def _(matcher: Matcher):
    """
        运行 matcher 前运行
    """
    # 记录运行时间
    matcher.state[STATE_STATISTICE_DEAL] = time()


@run_postprocessor
async def _(matcher: Matcher):
    """
        运行 matcher 后运行
    """
    start_time: Optional[float] = matcher.state.get(STATE_STATISTICE_DEAL)
    if start_time:
        statistics_record.add_matcher_deal_time(time() - start_time)


@event_postprocessor
async def _(event: Union[v11.MessageEvent, v12.MessageEvent]):
    """
        NoneBot2 处理 Event 后运行

        运行matcher之后
    """
    if hasattr(event, "statistics_deal_time"):
        statistics_record.add_event_deal_time(
            time() - getattr(event, "statistics_deal_time"))
