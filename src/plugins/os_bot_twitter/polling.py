"""
    轮询与更新推送
"""
import asyncio
import re
import aiohttp
from time import time
from typing import Any, Dict, List, Optional, Union
from nonebot import get_driver
from nonebot.adapters.onebot import v11
from nonebot_plugin_apscheduler import scheduler
from tweepy import TweepyException
from cacheout import Cache
from cacheout.memoization import memoize
from .twitter import AsyncTwitterClient, TwitterUpdate, TwitterTweetModel, TwitterUserModel, TwitterSubscribeModel, TweetTypeEnum, TwitterDatabaseException
from .logger import logger
from .config import config, TwitterPlugSession, TwitterSession
from .exception import TwitterPollingSendError

from ..os_bot_base.util import get_plugin_session, plug_is_disable, get_session
from ..os_bot_base.notice import UrgentNotice, BotSend
from ..os_bot_base.adapter.onebot import V11Adapter
from ..os_bot_base.exception import MatcherErrorFinsh

driver = get_driver()


@memoize(maxsize=1)
async def _model_get_listeners() -> List[str]:
    return await TwitterSubscribeModel.all().only(
        "subscribe").distinct().values_list("subscribe",
                                            flat=True)  # type: ignore


@memoize(maxsize=1)
async def _model_get_listeners_map() -> Dict[str, List[TwitterSubscribeModel]]:
    """
        构建监听地图

        监听推特用户ID -> 相关订阅列表
    """
    subscribes = await TwitterSubscribeModel.all()
    listeners_map: Dict[str, List[TwitterSubscribeModel]] = {}

    for sub in subscribes:
        if sub.subscribe not in listeners_map:
            listeners_map[sub.subscribe] = []
        listeners_map[sub.subscribe].append(sub)

    return listeners_map


def twitter_subscribe_invalid_cache():
    cache: Cache = _model_get_listeners.cache
    cache.clear()
    cache: Cache = _model_get_listeners_map.cache
    cache.clear()


