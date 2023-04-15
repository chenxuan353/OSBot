import asyncio
import functools
from time import time
from typing import Any, Dict, List, Optional, Tuple, Type
import aiohttp
from yarl import URL
from tortoise.exceptions import BaseORMException
from tweepy.asynchronous import AsyncClient, AsyncStreamingClient as BaseAsyncStreamingClient
from tweepy import User, Tweet, Poll, Media, OAuth1UserHandler, TweepyException, StreamRule
from requests_oauthlib import OAuth1Session
from cacheout import LRUCache
from cacheout.memoization import lru_memoize
from collections import deque
from math import inf

from .model import TwitterTweetModel, TwitterUserModel, TweetTypeEnum, TwitterSubscribeModel
from .logger import logger
from .exception import TwitterException, RatelimitException, TwitterDatabaseException
from .config import config

from ..os_bot_base.notice import UrgentNotice
from ..os_bot_base.util import AsyncTokenBucket, inhibiting_exception


class ProxyClientRequest(aiohttp.ClientRequest):

    def __init__(self, *args, proxy=None, **kws):
        super().__init__(*args, proxy=URL(config.os_twitter_proxy),
                         **kws)  # type: ignore


class TwitterBuckets:

    def __init__(self) -> None:
        self.get_user = AsyncTokenBucket(200, 15 * 60, initval=5)
        self.get_users = AsyncTokenBucket(200, 15 * 60, initval=5)
        self.get_tweet = AsyncTokenBucket(200, 15 * 60, initval=5)
        self.get_timeline = AsyncTokenBucket(500, 15 * 60, initval=5)
        self.self_timeline = AsyncTokenBucket(150, 15 * 60, initval=5)
        self.self_following_list = AsyncTokenBucket(10, 15 * 60, initval=5)
        self.self_following = AsyncTokenBucket(30, 15 * 60, initval=1)
        self.self_unfollowing = AsyncTokenBucket(30, 15 * 60, initval=1)


class TwitterUpdate:
    """
        推特数据更新的hook
    """
    client: "AsyncTwitterClient"

    def __init__(self) -> None:
        self.ignore_new_time = 4 * 3600
        """
            推文创建多长时间后忽略新增事件，单位秒
        """
        self.ignore_update_time = 86400
        """
            推文创建多长时间后忽略更新事件，单位秒
        """

    async def tweet_new(self, tweet: TwitterTweetModel):
        """
            推文创建
            
            创建也包含出现完整性转换的推文(minor_data修正为False)。
        """
        logger.info("推文创建：{}@{} | {} -> {}", tweet.author_name,
                    tweet.author_username, tweet.id, tweet.display_text)
        if time() - tweet.created_at.timestamp() > self.ignore_new_time:
            return

    async def tweet_update(self, tweet: TwitterTweetModel,
                           old_tweet: Optional[TwitterTweetModel]):
        """
            推文更新
        """
        if not old_tweet:
            return await self.tweet_new(tweet)
        logger.info("推文更新：{}@{} | {} -> {}", tweet.author_name,
                    tweet.author_username, tweet.id, tweet.display_text)

        if time() - tweet.created_at.timestamp() > self.ignore_update_time:
            return

    async def user_new(self, user: TwitterUserModel):
        """
            用户创建
        """
        logger.info("用户创建 {}@{} [{}]", user.name, user.username, user.id)

    async def user_update(self, user: TwitterUserModel,
                          old_user: Optional[TwitterUserModel]):
        """
            用户更新
        """
        if not old_user:
            return await self.user_new(user)
        logger.info("用户更新 {}@{} [{}]", user.name, user.username, user.id)
        if old_user.profile_image_url is not None and old_user.profile_image_url != user.profile_image_url:
            logger.info("用户头像更新 {}@{} [{}] | {} -> {}", user.name,
                        user.username, user.id, old_user.profile_image_url,
                        user.profile_image_url)
        if old_user.description is not None and old_user.description != user.description:
            logger.info("用户描述更新 {}@{} [{}] | {} -> {}", user.name,
                        user.username, user.id, old_user.profile_image_url,
                        user.profile_image_url)
        if old_user.followers_count != -1 and old_user.followers_count != user.followers_count:
            logger.info("用户粉丝数更新 {}@{} [{}] | {} -> {}", user.name,
                        user.username, user.id, old_user.followers_count,
                        user.followers_count)


@lru_memoize(maxsize=1024)
async def model_tweet_get_or_none(tweet_id: str):
    return await TwitterTweetModel.get_or_none(id=tweet_id)


