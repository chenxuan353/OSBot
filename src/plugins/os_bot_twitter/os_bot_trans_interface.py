import random
from typing import Optional
from nonebot.adapters import Bot, Event
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from .commands import deal_tweet_link, polling
from .model import TwitterTweetModel
from .config import TwitterSession

from ..os_bot_base.depends import get_session_depend


async def trans_tran_tweet(matcher: Matcher, bot: Bot, event: Event,
                           msg: str) -> TwitterTweetModel:
    session: TwitterSession = await get_session_depend(matcher, bot, event,
                                                       TwitterSession
                                                       )  # type: ignore
    tweet_id = deal_tweet_link(msg, session)
    if not tweet_id:
        await matcher.finish("格式可能不正确哦……可以是链接、序号什么的。")
    tweet = await polling.client.model_tweet_get_or_none(tweet_id)
    has_perm = await (SUPERUSER | GROUP_ADMIN | GROUP_OWNER)(bot, event)
    if not tweet:
        if has_perm:
            tweet = await polling.client.get_tweet(tweet_id)
    if not tweet:
        finish_msgs = ["没有找到推文哦", "找不到哦，要不再检查检查？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if tweet.possibly_sensitive and not has_perm:
        await matcher.finish("推文被标记可能存在敏感内容，不予显示。")

    return tweet
