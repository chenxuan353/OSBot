import asyncio
import random
from time import localtime, strftime, time
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Self
from nonebot import get_driver
from nonebot.adapters.onebot import v11
from nonebot_plugin_apscheduler import scheduler
from cacheout import Cache
from cacheout.memoization import memoize
from itertools import cycle

from .subchannel import RsshubChannel, RsshubChannelSession, SubscribeInfoData

from ...utils.rss import RssChannelData
from ..factory import channel_factory
from ...model import SubscribeModel
from ...logger import logger
from ...exception import BaseException
from .config import config

from ....os_bot_base.util import seconds_to_dhms, inhibiting_exception
from ....os_bot_base.depends import get_plugin_session
from ....os_bot_base import Session

driver = get_driver()


class RsshubPollSession(Session):

    channel_enables: Dict[str, bool]
    """频道启用状态 channel_id->enable"""
    subscribe_update_timestamps: Dict[str, int]
    """订阅更新时间戳 channel_id_subscribe->timestamps"""
    _channel_data: Dict[str, RssChannelData]
    """频道缓存数据 channel_id_subscribe->RssChannelData"""

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.channel_enables = {}
        self.subscribe_update_timestamps = {}
        self._channel_data = {}

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        return self

    def enable_channel(self, channel: RsshubChannel):
        self.channel_enables[channel.channel_id] = True

    def disable_channel(self, channel: RsshubChannel):
        self.channel_enables[channel.channel_id] = False

    def is_enable_channel(self, channel: RsshubChannel):
        return self.channel_enables.get(channel.channel_id, True)

    async def _unlock(self) -> None:
        await self._session_manage._hook_session_activity(self.key)


@memoize(maxsize=256)
async def _model_get_listeners(channel_subtype: str) -> List[str]:
    return await SubscribeModel.filter(
        channel_type=RsshubChannel._CHANNEL_TYPE,
        channel_subtype=channel_subtype,
    ).only("subscribe").distinct().values_list("subscribe",
                                               flat=True)  # type: ignore


@memoize(maxsize=256)
async def _model_get_listeners_map(
        channel_subtype: str) -> Dict[str, List[SubscribeModel]]:
    subscribes = await SubscribeModel.filter(
        channel_type=RsshubChannel._CHANNEL_TYPE,
        channel_subtype=channel_subtype,
    )
    listeners_map: Dict[str, List[SubscribeModel]] = {}

    for sub in subscribes:
        if sub.subscribe not in listeners_map:
            listeners_map[sub.subscribe] = []
        listeners_map[sub.subscribe].append(sub)

    return listeners_map


def rsshub_subscribe_invalid_cache():
    cache: Cache = _model_get_listeners.cache
    cache.clear()
    cache: Cache = _model_get_listeners_map.cache
    cache.clear()


def rsshub_subscribe_invalid_subtype_cache(channel_subtype: str):
    key = _model_get_listeners.cache_key(channel_subtype)
    _model_get_listeners.cache.delete(key)
    key = _model_get_listeners_map.cache_key(channel_subtype)
    _model_get_listeners_map.cache.delete(key)


"""
    RSShub轮询方式

    每个频道单独轮询，按照频道设计的轮询间隔进行

    更新逻辑，基于RSS发布时间及更新时间戳

    rss发布时间更新且
"""


@driver.on_startup
async def _():
    if not config.os_subscribe_rsshub_enable:
        logger.info("Rsshub订阅已关闭")
        return
    urls = config.os_subscribe_rsshub_urls
    if not urls:
        raise BaseException("Rsshub订阅必须提供至少一个订阅源地址")

    logger.debug("Rsshub初始化...")

    channel_subtype_map = channel_factory.get_by_type(
        RsshubChannel._CHANNEL_TYPE)

    session: RsshubPollSession = await get_plugin_session(RsshubPollSession
                                                          )  # type: ignore
    await session._lock()

    @inhibiting_exception()
    async def pool_loop(channel: RsshubChannel):
        logger.debug("Rsshub轮询启动 {} 的总订阅数 {}", channel.name,
                     len(await _model_get_listeners(channel.channel_subtype)))
        RssCls = channel.rss_cls

        url_cycle = cycle(urls)
        channel_session: RsshubChannelSession = await channel.get_session(
        )  # type: ignore
        await channel_session._lock()

        while True:
            start_time = time()

            listeners = await _model_get_listeners(channel.channel_subtype)
            listener_maps = await _model_get_listeners_map(
                channel.channel_subtype)

            if len(listeners) > 5:
                logger.debug("Rsshub轮询开始")

            for listener in listeners:
                if not session.is_enable_channel(channel):
                    await asyncio.sleep(15)
                    continue
                if not listener_maps.get(listener, None):
                    logger.warning("{} 订阅 {} 未绑定推送，跳过更新", channel.channel_id,
                                   listener)
                    continue
                try:
                    now_url = next(url_cycle)

                    rss = RssCls(now_url,
                                 channel.subscribe_to_rsshub_path(
                                     listener, channel_session),
                                 source_type=channel.channel_type,
                                 source_subtype=channel.channel_subtype)

                    logger.debug("{}-{} Rsshub轮询请求 {}", channel.channel_type,
                                 channel.channel_subtype, rss.url)

                    # 读取
                    channel_data = await rss.read()
                    cache_key = f"{channel.channel_id}_{listener}"

                    # 获取更新
                    subscribe_last_update_timestamp = session.subscribe_update_timestamps.get(
                        cache_key, 0)

                    if cache_key in session._channel_data:
                        # 更新推送
                        if channel_data.updated < session._channel_data[
                                cache_key].updated:
                            """发布时间小于上一次获取时间时拒绝使用此次更新信息"""
                            # logger.debug(
                            #     "{}-{} 发布时间小于上次更新 该数据已忽略 更新来源 - {}",
                            #     channel.channel_id, listener,
                            #     session._channel_data[cache_key].source_url)
                            continue
                        await channel.polling_update(
                            listener_maps[listener],
                            session._channel_data[cache_key], channel_data,
                            subscribe_last_update_timestamp,
                            session.subscribe_update_timestamps[cache_key])

                    session.subscribe_update_timestamps[cache_key] = int(
                        time() * 1000)

                    # 缓存结果
                    session._channel_data[cache_key] = channel_data

                    # 缓存用于快速查询的内容
                    info = SubscribeInfoData(title=channel_data.title_full,
                                             des=channel_data.des_full)
                    channel_session.set_subscribe_info(channel, listener, info)

                except BaseException as e:
                    logger.warning("{}-{} 轮询请求失败:{}", channel.channel_type,
                                   channel.channel_subtype, str(e))
                except Exception as e:
                    logger.opt(exception=True).error("轮询中发生意外的报错")
                await asyncio.sleep(
                    max(random.randint(*channel.poll_interval) / len(urls) / 1000, 0.01))

            await channel_session.save()
            end_time = time()
            if len(listeners) > 10:
                logger.info("Rsshub轮询完成 共 {} 订阅，耗时 {}", len(listeners),
                            seconds_to_dhms(end_time - start_time))
            elif len(listeners) > 5:
                logger.debug("Rsshub轮询完成 共 {} 订阅，耗时 {}", len(listeners),
                             seconds_to_dhms(end_time - start_time))
            if len(listeners) <= 3:
                await asyncio.sleep(5)

    pools = []

    for subtype in channel_subtype_map:
        subchannel: RsshubChannel = channel_subtype_map[
            subtype]  # type: ignore
        pools.append(pool_loop(subchannel))

    asyncio.gather(*pools)