def model_tweet_get_or_none_update(tweet_id: str, model: TwitterTweetModel):
    key = model_tweet_get_or_none.cache_key(tweet_id)
    model_tweet_get_or_none.cache.set(key, model, None)
    # logger.debug("model_tweet_get_or_none 更新缓存 {}", tweet_id)


@lru_memoize(maxsize=256)
async def model_user_get_or_none(user_id: str):
    return await TwitterUserModel.get_or_none(id=user_id)


def model_user_get_or_none_update(user_id: str, model: TwitterUserModel):
    key = model_user_get_or_none.cache_key(user_id)
    model_user_get_or_none.cache.set(key, model, None)
    # logger.debug("model_user_get_or_none_update 更新缓存 {}", user_id)


class AsyncTwitterClient:
    """
        异步推特Api客户端封装
    """

    def __init__(
            self,
            TwitterUpdateCls: Type[TwitterUpdate] = TwitterUpdate) -> None:
        self.client = AsyncClient(
            bearer_token=config.os_twitter_bearer,
            consumer_key=config.os_twitter_key,
            consumer_secret=config.os_twitter_secret,
            access_token=config.os_twitter_access_token,
            access_token_secret=config.os_twitter_access_token_secret,
        )
        self.token_buckets: TwitterBuckets = TwitterBuckets()
        self.client.session = aiohttp.ClientSession(  # type: ignore
            request_class=ProxyClientRequest,
            timeout=aiohttp.ClientTimeout(total=10))

        self.tweet_expansions = "author_id,referenced_tweets.id,in_reply_to_user_id,attachments.media_keys,attachments.poll_ids,referenced_tweets.id.author_id"
        self.tweet_fields = (
            "id,text,edit_history_tweet_ids,attachments,author_id,conversation_id,created_at,entities,"
            "in_reply_to_user_id,lang,possibly_sensitive,public_metrics,referenced_tweets,reply_settings"
        )
        self.user_expansions = "pinned_tweet_id"
        self.user_fields = "id,name,username,created_at,description,entities,pinned_tweet_id,profile_image_url,protected,public_metrics,verified"
        self.media_fields = "media_key,type,url,duration_ms,width,height,preview_image_url,public_metrics,variants"
        self.poll_fields = "id,options,end_datetime,voting_status"
        self.update = TwitterUpdateCls()
        self.update.client = self

    async def tweet_get_type(self, tweet: Tweet) -> TweetTypeEnum:
        if tweet.referenced_tweets:
            if len(tweet.referenced_tweets) > 1:
                if tweet.referenced_tweets[0].type in [
                        "quoted", "replied_to"
                ] and tweet.referenced_tweets[0].type in [
                        "quoted", "replied_to"
                ]:
                    return TweetTypeEnum.quote_replay
                raise TwitterException(f"推文 {tweet.id} 存在两个及以上的 推文类型标识")
            if tweet.referenced_tweets[0].type == "retweeted":
                return TweetTypeEnum.retweet
            elif tweet.referenced_tweets[0].type == "quoted":
                return TweetTypeEnum.quote
            elif tweet.referenced_tweets[0].type == "replied_to":
                return TweetTypeEnum.replay
            else:
                raise TwitterException(
                    f"推文 {tweet.id} 推文类型标识无法匹配 {tweet.referenced_tweets[0].type}"
                )
        return TweetTypeEnum.tweet

    async def render_text(self,
                          text: str,
                          entities: Optional[Dict[str, List[Dict[str, str]]]],
                          is_tweet_type: bool = True):
        text_replace: List[Dict[str, Any]] = []
        if entities:
            urls = entities.get("urls", [])
            for url in urls:
                # 替换缩写的Url至正常Url
                if not is_tweet_type and url["end"] == len(text):
                    # 处理尾部链接，转推与转评会在尾部带上url(实际上不需要展示)
                    text_replace.append({
                        'start': url['start'],
                        'end': url['end'],
                        'replace': '',
                    })
                else:
                    if url['display_url'].startswith("pic.twitter.com"):
                        text_replace.append({
                            'start': url['start'],
                            'end': url['end'],
                            'replace': '',
                        })
                    else:
                        text_replace.append({
                            'start': url['start'],
                            'end': url['end'],
                            'replace': url['expanded_url'],
                        })
        if not text_replace:
            return text
        text_replace.sort(key=lambda e: e['start'])
        rtn_text = ""
        start = 0
        for tr in text_replace:
            rtn_text += text[start:tr['start']]
            start = tr['end']
            rtn_text += tr['replace']
        return rtn_text.replace('&lt;', '<').replace('&gt;', '>')

    async def model_tweet_get_or_none(self, tweet_id: str):
        return await model_tweet_get_or_none(tweet_id)

    def model_tweet_get_or_none_update(self, tweet_id: str,
                                       model: TwitterTweetModel):
        model_tweet_get_or_none_update(tweet_id, model)

    async def model_user_get_or_none(self, user_id: str):
        return await model_user_get_or_none(user_id)

    def model_user_get_or_none_update(self, user_id: str,
                                      model: TwitterUserModel):
        model_user_get_or_none_update(user_id, model)

    def invalid_cache(self):
        cache: LRUCache = model_tweet_get_or_none.cache
        cache.clear()
        cache: LRUCache = model_user_get_or_none.cache
        cache.clear()

    async def conversion_tweet(self,
                               tweet: Tweet,
                               includes: Dict[str, List[Any]] = {},
                               is_minor: bool = True,
                               auto: bool = False) -> TwitterTweetModel:
        """
            转换推文数据

            此方法仅针对传入的`Tweet`对象进行转换，`includes`中的推文不会进行处理。

            includes 用于提供可能的数据还原
            is_minor 是否是次生数据，`includes`中的数据不一定属于次生数据，目前仅转推时会携带所引用推文完整数据
            auto 来自自动更新的数据？(自动更新的数据被认为时效性更佳)
            注意，即使`is_minor`被设置为`False`，当检测到数据完整性缺失时仍然会视为次生数据。
        """
        polls: List[Poll] = includes.get("polls", [])
        medias: List[Media] = includes.get("media", [])
        users: List[User] = includes.get("users", [])
        tweets: List[Tweet] = includes.get("tweets", [])
        old_model = None
        tweet_model = await self.model_tweet_get_or_none(f"{tweet.id}")
        if not tweet_model or (tweet_model.minor_data and not is_minor):
            # 初始化 - 当完整性从非完整变更为完整时再度触发
            if not tweet_model:
                tweet_model = await self.model_tweet_get_or_none(f"{tweet.id}")
                if not tweet_model:
                    tweet_model = TwitterTweetModel(id=f"{tweet.id}")
                    # 更新缓存
                    self.model_tweet_get_or_none_update(
                        f"{tweet.id}", tweet_model)
            tweet_model.minor_data = is_minor
            tweet_model.author_id = f"{tweet.author_id}"
            tweet_model.type = await self.tweet_get_type(tweet)
            tweet_model.text = str(tweet.text)
            tweet_model.text = tweet_model.text.replace('&lt;', '<').replace(
                '&gt;', '>')
            tweet_model.display_text = await self.render_text(
                tweet.text, tweet.entities,
                tweet_model.type == TweetTypeEnum.tweet)
            tweet_model.conversation_id = f"{tweet.conversation_id}"
            tweet_model.lang = tweet.lang
            tweet_model.created_at = tweet.created_at

            # 解析推文作者相关数据
            for user in users:
                if tweet.author_id == user.id:
                    tweet_model.author_name = user.name
                    tweet_model.author_username = user.username
            if not tweet_model.author_name:
                if not tweet_model.minor_data:
                    tweet_model.minor_data = True
                    logger.warning(f"[tweet conversion] `{tweet.id}`缺失推文作者信息！")

            # 处理引用推文
            if tweet.referenced_tweets:
                tweet_model.referenced_tweet_id = f"{tweet.referenced_tweets[0].id}"
                for sub_tweet in tweets:
                    if sub_tweet.id == tweet.referenced_tweets[0].id:
                        tweet_model.referenced_tweet_author_id = f"{sub_tweet.author_id}"
                        for user in users:
                            if sub_tweet.author_id == user.id:
                                tweet_model.referenced_tweet_author_name = user.name
                                tweet_model.referenced_tweet_author_username = user.username
                if not tweet_model.referenced_tweet_author_id:
                    if not tweet_model.minor_data:
                        tweet_model.minor_data = True
                        logger.warning(
                            f"[tweet conversion] `{tweet.id}`缺失引用推文！可能的原因：原文被删除"
                        )
                if not tweet_model.referenced_tweet_author_name:
                    if not tweet_model.minor_data:
                        tweet_model.minor_data = True
                        logger.warning(
                            f"[tweet conversion] `{tweet.id}`缺失引用推文的用户数据！可能的原因：用户封禁"
                        )

            # 处理附件(投票、图片、视频等)
            if tweet.attachments:
                attachments: Dict[str, List[str]] = tweet.attachments
                poll_ids = attachments.get("poll_ids", [])
                media_keys = attachments.get("media_keys", [])
                # 投票
                if poll_ids:
                    if len(poll_ids) > 1:
                        logger.warning(
                            f"[tweet conversion] `{tweet.id}`出现多个投票！")
                    for poll in polls:
                        if poll.id == poll_ids[0]:
                            tweet_model.poll = poll.data
                    if not tweet_model.poll:
                        if not tweet_model.minor_data:
                            tweet_model.minor_data = True
                            logger.warning(
                                f"[tweet conversion] `{tweet.id}`在完整性转换时缺失投票数据"
                            )
                # 媒体
                if media_keys:
                    tweet_medias = []
                    for media_key in media_keys:
                        for media in medias:
                            if media_key == media.media_key:
                                tweet_medias.append(media.data)
                    if not tweet_medias or len(tweet_medias) != len(
                            media_keys):
                        if not tweet_model.minor_data:
                            tweet_model.minor_data = True
                            logger.warning(
                                f"[tweet conversion] `{tweet.id}`在完整性转换时缺失媒体数据"
                            )
                    tweet_model.medias = tweet_medias

            # 解析提及(尽力提供，不保证准确)
            if tweet.entities:
                entities: Dict[str, List[Dict[str, str]]] = tweet.entities
                mentions = entities.get("mentions", [])
                for mention in mentions:
                    if mention.get("id"):
                        tweet_model.mentions.append(
                            mention.get("id"))  # type: ignore
        else:
            old_model = tweet_model.clone(tweet_model.pk)
        # 数据更新
        tweet_model.auto = auto
        tweet_model.possibly_sensitive = tweet.possibly_sensitive is True
        if tweet.public_metrics:
            public_metrics: Dict[str, int] = tweet.public_metrics
            tweet_model.retweet_count = public_metrics.get(
                "retweet_count", tweet_model.retweet_count)
            tweet_model.reply_count = public_metrics.get(
                "reply_count", tweet_model.reply_count)
            tweet_model.like_count = public_metrics.get(
                "like_count", tweet_model.like_count)
            tweet_model.quote_count = public_metrics.get(
                "quote_count", tweet_model.quote_count)
        tweet_model.reply_settings = tweet.reply_settings
        tweet_model.source = tweet.data
        await tweet_model.save()

        asyncio.gather(self.update.tweet_update(tweet_model, old_model))
        self.model_tweet_get_or_none_update(tweet_model.id, tweet_model)
        return tweet_model

    async def conversion_user(self, user: User) -> TwitterUserModel:
        old_model = None
        user_model = await self.model_user_get_or_none(f"{user.id}")
        if not user_model:
            user_model = await self.model_user_get_or_none(f"{user.id}")
            if not user_model:
                user_model = TwitterUserModel(id=f"{user.id}")
                # 更新缓存
                self.model_user_get_or_none_update(f"{user.id}", user_model)
        else:
            old_model = user_model.clone(user_model.pk)
        user_model.name = user.name
        user_model.username = user.username
        user_model.profile_image_url = user.profile_image_url
        user_model.description = await self.render_text(
            user.description, user.entities)
        user_model.protected = user.protected
        user_model.verified = user.verified
        user_model.pinned_tweet_id = f"{user.pinned_tweet_id}"
        user_model.source = user.data
        user_model.created_at = user.created_at

        if user.public_metrics:
            public_metrics: Dict[str, int] = user.public_metrics
            followers_count = public_metrics.get("followers_count",
                                                 user_model.followers_count)
            if followers_count > user_model.followers_count or user_model.followers_count - followers_count > 10000:
                user_model.followers_count = followers_count
            user_model.following_count = public_metrics.get(
                "following_count", user_model.following_count)
            user_model.tweet_count = public_metrics.get(
                "tweet_count", user_model.tweet_count)
            user_model.listed_count = public_metrics.get(
                "listed_count", user_model.listed_count)

        await user_model.save()
        self.model_user_get_or_none_update(user_model.id, user_model)
        asyncio.gather(self.update.user_update(user_model, old_model))
        return user_model

    async def get_user(
            self,
            id: Optional[str] = None,
            username: Optional[str] = None) -> Optional[TwitterUserModel]:
        if not id and not username:
            raise TypeError("至少提供 id 或 username 之中任一参数")
        if not await self.token_buckets.get_user.consume(1):
            raise RatelimitException("速率限制")

        userResponse = await self.client.get_user(
            id=id,
            username=username,
            expansions=self.user_expansions,
            tweet_fields=self.tweet_fields,
            user_fields=self.user_fields)
        if not userResponse.data:  # type: ignore
            return None
        includes: Dict[str, List[Any]] = userResponse.includes  # type: ignore
        tweets: Optional[List[Tweet]] = includes.get("tweets", [])
        if tweets:
            for tweet in tweets:
                await self.conversion_tweet(tweet, includes)
        return await self.conversion_user(userResponse.data)  # type: ignore

    async def get_users(
            self,
            ids: List[str],
            ignore_exception: bool = False) -> List[TwitterUserModel]:
        if not ids:
            return []
        if not await self.token_buckets.get_users.consume(1):
            raise RatelimitException("速率限制")

        usersResponse = await self.client.get_users(
            ids=ids,
            expansions=self.user_expansions,
            tweet_fields=self.tweet_fields,
            user_fields=self.user_fields)
        includes: Dict[str, List[Any]] = usersResponse.includes  # type: ignore

        return_users = []
        for user in usersResponse.data:  # type: ignore
            try:
                return_users.append(await self.conversion_user(user))
            except BaseORMException as e:
                raise TwitterDatabaseException(
                    "数据库异常！位于：self_following_list处理", cause=e)
            except Exception as e:
                if not ignore_exception:
                    raise TwitterException("意外的错误，可能是转换失败导致。", cause=e)

        tweets: Optional[List[Tweet]] = includes.get("tweets", [])
        if tweets:
            for tweet in tweets:
                try:
                    await self.conversion_tweet(tweet, includes)
                except BaseORMException as e:
                    raise TwitterDatabaseException(
                        "数据库异常！位于：self_following_list处理-指定推文列表", cause=e)
                except Exception as e:
                    if not ignore_exception:
                        raise TwitterException("意外的错误，可能是转换失败导致。", cause=e)

        return return_users

    async def get_tweet(self,
                        id: str,
                        use_limit: bool = True) -> Optional[TwitterTweetModel]:
        if not await self.token_buckets.get_tweet.consume(1) and use_limit:
            raise RatelimitException("速率限制")

        tweetResponse = await self.client.get_tweet(
            id=id,
            expansions=self.tweet_expansions,
            tweet_fields=self.tweet_fields,
            user_fields=self.user_fields,
            poll_fields=self.poll_fields,
            media_fields=self.media_fields)

        if not tweetResponse.data:  # type: ignore
            return None

        includes: Dict[str, List[Any]] = tweetResponse.includes  # type: ignore
        users: List[User] = includes.get("users", [])
        tweets: Optional[List[Tweet]] = includes.get("tweets", [])
        includes["tweets"] = []
        includes["tweets"].extend(tweets)
        includes["tweets"].append(tweetResponse.data)  # type: ignore

        for user in users:
            await self.conversion_user(user)

        for tweet in tweets:
            await self.conversion_tweet(tweet, includes)

        main_tweet = await self.conversion_tweet(
            tweetResponse.data,  # type: ignore
            includes,
            is_minor=False)

        return main_tweet

    async def _handle_timeline(self,
                               tweetsResponse,
                               ignore_exception: bool = False,
                               auto: bool = False) -> List[TwitterTweetModel]:
        includes: Dict[str,
                       List[Any]] = tweetsResponse.includes  # type: ignore
        users: List[User] = includes.get("users", [])
        tweets: Optional[List[Tweet]] = includes.get("tweets", [])
        includes["tweets"] = []
        includes["tweets"].extend(tweets)
        includes["tweets"].extend(tweetsResponse.data)  # type: ignore

        return_tweets = []
        res_tweets: List[Tweet] = tweetsResponse.data  # type: ignore

        # 优先处理依赖
        for user in users:
            try:
                await self.conversion_user(user)
            except BaseORMException as e:
                raise TwitterDatabaseException(
                    f"数据库异常！位于：timeline处理-用户 {user.id}", cause=e)
            except Exception as e:
                if not ignore_exception:
                    raise TwitterException(
                        f"意外的错误，可能是转换失败导致。 timeline处理-用户 {user.id}", cause=e)

        for tweet in tweets:
            try:
                await self.conversion_tweet(tweet, includes, auto=auto)
            except BaseORMException as e:
                raise TwitterDatabaseException(
                    f"数据库异常！位于：timeline处理-次要推文 {tweet.id}", cause=e)
            except Exception as e:
                if not ignore_exception:
                    raise TwitterException(
                        f"意外的错误，可能是转换失败导致。位于：timeline处理-次要推文 {tweet.id}",
                        cause=e)

        # 处理主体
        for res_tweet in res_tweets:
            try:
                return_tweets.append(await
                                     self.conversion_tweet(res_tweet,
                                                           includes,
                                                           is_minor=False,
                                                           auto=auto))
            except BaseORMException as e:
                raise TwitterDatabaseException(
                    f"数据库异常！位于：timeline处理-主数据 {res_tweet.id}", cause=e)
            except Exception as e:
                if not ignore_exception:
                    raise TwitterException(
                        f"意外的错误，可能是转换失败导致。 位于：timeline处理-主数据 {res_tweet.id}",
                        cause=e)

        return return_tweets

    async def get_timeline(self,
                           id: Optional[str] = None,
                           username: Optional[str] = None,
                           ignore_exception: bool = False,
                           auto: bool = False) -> List[TwitterTweetModel]:
        """
            获取时间线

            ignore_exception 是否忽视异常
        """
        if not await self.token_buckets.get_timeline.consume(1):
            raise RatelimitException("速率限制")
        if not id:
            user = await self.get_user(username=username)
            if not user:
                raise TwitterException("用户不存在")
            id = user.id
        tweetsResponse = await self.client.get_users_tweets(
            id=id,
            max_results=100,
            expansions=self.tweet_expansions,
            tweet_fields=self.tweet_fields,
            user_fields=self.user_fields,
            poll_fields=self.poll_fields,
            media_fields=self.media_fields)

        return await self._handle_timeline(tweetsResponse, ignore_exception,
                                           auto)

    async def self_timeline(self,
                            ignore_exception: bool = False,
                            auto: bool = False) -> List[TwitterTweetModel]:
        """
            获取自己的时间线

            注意：当前的设计下，如果轮询间隔内更新的推文超过100条，可能导致部分推文被忽略。

            ignore_exception 是否忽视异常
        """
        if not await self.token_buckets.self_timeline.consume(1):
            raise RatelimitException("速率限制")
        tweetsResponse = await self.client.get_home_timeline(
            max_results=100,
            expansions=self.tweet_expansions,
            tweet_fields=self.tweet_fields,
            user_fields=self.user_fields,
            poll_fields=self.poll_fields,
            media_fields=self.media_fields)
        return await self._handle_timeline(tweetsResponse, ignore_exception,
                                           auto)

    async def self_following_list(self,
                                  ignore_exception: bool = False
                                  ) -> List[TwitterUserModel]:
        """
            关注的用户列表。

            当前的设计下，关注列表至多支持1000个用户的监听。
        """
        if not await self.token_buckets.self_following_list.consume(1):
            raise RatelimitException("速率限制")
        usersResponse = await self.client.get_users_following(
            id=await self.client._get_authenticating_user_id(oauth_1=True),
            max_results=1000,
            expansions=self.user_expansions,
            tweet_fields=self.tweet_fields,
            user_fields=self.user_fields,
            user_auth=True)
        includes: Dict[str, List[Any]] = usersResponse.includes  # type: ignore

        return_users = []
        for user in usersResponse.data:  # type: ignore
            try:
                return_users.append(await self.conversion_user(user))
            except BaseORMException as e:
                raise TwitterDatabaseException(
                    f"数据库异常！位于：self_following_list处理 {user.id}", cause=e)
            except Exception as e:
                if not ignore_exception:
                    raise TwitterException(f"意外的错误，可能是转换失败导致。 {user.id}",
                                           cause=e)

        tweets: Optional[List[Tweet]] = includes.get("tweets", [])
        if tweets:
            for tweet in tweets:
                try:
                    await self.conversion_tweet(tweet, includes)
                except BaseORMException as e:
                    raise TwitterDatabaseException(
                        "数据库异常！位于：self_following_list处理-指定推文列表", cause=e)
                except Exception as e:
                    if not ignore_exception:
                        raise TwitterException("意外的错误，可能是转换失败导致。", cause=e)

        return return_users

    async def self_following(
            self,
            id: Optional[str] = None,
            username: Optional[str] = None) -> TwitterUserModel:
        """
            关注
        """
        if not await self.token_buckets.self_following.consume(1):
            raise RatelimitException("速率限制")
        user = await self.get_user(id=id, username=username)
        if not user:
            raise TwitterException("用户不存在")
        await self.client.follow_user(user.id)
        return user

    async def self_unfollowing(
            self,
            id: Optional[str] = None,
            username: Optional[str] = None) -> TwitterUserModel:
        """
            取消关注
        """
        if not await self.token_buckets.self_unfollowing.consume(1):
            raise RatelimitException("速率限制")
        user = await self.get_user(id=id, username=username)
        if not user:
            raise TwitterException("用户不存在")
        await self.client.unfollow_user(user.id)
        return user

    async def generate_authorization_url(self) -> str:
        self.oauth1_user_handler = OAuth1UserHandler(
            self.client.consumer_key,
            self.client.consumer_secret,
            callback="oob")
        self.oauth1_user_handler.oauth.proxies = {
            "http": config.os_twitter_proxy,
            "https": config.os_twitter_proxy
        }
        return self.oauth1_user_handler.get_authorization_url()

    async def generate_accesstoken(self, pin: str) -> Tuple[str, str]:
        oauth1_user_handler = self.oauth1_user_handler
        oauth1_user_handler.oauth.proxies = {
            "http": config.os_twitter_proxy,
            "https": config.os_twitter_proxy
        }
        try:
            url = oauth1_user_handler._get_oauth_url('access_token')
            oauth1_user_handler.oauth = OAuth1Session(
                oauth1_user_handler.consumer_key,
                client_secret=oauth1_user_handler.consumer_secret,
                resource_owner_key=oauth1_user_handler.
                request_token['oauth_token'],
                resource_owner_secret=oauth1_user_handler.
                request_token['oauth_token_secret'],
                verifier=pin,
                callback_uri=oauth1_user_handler.callback)
            oauth1_user_handler.oauth.proxies = {
                "http": config.os_twitter_proxy,
                "https": config.os_twitter_proxy
            }
            resp = oauth1_user_handler.oauth.fetch_access_token(url)
            oauth1_user_handler.access_token = resp['oauth_token']
            oauth1_user_handler.access_token_secret = resp[
                'oauth_token_secret']
            return oauth1_user_handler.access_token, oauth1_user_handler.access_token_secret
        except Exception as e:
            raise TweepyException(e)