class PollTwitterUpdate(TwitterUpdate):
    """
        推特数据更新的hook
    """
    session: TwitterPlugSession
    client: AsyncTwitterClient

    def __init__(self) -> None:
        self.ignore_new_time = 3600
        """推文创建多长时间后忽略新增事件，单位秒"""
        self.ignore_update_time = 86400
        """推文创建多长时间后忽略更新事件，单位秒"""
        self.update_user_precision = 1000
        """粉丝数通知精度，默认千位"""
        self.update_mention_followers = 3000
        """相关推送最低粉丝数限制"""
        self.update_mention_verified = True
        """相关推送包含已验证账户"""

    def invaild_cache(self):
        self.invaild_cache()

    async def push_message(self, subscribe: TwitterSubscribeModel,
                           message: Union[str, v11.Message]):
        if await BotSend.send_msg(subscribe.bot_type, subscribe.send_param,
                                  message):
            return
        raise TwitterPollingSendError(f"订阅消息发送失败(相关订阅 {subscribe.id})")

    async def user_to_message(self, user: TwitterUserModel, bot_type: str):
        """
            用户查看用途
        """
        msg = f"{user.name}@{user.username}"
        if bot_type == V11Adapter.get_type():
            msg += "\n" + v11.MessageSegment.image(file=user.profile_image_url)
        else:
            logger.debug("暂未支持的推送适配器 {} 相关用户 {}", bot_type, user.id)
        msg += f"\n粉丝 {user.followers_count} 关注 {user.following_count}"
        msg += f"\n推文 {user.tweet_count}"
        msg += f"\n置顶 {user.pinned_tweet_id}"
        msg += f"\n---简介---\n{user.description}"
        tags = []
        if user.protected:
            tags.append("推文受保护")
        if user.verified:
            tags.append("已验证")
        msg += f"\n建于 {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        return msg

    async def tweet_to_message(
        self,
        tweet: TwitterTweetModel,
        relate_tweet: Optional[TwitterTweetModel],
        bot_type: str,
        tweet_trans: bool = False,
    ):
        """
            推文查看用途
        """
        if not relate_tweet and tweet.referenced_tweet_id:
            relate_tweet = await self.client.model_tweet_get_or_none(
                tweet.referenced_tweet_id)
        # 标题及依赖推文
        msg = ""
        if tweet.type == TweetTypeEnum.tweet:
            msg = f"{tweet.author_name}的推文~"
            # 附加主推文
            msg += f"\n{tweet.display_text}"
            if tweet_trans and tweet.trans_text:
                msg += f"\n--------"
                msg += f"\n{tweet.trans_text}"
        elif tweet.type == TweetTypeEnum.retweet:
            if tweet.author_id == tweet.referenced_tweet_author_id:
                msg = f"{tweet.author_name}\n转了自己的推"
            else:
                msg = f"{tweet.author_name}转了\n{tweet.referenced_tweet_author_name}的推文"
            if relate_tweet:
                msg += f"\n{relate_tweet.display_text}"
                if tweet_trans and relate_tweet.trans_text:
                    msg += f"\n------"
                    msg += f"\n{relate_tweet.trans_text}"
            else:
                logger.warning("转推更新涉及的依赖推文不存在！ 主推文 {} 依赖推文 {}", tweet.id,
                               tweet.referenced_tweet_id)
                msg += f"\n{tweet.display_text}"
                msg += "\n>依赖推文缺失\n"
                return msg
        elif tweet.type == TweetTypeEnum.quote:
            if tweet.author_id == tweet.referenced_tweet_author_id:
                msg = f"{tweet.author_name}\n转评了自己的推文~"
            else:
                msg = f"{tweet.author_name}\n转评了\n{tweet.referenced_tweet_author_name}的推文"
            # 附加主推文
            msg += f"\n{tweet.display_text}"
            if tweet_trans and tweet.trans_text:
                msg += f"\n------"
                msg += f"\n{tweet.trans_text}"
            if relate_tweet:
                msg += f"\n========"
                msg += f"\n{relate_tweet.display_text}"
                if tweet_trans and relate_tweet.trans_text:
                    msg += f"\n------"
                    msg += f"\n{relate_tweet.trans_text}"
            else:
                logger.warning("转评更新涉及的依赖推文不存在！ 主推文 {} 依赖推文 {}", tweet.id,
                               tweet.referenced_tweet_id)
                msg += f"\n========\n引用推文数据缺失"
        elif tweet.type == TweetTypeEnum.replay:
            if tweet.author_id == tweet.referenced_tweet_author_id:
                msg = f"{tweet.author_name}\n回复了自己的推"
            else:
                msg = f"{tweet.author_name}\n回复了\n{tweet.referenced_tweet_author_name}的推"
            # 附加主推文
            msg += f"\n{tweet.display_text}"
            if tweet_trans and tweet.trans_text:
                msg += f"\n------"
                msg += f"\n{tweet.trans_text}"
            if relate_tweet:
                msg += f"\n========"
                msg += f"\n{relate_tweet.display_text}"
                if tweet_trans and relate_tweet.trans_text:
                    msg += f"\n------"
                    msg += f"\n{relate_tweet.trans_text}"
            else:
                logger.warning("回复更新涉及的依赖推文不存在！ 主推文 {} 依赖推文 {}", tweet.id,
                               tweet.referenced_tweet_id)
                msg += f"\n========\n引用推文数据缺失"
        elif tweet.type == TweetTypeEnum.quote_replay:
            msg = f"{tweet.author_name}\n带推回复了\n{tweet.referenced_tweet_author_name}的推"
            # 附加主推文
            msg += f"\n{tweet.display_text}"
            if tweet_trans and tweet.trans_text:
                msg += f"\n------"
                msg += f"\n{tweet.trans_text}"
        else:
            logger.warning("异常推文类型({})：{}", tweet.id, tweet.type)
            msg = f"{tweet.author_name} 的未知类型推文"
            msg += f"\n{tweet.display_text}"
        # 拼接图片
        if tweet.medias:
            # type photo, GIF, video
            type = tweet.medias[0].get("type", "")
            if type.lower() in ("video", "gif"):
                url = ""
                variants: Optional[Dict[str,
                                        str]] = tweet.medias[0].get('variants')
                if variants:
                    url = variants.get("url", "")
                msg += f"\n 包含视频或Gif {url}"
            if bot_type == V11Adapter.get_type():
                for media in tweet.medias:
                    display_url = None
                    if media.get("type", "").lower() in ("video", "gif"):
                        display_url = media.get("preview_image_url")
                    elif media.get("type", "").lower() == "photo":
                        display_url = media.get("url")
                    if display_url:
                        msg += v11.MessageSegment.image(file=display_url)
                    else:
                        logger.warning("推文媒体缺失 媒体类型 {} 推送目标 {} 推文 {} ",
                                       media.get("type", ""), bot_type,
                                       tweet.id)
            else:
                logger.debug("暂未支持的推送适配器 {} 推文 {} ", bot_type, tweet.id)
        return msg

    async def push_tweet_message(self,
                                 subscribe: TwitterSubscribeModel,
                                 tweet: TwitterTweetModel,
                                 only_add_failure: bool = False):
        if await plug_is_disable("os_bot_twitter", subscribe.group_mark):
            logger.info("因组 {} 的推特插件被关闭，转推消息推送取消。(相关订阅 {})",
                        subscribe.group_mark, subscribe.id)
            return
        session: TwitterSession = await get_session(subscribe.group_mark,
                                              TwitterSession,
                                              "os_bot_twitter")  # type: ignore
        if only_add_failure:
            session.failure_list.append(tweet.id)
            return
        if tweet.author_id in session.ban_users:
            logger.debug("{} 内推送 {} 被禁用 涉及推文 {} 订阅 {}", subscribe.group_mark,
                         tweet.author_id, tweet.id, subscribe.id)
            return

        relate_tweet = None
        if tweet.referenced_tweet_id:
            relate_tweet = await self.client.model_tweet_get_or_none(
                tweet.referenced_tweet_id)

        # 推文翻译
        if subscribe.tweet_trans:
            if config.os_twitter_trans_engine:
                from ..os_bot_trans.trans import engines, base_langs, deal_trans_text
                if config.os_twitter_trans_engine in engines:
                    engine = engines[config.os_twitter_trans_engine]
                    if not tweet.trans_text:
                        try:
                            source = "auto"
                            if tweet.lang and tweet.lang in base_langs and engine.check_lang(
                                    tweet.lang, "zh-cn"):
                                source = tweet.lang

                            tweet.trans_text = await engine.trans(
                                source, "zh-cn",
                                deal_trans_text(tweet.display_text))
                            await tweet.save()
                        except Exception as e:
                            logger.opt(exception=True).warning(
                                "机翻 {} 失败！使用引擎及参数 {} {} -> {} 内容 {}", tweet.id,
                                config.os_twitter_trans_engine, "auto", "zh",
                                tweet.display_text)

                    try:
                        if relate_tweet and not relate_tweet.trans_text:
                            source = "auto"
                            if relate_tweet.lang and relate_tweet.lang in base_langs and engine.check_lang(
                                    relate_tweet.lang, "zh-cn"):
                                source = relate_tweet.lang
                            relate_tweet.trans_text = await engine.trans(
                                source, "zh-cn", relate_tweet.display_text)
                            await relate_tweet.save()
                    except Exception as e:
                        logger.opt(exception=True).warning(
                            "机翻 {}(相关推文) 失败！使用引擎及参数 {} {} -> {} 内容 {}",
                            tweet.id, config.os_twitter_trans_engine, "auto",
                            "zh", tweet.display_text)

            else:
                logger.warning("推送{}启用了推文翻译，但未设置翻译引擎！", subscribe.id)
        msg = await self.tweet_to_message(tweet, relate_tweet,
                                          subscribe.bot_type,
                                          subscribe.tweet_trans)

        # 生成推文映射
        while f"{session.num}" in session.tweet_map:
            session.num += 1
        tweet_num = f"{session.num}"
        session.tweet_map[tweet_num] = tweet.id
        session.num += 1
        await session.save()
        msg += f"\n序 {tweet_num}"
        msg += f"\nhttps://twitter.com/{tweet.author_username}/status/{tweet.id}"
        try:
            await self.push_message(subscribe, msg)
        except TwitterPollingSendError as e:
            logger.warning("推文更新消息推送失败 订阅 {} 消息 {}", subscribe.id, msg)
            session.failure_list.append(tweet.id)

    async def push_user_message(self, subscribe: TwitterSubscribeModel,
                                user: TwitterUserModel, update_type: str,
                                old_val: Any, new_val: Any):
        if await plug_is_disable("os_bot_twitter", subscribe.group_mark):
            logger.info("因组 {} 的推特插件被关闭，用户更新消息推送取消。(相关订阅 {})",
                        subscribe.group_mark, subscribe.id)
            return
        session: TwitterSession = await get_session(subscribe.group_mark,
                                              TwitterSession,
                                              "os_bot_twitter")  # type: ignore
        if user.id in session.ban_users:
            logger.debug("{} 内用户 {} 的设置更新推送被禁用 订阅 {}", subscribe.group_mark,
                         user.id, subscribe.id)
            return
        if subscribe.bot_type == V11Adapter.get_type():
            if update_type == "昵称":
                msg = (f"{user.name}的昵称更新~\n"
                       f"{old_val}\n更新为\n"
                       f"{new_val}")
            elif update_type == "描述":
                msg = (f"{user.name}的描述更新~\n"
                       f"旧：{old_val}\n"
                       f"新：{new_val}")
            elif update_type == "头像":
                msg = f"{user.name}的头像更新咯！"
                msg += "\n旧：" + v11.MessageSegment.image(file=old_val)
                msg += "\n新：" + v11.MessageSegment.image(file=new_val)
            elif update_type in ("粉丝数涨到", "粉丝数跌到"):
                msg = f"{user.name}的{update_type}{new_val}了~"
            else:
                msg = (f"{user.name}的{update_type}更新~"
                       f"{old_val} => {new_val}")
            try:
                await self.push_message(subscribe, msg)
            except TwitterPollingSendError as e:
                logger.warning("用户更新消息推送失败 订阅 {} 消息 {}", subscribe.id, msg)
        else:
            logger.warning("消息推送不支持的Bot类型 {} (相关订阅 {})", subscribe.bot_type,
                           subscribe.id)
            return

    async def tweet_new(self, tweet: TwitterTweetModel):
        """
            推文创建
            
            创建也包含出现完整性转换的推文(minor_data修正为False)。
        """
        now_time = time()
        is_timeout = now_time - tweet.created_at.timestamp(
        ) > self.ignore_new_time
        if is_timeout:
            logger.debug("推文创建：{}@{} | {} -> {}", tweet.author_name,
                         tweet.author_username, tweet.id, tweet.display_text)
            if now_time - tweet.created_at.timestamp() > 86400:
                # 超过一天的数据不做推送及标记
                return
        else:
            logger.info("推文新增：{}@{} | {} -> {}", tweet.author_name,
                        tweet.author_username, tweet.id, tweet.display_text)

        listeners_map = await _model_get_listeners_map()
        main_listeners = listeners_map.get(tweet.author_id, [])

        for listener in main_listeners:
            if tweet.type == TweetTypeEnum.tweet:
                await self.push_tweet_message(listener,
                                              tweet,
                                              only_add_failure=is_timeout)
            elif tweet.type == TweetTypeEnum.retweet and listener.update_retweet:
                await self.push_tweet_message(listener,
                                              tweet,
                                              only_add_failure=is_timeout)
            elif tweet.type == TweetTypeEnum.quote and listener.update_quote:
                await self.push_tweet_message(listener,
                                              tweet,
                                              only_add_failure=is_timeout)
            elif tweet.type == TweetTypeEnum.replay and listener.update_replay:
                await self.push_tweet_message(listener,
                                              tweet,
                                              only_add_failure=is_timeout)
            else:
                logger.warning("意外的推文类型({})：{}", tweet.id, tweet.type)

        if tweet.possibly_sensitive:
            """
                被标记为敏感的推文不参与相关推送
            """
            return
        user = await self.client.model_user_get_or_none(tweet.author_id)
        if not user:
            return
        if not ((self.update_mention_verified and user.verified)
                or user.followers_count > self.update_mention_followers):
            """
                账户已验证 或 粉丝数大于设定的值 才被视为真相关
            """
            return
        for user_id in tweet.mentions:
            listeners = listeners_map.get(user_id, [])
            for listener in listeners:
                if listener.update_mention:
                    await self.push_tweet_message(listener,
                                                  tweet,
                                                  only_add_failure=is_timeout)

    async def tweet_update(self, tweet: TwitterTweetModel,
                           old_tweet: Optional[TwitterTweetModel]):
        """
            推文更新
        """
        if not old_tweet:
            return await self.tweet_new(tweet)
        if time() - tweet.created_at.timestamp() > self.ignore_update_time:
            logger.debug("历史推文更新：{}@{} | {} -> {}", tweet.author_name,
                         tweet.author_username, tweet.id, tweet.display_text)
            return
        logger.debug("推文更新：{}@{} | {} -> {}", tweet.author_name,
                     tweet.author_username, tweet.id, tweet.display_text)

    async def user_new(self, user: TwitterUserModel):
        """
            用户创建
        """
        logger.debug("用户创建 {}@{} [{}]", user.name, user.username, user.id)

    async def user_update(self, user: TwitterUserModel,
                          old_user: Optional[TwitterUserModel]):
        """
            用户更新
        """
        if not old_user:
            return await self.user_new(user)
        logger.debug("用户更新 {}@{} [{}]", user.name, user.username, user.id)
        update_types = []
        if old_user.name is not None and old_user.name != user.name:
            update_type = "昵称"
            old_val = old_user.name
            new_val = user.name
            logger.debug("用户昵称更新 @{} [{}] | {} -> {}", user.username, user.id,
                         old_val, new_val)
            update_types.append((update_type, old_val, new_val))
        if old_user.profile_image_url is not None and old_user.profile_image_url != user.profile_image_url:
            update_type = "头像"
            old_val = old_user.profile_image_url
            new_val = user.profile_image_url
            logger.debug("用户头像更新 {}@{} [{}] | {} -> {}", user.name,
                         user.username, user.id, old_val, new_val)
            update_types.append((update_type, old_val, new_val))
        if old_user.description is not None and old_user.description != user.description:
            update_type = "描述"
            old_val = old_user.description
            new_val = user.description
            logger.info("用户描述更新 {}@{} [{}] | {} -> {}", user.name,
                        user.username, user.id, old_val, new_val)
            update_types.append((update_type, old_val, new_val))
        if old_user.followers_count != -1 and old_user.followers_count != user.followers_count:
            old_val = old_user.followers_count
            new_val = user.followers_count
            if old_val == -1 or new_val == -1:
                return
            old_precision = int(old_val / self.update_user_precision)
            new_precision = int(new_val / self.update_user_precision)
            if old_precision == new_precision:
                return
            if new_precision > old_precision:
                update_type = "粉丝数涨到"
            else:
                update_type = "粉丝数跌到"
            logger.info("用户粉丝数更新 {}@{} [{}] | {} -> {}", user.name,
                        user.username, user.id, old_val, str(new_val))
            update_types.append((update_type, old_val, new_val))
        if not update_types:
            return
        listeners_map = await _model_get_listeners_map()
        main_listeners = listeners_map.get(user.id, [])

        for listener in main_listeners:
            for update_type_tuple in update_types:
                if update_type_tuple[0] == "昵称" and listener.update_name:
                    await self.push_user_message(listener, user,
                                                 *update_type_tuple)
                elif update_type_tuple[0] == "头像" and listener.update_profile:
                    await self.push_user_message(listener, user,
                                                 *update_type_tuple)
                elif update_type_tuple[
                        0] == "描述" and listener.update_description:
                    await self.push_user_message(listener, user,
                                                 *update_type_tuple)
                elif update_type_tuple[0] in (
                        "粉丝数涨到", "粉丝数跌到") and listener.update_followers:
                    await self.push_user_message(listener, user,
                                                 *update_type_tuple)
                else:
                    logger.warning("未配置的更新组：{}", update_type_tuple)


