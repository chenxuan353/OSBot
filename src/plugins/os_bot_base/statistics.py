"""
    # 基础数据服务

    进行简单的运行统计，并自动输出到日志内。

    也提供查看这些数据的功能

    例如 运行时间、处理时间
"""
import asyncio
from dataclasses import dataclass
import json
from time import time
import psutil
from typing import Any, Deque, Dict, List, Optional, Union
from typing_extensions import Self
from dataclasses import dataclass, field
from collections import deque
from nonebot import get_driver, get_bots, on_command
from nonebot.message import run_preprocessor, run_postprocessor, event_preprocessor, event_postprocessor
from nonebot.adapters.onebot import v11, v12
from nonebot.adapters import Event, Bot
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot_plugin_apscheduler import scheduler
from .config import config
from .consts import STATE_STATISTICE_DEAL
from .logger import logger
from .util import seconds_to_dhms, matcher_exception_try, only_command
from .notice import UrgentNotice
from .session import Session, StoreSerializable
from .depends import get_plugin_session

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
    aliases={"数据统计", "数据分析", "数据分析统计", "运行分析"},
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
    logger.info(f"以下消息来自定时任务~\n===[数据分析] 统计信息==="
                f"\n{get_statistics_info()}"
                f"\n{get_statistics_system_info()}")


CHECK_SEND_DISK = "disk"
CHECK_SEND_MEMORY = "memory"
last_check_send = {CHECK_SEND_DISK: 0.0, CHECK_SEND_MEMORY: 0.0}


@scheduler.scheduled_job("interval", minutes=1, name="运行状态检查")
async def statistics_info_check():
    """
        检查内存与磁盘状态
    """
    if config.os_notice_distusage:
        # 两次提醒至少相隔4小时
        if time() - last_check_send[CHECK_SEND_DISK] > 3600 * 4:
            disks = psutil.disk_partitions()
            if config.os_notice_distusage_single:
                for disk in disks:
                    if disk.mountpoint in config.os_notice_distusage_per_igonre:
                        # 忽略排除检查的磁盘
                        continue
                    disk_usage = psutil.disk_usage(disk.mountpoint)
                    if config.os_notice_distusage_percent < 95 and disk_usage.percent > 95:
                        last_check_send[CHECK_SEND_DISK] = time()
                        logger.warning(f"磁盘 {disk.mountpoint} 用量超过95%了哦")
                        await UrgentNotice.send(
                            f"磁盘 {disk.mountpoint} 用量超过95%了哦")
                    elif disk_usage.percent > config.os_notice_distusage_percent:
                        last_check_send[CHECK_SEND_DISK] = time()
                        logger.warning("磁盘 {} 用量超过{}%了哦", disk.mountpoint,
                                       config.os_notice_distusage_percent)
                        await UrgentNotice.send(
                            f"磁盘 {disk.mountpoint} 用量超过{config.os_notice_distusage_percent}%了哦"
                        )

            else:
                disk_usage_totel = 0
                for disk in disks:
                    disk_usage = psutil.disk_usage(disk.mountpoint)
                    disk_usage_totel += disk_usage.percent
                disk_usage_percent = disk_usage_totel / len(disks)
                if config.os_notice_distusage_percent < 95 and disk_usage_percent > 95:
                    last_check_send[CHECK_SEND_DISK] = time()
                    logger.warning("综合磁盘使用量超过95%")
                    await UrgentNotice.send("综合磁盘用量超过95%了哦")
                elif disk_usage_percent > config.os_notice_distusage_percent:
                    logger.warning("综合磁盘使用量超过{}%",
                                   config.os_notice_distusage_percent)
                    last_check_send[CHECK_SEND_DISK] = time()
                    await UrgentNotice.send(
                        f"综合磁盘用量超过{config.os_notice_distusage_percent}%了哦")

        await asyncio.sleep(10)

    if config.os_notice_memoryusage:
        # 两次提醒至少相隔2小时
        if time() - last_check_send[CHECK_SEND_MEMORY] > 3600 * 2:
            memory_use = psutil.virtual_memory().percent
            if config.os_notice_memoryusage_percent < 95 and memory_use > 95:
                last_check_send[CHECK_SEND_MEMORY] = time()
                logger.warning("内存用量超过{}%", 95)
                await UrgentNotice.send(
                    f"内存用量超过{config.os_notice_memoryusage_percent}%了哦")
            elif memory_use > config.os_notice_memoryusage_percent:
                last_check_send[CHECK_SEND_MEMORY] = time()
                logger.warning("内存用量超过{}%",
                               config.os_notice_memoryusage_percent)
                await UrgentNotice.send(
                    f"内存用量超过{config.os_notice_memoryusage_percent}%了哦")


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


@dataclass
class ApiResultUnit(StoreSerializable):
    """
        API调用相关数据

        - `api` 调用的API
        - `result` 请求结果
        - `data` 请求体
        - `exception_str` 异常文本（如果有）
        - `create_time` 创建时间
    """

    api: str = field(default=None)  # type: ignore
    data: str = field(default=None)  # type: ignore
    result: str = field(default=None)  # type: ignore
    exception_str: str = field(default=None)  # type: ignore
    create_time: int = field(default_factory=(lambda: int(time())), init=False)


class ApiCalledSession(Session):
    api_failed_results: List[ApiResultUnit]

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.api_failed_results = []

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)

        # 加载 ban_user_list
        tmp_list: List[Dict[str,
                            Any]] = self.api_failed_results  # type: ignore
        self.api_failed_results = []
        for item in tmp_list:
            unit = ApiResultUnit._load_from_dict(item)  # type: ignore
            self.api_failed_results.append(unit)

        return self

    @classmethod
    def domain(cls) -> Optional[str]:
        """
            域

            覆盖此属性用以增强唯一性，默认使用的域为`nonebot`提供的插件标识符
        """
        return "ApiCalled"


def any_to_str(obj):
    try:
        return str(obj)
    except Exception:
        return f"Type Error:{type(obj)}"


@Bot.on_called_api
async def handle_api_result(bot: Bot, exception: Optional[Exception], api: str,
                            data: Dict[str, Any], result: Any):
    statistics_record.add_api_call_response_time()
    if exception:
        statistics_record.add_api_call_error_count()
        if api in ["send_msg"]:
            if isinstance(exception, v11.ActionFailed):
                exp_result: Dict[str, Any] = exception.info
                UrgentNotice.add_notice(
                    f"API`{api}`异常 {exp_result.get('msg', '未知错误')}")
                session: ApiCalledSession = await get_plugin_session(
                    ApiCalledSession)  # type: ignore
                exception_str = str(exception) if exception is not None else ""
                data_str = json.dumps(data,
                                      ensure_ascii=False,
                                      sort_keys=True,
                                      indent=2,
                                      default=any_to_str)
                result_str = json.dumps(exp_result,
                                        ensure_ascii=False,
                                        sort_keys=True,
                                        indent=2,
                                        default=any_to_str)
                async with session:
                    session.api_failed_results.append(
                        ApiResultUnit(api=api,
                                      data=data_str,
                                      result=result_str,
                                      exception_str=exception_str))


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