class AsyncTweetUpdateStreamingClient(BaseAsyncStreamingClient):

    def __init__(self,
                 bearer_token,
                 async_stream: "AsyncTwitterStream",
                 *,
                 return_type=...,
                 wait_on_rate_limit=False,
                 **kwargs):
        super().__init__(bearer_token,
                         return_type=return_type,
                         wait_on_rate_limit=wait_on_rate_limit,
                         **kwargs)
        self.async_stream = async_stream
        self.client = async_stream.client
        self.is_retry = False
        self.error = deque(maxlen=10)  # 记录五次错误

    @property
    def running(self):
        return self.task is not None and not self.task.done()

    async def on_connect(self):
        self.connect_error_clear()
        logger.info("推特过滤流已连接！")
        UrgentNotice.add_notice("推特过滤流已连接！")

        @inhibiting_exception()
        async def delay_run():
            await asyncio.sleep(10)
            self.delay_update_all_listener()

        asyncio.gather(delay_run())

    async def on_tweet(self, tweet: Tweet):
        await self.client.get_tweet(f"{tweet.id}", use_limit=False)

    async def on_includes(self, includes):
        users: List[User] = includes.get("users", [])
        for user in users:
            try:
                await self.client.conversion_user(user)
            except Exception as e:
                logger.opt(exception=True).error("推特流式传输中转换用户对象异常 {}", e)

    async def on_errors(self, errors):
        # 流式传输中的错误，不影响流
        logger.warning("推特过滤流错误 errors:{}", errors)
        UrgentNotice.add_notice("推特过滤流错误")

    async def on_close(self, resp):
        # 过滤流被关闭（tweepy将开始重试）
        logger.warning("推特过滤流被关闭")
        self.delay_update_all_listener()
        UrgentNotice.add_notice("推特过滤流被关闭")

    async def on_request_error(self, status):
        # API流链接请求失败，429之类的问题, 是没什么用的on（tweepy将开始重试）
        logger.error("推特监听流链接异常 reques status {}", status)
        self.delay_update_all_listener()

    async def on_connection_error(self):
        # API错误，会导致流暂时断开（tweepy将开始重试） aiohttp.ClientConnectionError,aiohttp.ClientPayloadError
        logger.warning(
            "推特流式传输连接异常！ (或发生 ClientConnectionError or ClientPayloadError)")
        self.delay_update_all_listener()
        UrgentNotice.add_notice("推特流式传输连接异常")

    async def on_exception(self, exception):
        # 侦听异常，会导致意外关闭
        logger.opt(exception=True).error("推特过滤流异常 e:{}", exception)
        UrgentNotice.add_notice("推特过滤流出现意外的异常")

        @inhibiting_exception()
        async def in_func():
            self.is_retry = True
            # 自动重连
            await asyncio.sleep(30)
            await self.async_stream.connect()
            self.delay_update_all_listener()
            self.is_retry = False

        asyncio.gather(in_func())

    async def on_disconnect(self):
        # 真正关闭后时调用此方法
        logger.error("推特过滤流已断开连接")
        UrgentNotice.add_notice("推特过滤流已断开连接")

    def isrunning(self, ignore_retry: bool = False):
        if not ignore_retry and self.is_retry:
            return True
        return self.running

    def connect_error(self, error: Any):
        self.error.append((time(), error))

    def connect_error_count(self):
        """
            统计五分钟以内发生的错误
        """
        count = 0
        now_time = time()
        for error in self.error:
            if now_time - error[0] < 300:
                count += 1
        return count

    def connect_error_clear(self):
        self.error.clear()

    def delay_update_all_listener(self):
        from .polling import update_all_listener
        update_all_listener()