# 进行初始化
session: TwitterPlugSession = None  # type: ignore
client: AsyncTwitterClient = None  # type: ignore


async def update_all_listener():
    """
        更新所有用户的时间线（异步）
    """
    listeners = await _model_get_listeners()
    for listener in listeners:
        try:
            user = await client.model_user_get_or_none(listener)
            if not user:
                logger.error(" {} 用户信息不存在，已取消关注操作", id)
                return False
            if user.protected:
                logger.error(" {} 的时间线，受保护，已取消更新", listener)
                continue
            try:
                await client.get_timeline(id=listener)
            except (asyncio.exceptions.TimeoutError, aiohttp.ClientError) as e:
                await asyncio.sleep(10)
                await client.get_timeline(id=listener)
            logger.debug("已更新 {}@{} 的时间线", user.name, user.username)
        except (TweepyException, asyncio.exceptions.TimeoutError, aiohttp.ClientError) as e:
            user = None
            try:
                user = await client.model_user_get_or_none(listener)
            except Exception as e:
                pass
            if not user:
                logger.opt(exception=True).error("更新 {} 时间线时错误", listener)
            else:
                logger.opt(exception=True).error("更新 {}@{} 时间线时错误", user.name,
                                                 user.username)

        # 时间线更新间隔 3s
        await asyncio.sleep(3)