# aiohttp.ClientSession = functools.partial(aiohttp.ClientSession, request_class=ProxyClientRequest)


class AsyncTwitterStream:

    def __init__(self, client: AsyncTwitterClient) -> None:
        self.client = client
        self.stream = AsyncTweetUpdateStreamingClient(
            config.os_twitter_bearer,
            self,
            wait_on_rate_limit=True,
            max_retries=inf,  # 无限重试
            proxy=URL(config.os_twitter_proxy),
        )
        # self.stream.session = aiohttp.ClientSession(  # type: ignore
        #     request_class=ProxyClientRequest, timeout=aiohttp.ClientTimeout(connect=15, sock_read=300))

        self.tweet_expansions = "author_id,referenced_tweets.id,in_reply_to_user_id,referenced_tweets.id.author_id"
        self.tweet_fields = (
            "id,text,edit_history_tweet_ids,attachments,author_id,conversation_id,created_at,entities,"
            "in_reply_to_user_id,lang,possibly_sensitive,public_metrics,referenced_tweets,reply_settings"
        )
        self.user_fields = "id,name,username,created_at,description,entities,pinned_tweet_id,profile_image_url,protected,public_metrics,verified"
        self.media_fields = "media_key,type,url,duration_ms,width,height,preview_image_url,public_metrics,variants"
        self.poll_fields = "id,options,end_datetime,voting_status"

    async def reload_listeners(self, listeners: List[str]):
        """
            重设监听列表
        """
        try:
            ids = [
                rule.id for rule in (
                    await self.stream.get_rules()).data  # type: ignore
            ]
        except TypeError:
            ids = []
        if ids:
            await self.stream.delete_rules(ids)

        listeners_rules = []
        listeners_line = ""
        for listener in listeners:
            add_one = f"from:{listener} -is:nullcast OR "
            if len(listeners_line) + len(add_one) - 4 >= 512:
                listeners_rules.append(StreamRule(value=listeners_line[:-4]))
                listeners_line = ""
            listeners_line += add_one

        if listeners_line:
            listeners_rules.append(StreamRule(value=listeners_line[:-4]))

        if len(listeners_rules) > config.os_twitter_stream_rule_limit:
            info = f"规则数量超限！将产生截断。当前监听总数：{len(listeners)} 生成规则数：{len(listeners_rules)}"
            logger.error(info)
            await UrgentNotice.send(info)
            listeners_rules = listeners_rules[:config.
                                              os_twitter_stream_rule_limit]
        else:
            if len(listeners) > config.os_twitter_stream_rule_limit * 13 - 10:
                info = f"监听数量即将达到当前允许的上限，请注意维护监听列表！ 当前监听总数：{len(listeners)}"
                logger.warning(info)
                UrgentNotice.add_notice(info)

        await self.stream.add_rules(listeners_rules)

    async def connect(self):
        self.stream.filter(expansions=self.tweet_expansions,
                           tweet_fields=self.tweet_fields,
                           user_fields=self.user_fields,
                           media_fields=self.media_fields,
                           poll_fields=self.poll_fields)

    async def reconnect(self):
        if self.stream.isrunning():
            self.stream.is_retry = True
            self.stream.disconnect()
            await asyncio.sleep(30)
        self.stream.is_retry = True
        await self.connect()
        self.stream.is_retry = False

    def is_running(self):
        return self.stream.isrunning()