async def user_follow_and_update(id: str) -> bool:
    """
        关注并更新用户
    """
    if id in session.blacklist_following_list:
        return False
    listeners = await _model_get_listeners()
    if id not in listeners:
        try:
            user = await client.model_user_get_or_none(id)
            if not user:
                logger.error(" {} 用户信息不存在，已取消关注操作", id)
                return False
            if user.protected:
                logger.error(" {} 的时间线，受保护，已取消关注操作", id)
                return False
            if id not in session.following_list:
                # 只关注没有关注的新用户
                await client.self_following(id)
                session.following_list.append(id)
                await session.save()
                # 同时更新时间线
                await client.get_timeline(id=id)
                logger.debug("已初始化 {}@{} 的时间线", user.name, user.username)
            return True
        except MatcherErrorFinsh as e:
            raise e
        except Exception as e:
            logger.opt(exception=True).error("关注用户时异常")
            return False
    return True


@driver.on_startup
async def _():
    global session, client
    if not config.os_twitter_poll_enable:
        logger.warning("推特轮询关闭！已取消轮询初始化。")
        return
    logger.info("推特功能初始化")
    # 进行初始化
    session = await get_plugin_session(TwitterPlugSession
                                                           )  # type: ignore
    session._keep = True
    PollTwitterUpdate.session = session
    client = AsyncTwitterClient(PollTwitterUpdate)

    async def startup_follow_listener():
        try:
            try:
                following_users = await client.self_following_list()
            except (TweepyException, asyncio.exceptions.TimeoutError, aiohttp.ClientError) as e:
                logger.info("获取当前关注列表失败，将在60秒后自动重试。")
                await asyncio.sleep(60.1)
                following_users = await client.self_following_list()

            following_list = []

            for user in following_users:
                following_list.append(user.id)

            session.following_list = following_list
            await session.save()
        except (TweepyException, asyncio.exceptions.TimeoutError, aiohttp.ClientError) as e:
            logger.warning("初始化关注列表失败！连接不稳定 {} | {}", e.__class__.__name__, e)
        except Exception as e:
            logger.opt(exception=True).error("初始化关注列表失败！")
        listeners = await _model_get_listeners()
        for listener in listeners:
            if listener not in session.following_list:
                if listener in session.blacklist_following_list:
                    logger.debug("检测到监听中存在黑名单用户 -> {}", id)
                    continue
                await user_follow_and_update(listener)
                await asyncio.sleep(60.5)

    async def startup():
        """
            启动初始化
        """
        session._enable=False
        strat_time = time()
        logger.info("检查并更新用户关注")
        strat_deal_time = time()
        await startup_follow_listener()
        logger.info(f"检查并更新用户关注结束 耗时 {time() - strat_deal_time:.2f}s")
        logger.info("推特时间线启动检测开始")
        strat_deal_time = time()
        await update_all_listener()
        logger.info(f"推特时间线启动检测结束 耗时 {time() - strat_deal_time:.2f}s")
        logger.info(f"推特功能初始化结束 总耗时 {time() - strat_time:.2f}s")
        session._enable=True

    asyncio.gather(startup())

    @scheduler.scheduled_job("interval", seconds=config.os_twitter_poll_interval, name="推特轮询")
    async def _():
        if not config.os_twitter_poll_enable:
            return
        if not session._enable:
            return

        async def update() -> bool:
            try:
                await client.self_timeline(ignore_exception=True, auto=True)
            except TweepyException as e:
                return True
            except (aiohttp.ClientError, asyncio.exceptions.TimeoutError) as e:
                logger.warning("推特更新轮询连接错误 {} | {}", e.__class__.__name__, str(e))
                return True
            except TwitterDatabaseException as e:
                session._enable = False
                logger.opt(exception=True).error("进行推特更新轮询时发生数据库异常，已暂时关闭轮询进程！")
                await UrgentNotice.send("推特更新时出现数据库异常，更新轮询已停止")
            except Exception as e:
                session._enable = False
                logger.opt(exception=True).error("进行推特更新轮询时出现未知异常，已暂时关闭轮询进程！")
                await UrgentNotice.send("推特更新出现未知异常，更新轮询已停止")
            return False

        # 重试机制 重试五次 每次间隔1分钟
        for _ in range(5):
            if not await update():
                break
            await asyncio.sleep(60)
