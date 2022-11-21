import asyncio
import base64
from lib2to3.pgen2 import driver
import math
import os
import random
import re
from time import time
from typing import List, Optional
from tortoise.expressions import Q
from tortoise.query_utils import Prefetch
from nonebot import on_command, Bot, get_driver, on_startswith
from nonebot.permission import SUPERUSER
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, EventMessage
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, PRIVATE_FRIEND
from .polling import twitter_subscribe_invalid_cache, update_all_listener
from .polling import user_follow_and_update, client as tweet_client, PollTwitterUpdate
from .model import TwitterUserModel, TwitterSubscribeModel, TwitterTweetModel, TweetTypeEnum, TwitterTransModel
from .exception import QueueFullException
from .config import TwitterSession, TwitterPlugSession
from .logger import logger
from .config import config
from .tran import TwitterTransManage

from ..os_bot_base.util import matcher_exception_try, only_command
from ..os_bot_base.depends import SessionPluginDepend, SessionDepend
from ..os_bot_base.depends import Adapter, AdapterDepend, ArgMatchDepend
from ..os_bot_base.argmatch import ArgMatch, Field, PageArgMatch

driver = get_driver()
twitterTransManage = TwitterTransManage()


@driver.on_startup
async def _():
    # 启动烤推
    await twitterTransManage.startup()


async def get_user_from_search(msg: str,
                               allow_api: bool = False
                               ) -> Optional[TwitterUserModel]:
    # 通过字符串检索用户
    msg = msg.strip()
    user = None
    if msg.isdigit():
        user = await tweet_client.model_user_get_or_none(msg)
    if not user:
        user = await TwitterUserModel.get_or_none(username=msg)
    if not user:
        user = await TwitterUserModel.get_or_none(name=msg)
    if not user and allow_api:
        try:
            user = await tweet_client.get_user(username=msg)
        except Exception as e:
            logger.opt(exception=True).debug("意外的报错")
    return user


class SubscribeOption:

    def __init__(self) -> None:
        self.tweet_trans: bool = False
        self.update_mention: bool = False
        self.update_retweet: bool = False
        self.update_quote: bool = False
        self.update_replay: bool = False
        self.update_name: bool = False
        self.update_description: bool = False
        self.update_profile: bool = False
        self.update_followers: bool = False

    def _load_from_model(self, model: TwitterSubscribeModel):
        option_keys = [
            "update_mention", "update_retweet", "update_quote",
            "update_replay", "update_description", "update_profile",
            "update_followers", "tweet_trans", "update_name"
        ]
        for option_key in option_keys:
            setattr(self, option_key, getattr(model, option_key, False))

    def _submit_to_model(self, model: TwitterSubscribeModel):
        option_keys = [
            "update_mention", "update_retweet", "update_quote",
            "update_replay", "update_description", "update_profile",
            "update_followers", "tweet_trans", "update_name"
        ]
        for option_key in option_keys:
            setattr(model, option_key, getattr(self, option_key, False))

    def __str__(self) -> str:
        options_map = {
            "update_mention": "相关",
            "update_retweet": "转推",
            "update_quote": "转评",
            "update_replay": "回复",
            "update_name": "昵称",
            "update_description": "描述",
            "update_profile": "头像",
            "update_followers": "粉丝数",
            "tweet_trans": "翻译"
        }
        conf_strs = []
        for option_key in options_map.keys():
            if getattr(self, option_key, False):
                conf_strs.append(options_map[option_key])
        return "、".join(conf_strs)


def deal_subscribe_option(
    msg: str,
    subscribe_option: Optional[SubscribeOption] = None
) -> Optional[SubscribeOption]:
    msg = msg.strip()
    result = re.match(r"""([+-][^+-]+)+""", msg)
    if not result:
        return None
    options_map = {
        "相关": "update_mention",
        "转推": "update_retweet",
        "转评": "update_quote",
        "回复": "update_replay",
        "昵称": "update_name",
        "描述": "update_description",
        "头像": "update_profile",
        "粉丝数": "update_followers",
        "机翻": "tweet_trans",
        "翻译": "tweet_trans",
    }

    if not subscribe_option:
        subscribe_option = SubscribeOption()
    result_all: List[str] = re.findall(r"""[+-][^+-]+""", msg)
    for option in result_all:
        if option in ("+全部", "+all", "+*"):
            for option_key in options_map:
                setattr(subscribe_option, options_map[option_key], True)
        elif option in ("-全部", "-all", "-*"):
            for option_key in options_map:
                setattr(subscribe_option, options_map[option_key], False)
        elif option in ("+通用推送", "+通用"):
            subscribe_option.tweet_trans = False
            subscribe_option.update_mention = True
            subscribe_option.update_retweet = False
            subscribe_option.update_quote = True
            subscribe_option.update_replay = True
            subscribe_option.update_name = True
            subscribe_option.update_description = True
            subscribe_option.update_profile = True
            subscribe_option.update_followers = True
        elif option.startswith("+"):
            option = option[1:]
            if option in options_map:
                setattr(subscribe_option, options_map[option], True)
        elif option.startswith("-"):
            option = option[1:]
            if option in options_map:
                setattr(subscribe_option, options_map[option], True)

    return subscribe_option


class SubscribeArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "订阅参数"
        des = "订阅参数"

    user_search: str = Field.Str("订阅对象")

    def __init__(self) -> None:
        super().__init__([self.user_search])  # type: ignore


subscribe_add = on_command("推特订阅",
                           aliases={"订阅推特", "加推"},
                           permission=SUPERUSER,
                           block=True)


@subscribe_add.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: SubscribeArg = ArgMatchDepend(SubscribeArg),
            adapter: Adapter = AdapterDepend()):
    group_mark = await adapter.mark_group_without_drive(bot, event)
    user = await get_user_from_search(arg.user_search, True)
    if not user:
        finish_msgs = ["找不到用户哦……", "唔……用户不存在……？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if user.protected:
        finish_msgs = ["对方并不开放推文……", "他的推文是私有的哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    subscribe = await TwitterSubscribeModel.get_or_none(group_mark=group_mark,
                                                        subscribe=user.id)
    if subscribe:
        finish_msgs = ["已经订阅了哦", "已经订阅啦"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    if not await user_follow_and_update(user.id):
        await matcher.finish("订阅没有成功，找管理员问问吧。")

    subscribe = TwitterSubscribeModel()
    subscribe.group_mark = group_mark
    subscribe.subscribe = user.id
    subscribe.drive_mark = await adapter.mark_drive(bot, event)
    subscribe.bot_type = adapter.type
    subscribe.bot_id = await adapter.get_bot_id(bot, event)
    if isinstance(event, v11.GroupMessageEvent):
        subscribe.send_param = {"group_id": event.group_id}
    elif isinstance(event, v11.PrivateMessageEvent):
        subscribe.send_param = {"user_id": event.user_id}
    else:
        await matcher.finish("不支持的事件类型")
    option = arg.tail.strip()
    if not option:
        option = "+通用"
    option_ins = SubscribeOption()
    option_ins._load_from_model(subscribe)
    option_ins = deal_subscribe_option(option, option_ins)
    if not option_ins:
        finish_msgs = ["选项不正确哦……", "是不认识的配置，再检查一下吧"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    option_ins._submit_to_model(subscribe)
    await subscribe.save()
    twitter_subscribe_invalid_cache()
    await matcher.finish(f"订阅了{user.name}@{user.username}~")


subscribe_del = on_command("取消推特订阅",
                           aliases={"取消订阅推特", "减推"},
                           block=True,
                           permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                           | PRIVATE_FRIEND)


@subscribe_del.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: SubscribeArg = ArgMatchDepend(SubscribeArg),
            adapter: Adapter = AdapterDepend()):
    group_mark = await adapter.mark_group_without_drive(bot, event)
    user = await get_user_from_search(arg.user_search, True)
    if not user:
        finish_msgs = ["找不到用户哦……", "唔……用户不存在……？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    subscribe = await TwitterSubscribeModel.get_or_none(group_mark=group_mark,
                                                        subscribe=user.id)
    if not subscribe:
        finish_msgs = ["没有订阅他哦！", "没有发现订阅，再检查一下？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    await subscribe.delete()
    twitter_subscribe_invalid_cache()
    await matcher.finish(f"取消了对{user.name}@{user.username}的订阅")


view_user = on_command("推特用户",
                       aliases={"查找推特用户", "检索推特用户"},
                       block=True,
                       permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                       | PRIVATE_FRIEND)


@view_user.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: SubscribeArg = ArgMatchDepend(SubscribeArg),
            adapter: Adapter = AdapterDepend()):
    user = await get_user_from_search(arg.user_search, True)
    if not user:
        finish_msgs = ["找不到用户哦……", "唔……用户不存在……？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    update: PollTwitterUpdate = tweet_client.update  # type: ignore
    finish_msgs = ["让我看看~\n", "找到了！\n"]
    await matcher.finish(
        f"{finish_msgs[random.randint(0,len(finish_msgs) - 1)]}"
        f"{await update.user_to_message(user, adapter.type)}")


def deal_tweet_link(msg: str, session: TwitterSession) -> str:
    msg = msg.strip()
    if msg.startswith(('https://twitter.com/', 'http://twitter.com/',
                       'twitter.com/', 'https://mobile.twitter.com/',
                       'http://mobile.twitter.com/', 'mobile.twitter.com/')):
        msg = msg.split('/')[-1]
        msg = msg.split('?')[0]
        if not msg.isdigit():
            return ""
        return msg
    if msg.startswith('#'):
        msg = msg.strip()[1:]
    if not msg.isdigit():
        return ""
    if msg in session.tweet_map:
        return session.tweet_map[msg]
    return msg


view_tweet = on_command("查看推文",
                        aliases={"检索推文", "看推", "推文", "看看推"},
                        block=True)


@view_tweet.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            message: v11.Message = CommandArg(),
            session: TwitterSession = SessionDepend(TwitterSession),
            adapter: Adapter = AdapterDepend()):
    tweet_id = deal_tweet_link(str(message), session)
    if not tweet_id:
        await matcher.finish("格式可能不正确哦……可以是链接、序号什么的。")
    tweet = await tweet_client.model_tweet_get_or_none(tweet_id)
    has_perm = await (SUPERUSER | GROUP_ADMIN | GROUP_OWNER)(bot, event)
    if not tweet:
        if has_perm:
            tweet = await tweet_client.get_tweet(tweet_id)
    if not tweet:
        finish_msgs = ["没有找到推文哦", "找不到哦，要不再检查检查？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if tweet.possibly_sensitive and not has_perm:
        await matcher.finish("推文被标记可能存在敏感内容，不予显示。")
    if tweet.id in session.failure_list:
        async with session:
            session.failure_list.remove(tweet.id)
    update: PollTwitterUpdate = tweet_client.update  # type: ignore
    finish_msgs = ["看看我发现了什么~\n", "\n"]
    await matcher.finish(
        f"{finish_msgs[random.randint(0,len(finish_msgs) - 1)]}"
        f"{await update.tweet_to_message(tweet, None, adapter.type, False)}")


subscribe_option = on_command(
    "推特订阅配置",
    aliases={"查看推特订阅配置", "看看推特订阅配置", "推特订阅设置", "设置推特订阅"},
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=True)


@subscribe_option.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: SubscribeArg = ArgMatchDepend(SubscribeArg),
            adapter: Adapter = AdapterDepend()):
    group_mark = await adapter.mark_group_without_drive(bot, event)
    user = await get_user_from_search(arg.user_search, True)
    if not user:
        finish_msgs = ["找不到用户哦……", "唔……用户不存在……？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    subscribe = await TwitterSubscribeModel.get_or_none(group_mark=group_mark,
                                                        subscribe=user.id)
    if not subscribe:
        finish_msgs = ["没有订阅他哦！", "没有发现订阅，再检查一下？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    msg = arg.tail.strip()
    option_ins = SubscribeOption()
    option_ins._load_from_model(subscribe)
    if not msg:
        await matcher.finish(f"{user.name}@{user.username}的状况：{option_ins}")

    option_ins = deal_subscribe_option(msg, option_ins)
    if not option_ins:
        finish_msgs = ["选项不正确哦……", "是不认识的配置，再检查一下吧"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    option_ins._submit_to_model(subscribe)
    await subscribe.save()
    twitter_subscribe_invalid_cache()
    await matcher.finish(f"{user.name}@{user.username}的选项更新！\n{option_ins}")


subscribe_list = on_command("推特订阅列表",
                            permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
                            block=True)


@subscribe_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            adapter: Adapter = AdapterDepend()):
    size = 10
    group_mark = await adapter.mark_group_without_drive(bot, event)
    subscribes_count = await TwitterSubscribeModel.filter(group_mark=group_mark
                                                          ).count()
    maxpage = math.ceil(subscribes_count / size)
    if subscribes_count == 0:
        finish_msgs = ["订阅空荡荡...", "没有任何订阅哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    subscribes = await TwitterSubscribeModel.filter(
        group_mark=group_mark
    ).offset(
        (arg.page - 1) * size
    ).limit(size).order_by("-id").only("subscribe").values_list("subscribe",
                                                                flat=True)

    users = await TwitterUserModel.filter(Q(id__in=subscribes)).order_by("-id")
    msg = f"{arg.page}/{maxpage}"
    for user in users:
        msg += f"\n{user.name}@{user.username}"
    await matcher.finish(msg)


subscribe_list_global = on_command("全局推特订阅列表",
                                   permission=SUPERUSER,
                                   block=True)


@subscribe_list_global.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            adapter: Adapter = AdapterDepend()):
    size = 10
    group_mark = await adapter.mark_group_without_drive(bot, event)
    subscribes_count = await TwitterSubscribeModel.all().only(
        "subscribe").distinct().count()
    maxpage = math.ceil(subscribes_count / size)
    if subscribes_count == 0:
        finish_msgs = ["订阅空荡荡...", "没有任何订阅哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    subscribes = await TwitterSubscribeModel.all().offset(
        (arg.page - 1) * size
    ).limit(size).order_by("-id").only("subscribe").values_list("subscribe",
                                                                flat=True)

    users = await TwitterUserModel.filter(Q(id__in=subscribes)).order_by("-id")
    msg = f"{arg.page}/{maxpage}"
    for user in users:
        msg += f"\n{user.name}@{user.username}"
    await matcher.finish(msg)


tweet_list = on_command("推文列表", block=True)


@tweet_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            session: TwitterSession = SessionDepend(TwitterSession)):
    tweet_keys = list(session.tweet_map.keys())
    size = 10
    tweet_count = len(tweet_keys)
    maxpage = math.ceil(tweet_count / size)
    if tweet_count == 0:
        finish_msgs = ["暂无推文~", "没有找到推文哟"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")
    tmp_tweet_keys = tweet_keys[(arg.page - 1) * size:arg.page * size]
    tweet_ids = []
    for tweet_key in tmp_tweet_keys:
        tweet_ids.append(session.tweet_map[tweet_key])

    group_mark = await adapter.mark_group_without_drive(bot, event)
    tweets = await TwitterTweetModel.filter(
        Q(id__in=tweet_ids)).order_by("-id").prefetch_related(
            Prefetch('relate_trans',
                     queryset=TwitterTransModel.filter(
                         group_mark=group_mark).order_by("-id").limit(1)))
    # 此处可能需求关联查询
    type_map = {
        TweetTypeEnum.tweet: "发",
        TweetTypeEnum.retweet: "转",
        TweetTypeEnum.quote: "评",
        TweetTypeEnum.replay: "回"
    }

    msg = f"库\n"
    for tweet_key in tmp_tweet_keys:
        append_msg = ""
        for tweet in tweets:
            if tweet.id == session.tweet_map[tweet_key]:
                append_msg = f"\n{tweet_key} {type_map[tweet.type]}"
                if not tweet.trans and session.tweet_map[
                        tweet_key] in session.failure_list:
                    append_msg += " ★"
                if tweet.trans:
                    tran_models = list(tweet.relate_trans)
                    if tran_models:
                        tran_model = tran_models[0]
                        append_msg += f"熟 {tran_model.trans_text[:10].replace('\n', '')}"
                append_msg += f"{tweet.display_text[:10].replace('\n', '')}"
        if not append_msg:
            append_msg = f"\n{tweet_key} 缓存失效"

        msg += append_msg
    msg += f"{arg.page}/{maxpage}"
    await matcher.finish(msg)


class TweetArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "推文参数"
        des = "推文参数"

    user_search: str = Field.Str("订阅对象")
    page: int = Field.Int("页数", min=1, default=1,
                          help="页码，大于等于1。")  # type: ignore

    def __init__(self) -> None:
        super().__init__([self.user_search, self.page])  # type: ignore


tweet_cache_list = on_command("查看缓存推文列表",
                              aliases={"缓存推文列表"},
                              permission=SUPERUSER,
                              block=True)


@tweet_cache_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher, arg: TweetArg = ArgMatchDepend(TweetArg)):
    user = await get_user_from_search(arg.user_search)
    if not user:
        finish_msgs = ["找不到用户哦……", "可能还没有订阅过哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    size = 5
    tweet_count = await TwitterTweetModel.filter(author_id=user.id).count()
    maxpage = math.ceil(tweet_count / size)
    if tweet_count == 0:
        finish_msgs = ["暂无推文~", "没有找到推文哟"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    tweets = await TwitterTweetModel.filter(author_id=user.id).offset(
        (arg.page - 1) * size).limit(size).order_by("-id")

    msg = f"{user.name}@{user.username}\n"
    for tweet in tweets:
        msg += f"\n{tweet.type.value} | {tweet.id} | {tweet.display_text[:10].replace('\n', '')}{tweet.display_text[10:] and '...'}"
    msg += f"{arg.page}/{maxpage}"
    await matcher.finish(msg)


cache_clear = on_command("清空推特缓存",
                         permission=SUPERUSER,
                         rule=only_command(),
                         block=True)


@cache_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    twitter_subscribe_invalid_cache()
    tweet_client.invalid_cache()
    await matcher.finish(f"完成啦！")


update_all = on_command("更新所有订阅",
                        permission=SUPERUSER,
                        rule=only_command(),
                        block=True)


@update_all.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: v11.PrivateMessageEvent):

    async def run():
        start_time = time()
        await update_all_listener()
        await bot.send(event, f"更新所有订阅的任务完成了哦！({time() - start_time:.2f}s)")

    asyncio.gather(run())
    await matcher.finish(f"提交到后台任务啦！")


ban_user = on_command("添加转推黑名单",
                      aliases={"加入推特黑名单", "加入转推黑名单", "添加推特黑名单"},
                      permission=SUPERUSER,
                      block=True)


@ban_user.handle()
@matcher_exception_try()
async def _(
    matcher: Matcher,
    arg: TweetArg = ArgMatchDepend(TweetArg),
    session_plug: TwitterPlugSession = SessionPluginDepend(TwitterPlugSession),
    adapter: Adapter = AdapterDepend()):
    user = await get_user_from_search(arg.user_search, allow_api=True)
    if not user:
        finish_msgs = ["找不到用户哦……", "用户不存在"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if user.id in session_plug.blacklist_following_list:
        await matcher.finish("重复禁用")
    async with session_plug:
        session_plug.blacklist_following_list.append(user.id)
    await matcher.finish(f"已禁用 {user.username}")


deban_user = on_command("移除转推黑名单",
                        aliases={"减少推特黑名单", "移出转推黑名单", "移出推特黑名单"},
                        permission=SUPERUSER,
                        block=True)


@deban_user.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: TweetArg = ArgMatchDepend(TweetArg),
            session_plug: TwitterPlugSession = SessionPluginDepend(
                TwitterPlugSession)):
    user = await get_user_from_search(arg.user_search, allow_api=True)
    if not user:
        finish_msgs = ["找不到用户哦……", "用户不存在"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if user.id not in session_plug.blacklist_following_list:
        await matcher.finish("没有禁用此用户")
    async with session_plug:
        session_plug.blacklist_following_list.remove(user.id)
    await matcher.finish(f"已取消禁用 {user.username}")


ban_list = on_command("推特黑名单列表",
                      permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
                      block=True)


@ban_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            session_plug: TwitterPlugSession = SessionPluginDepend(
                TwitterPlugSession)):
    size = 10
    ban_list_count = len(session_plug.blacklist_following_list)
    maxpage = math.ceil(ban_list_count / size)
    if ban_list_count == 0:
        await matcher.finish("黑名单列表为空")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    userids = session_plug.blacklist_following_list[(arg.page - 1) *
                                                    size:arg.page * size]

    users = await TwitterUserModel.filter(Q(id__in=userids)).order_by("-id")
    msg = f"{arg.page}/{maxpage}"
    for user in users:
        msg += f"\n{user.name}@{user.username}"
    await matcher.finish(msg)


class TransArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "烤推参数"
        des = "烤推参数"

    tweet_str: str = Field.Str("推文链接、序号")

    def __init__(self) -> None:
        super().__init__([self.user_search])  # type: ignore


tweet_tran = on_command("烤推", aliases={"烤"}, block=True)
tweet_tran_startswith = on_startswith("##", priority=4)


async def tweet_tran_deal(matcher: Matcher, bot: Bot, event: v11.MessageEvent,
                          arg: TransArg, adapter: Adapter,
                          session: TwitterSession,
                          session_plug: TwitterPlugSession):
    tweet_id = deal_tweet_link(arg.tweet_str, session)
    tweet_username = ""
    if not tweet_id:
        await matcher.finish("格式可能不正确哦……可以是链接、序号什么的。")
    tweet = await tweet_client.model_tweet_get_or_none(tweet_id)
    if tweet:
        tweet_username = tweet.author_username
    if not tweet_username:
        if arg.tweet_str.startswith(
            ('https://twitter.com/', 'http://twitter.com/', 'twitter.com/',
             'https://mobile.twitter.com/', 'http://mobile.twitter.com/',
             'mobile.twitter.com/')):
            result = arg.tweet_str.split('/')
            if len(result) > 3:
                tweet_username = result[-3]
    if tweet_username:
        user = await get_user_from_search(tweet_username)
        if user and user.id in session_plug.blacklist_following_list:
            logger.debug("用户被禁用，烤推操作取消 QQ {} -> user {}", event.user_id,
                         user.username)
            await matcher.finish()
    tweet_tran_str = arg.tail
    template = ""
    if tweet_tran_str:
        if session.default_template:
            template = session.default_template
        if tweet_username and tweet_username in session.template_map:
            template = session.template_map[tweet_username]
        if template:
            tweet_tran_str += "\n##默认模版 " + template.strip()

    try:
        task, wait_num, wait_time = await twitterTransManage.submit_trans(
            tweet_id=tweet_id,
            trans_str=tweet_tran_str,
            tweet_username=tweet_username or "normal")
    except QueueFullException:
        finish_msgs = ["烤架满了！稍后再试。", "烤不动了，歇一会……"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    async def wait_result():
        filename = await task

        # 存档
        try:
            trans_model = TwitterTransModel()
            trans_model.group_mark = await adapter.mark_group_without_drive(
                bot, event)
            if tweet:
                trans_model.subscribe = tweet.author_id
            trans_model.drive_mark = await adapter.mark_drive(bot, event)
            trans_model.bot_type = bot.type
            trans_model.bot_id = bot.self_id
            trans_model.user_id = f"{event.user_id}"
            trans_model.trans_text = arg.tail
            trans_model.tweet_id = tweet_id
            trans_model.file_name = filename
            await trans_model.save()
        except Exception as e:
            logger.opt(exception=True).error("保存烤推记录时异常！")

        finish_msgs = ["烤好啦", "熟啦", "叮！", "出锅！"]
        msg = finish_msgs[random.randint(0, len(finish_msgs) - 1)] + "\n"
        if config.os_twitter_trans_image_proxy:
            url = f"{config.os_twitter_trans_image_proxy}/{filename}"
            msg += f"\n {url}\n"
            msg += v11.MessageSegment.image(url)
        else:
            file = os.path.join(twitterTransManage.screenshot_path, filename)
            try:
                with open(file, 'rb') as f:
                    img_data = f.read()
                    base64_data = base64.b64encode(img_data)
            except Exception as e:
                logger.opt(exception=True).error("读取烤推文件时异常")
                await bot.send(event, "获取烤推结果时错误，请联系管理！")
                return
            msg += v11.MessageSegment.image(
                f"base64://{str(base64_data, 'utf-8')}")

        # 发送消息
        await bot.send(event, msg)

    asyncio.gather(wait_result())
    if wait_num == 0:
        finish_msgs = ["烤！", f"烤制{wait_time:.2f}秒~", "制作中~", "放入烤架！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    else:
        finish_msgs = [
            f"稍等一会哦，大概{wait_time:.0f}秒。", f"收到订单！{wait_time:.0f}秒后出餐！",
            f"前方{wait_num}人，稍等片刻。"
        ]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])


@tweet_tran_startswith.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            message: v11.Message = EventMessage(),
            adapter: Adapter = AdapterDepend(),
            session: TwitterSession = SessionDepend(TwitterSession),
            session_plug: TwitterPlugSession = SessionPluginDepend(
                TwitterPlugSession)):
    msg = str(message)
    if msg.startswith("#"):
        msg = msg[1:]
    arg = TransArg()(msg)
    await tweet_tran_deal(matcher, bot, event, arg, adapter, session,
                          session_plug)


@tweet_tran.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: TransArg = ArgMatchDepend(TransArg),
            adapter: Adapter = AdapterDepend(),
            session: TwitterSession = SessionDepend(TwitterSession),
            session_plug: TwitterPlugSession = SessionPluginDepend(
                TwitterPlugSession)):
    await tweet_tran_deal(matcher, bot, event, arg, adapter, session,
                          session_plug)


tweet_tran_history = on_command("烤推历史", aliases={"历史烤推", "烤推记录"}, block=True)


@tweet_tran_history.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            adapter: Adapter = AdapterDepend()):
    group_mark = await adapter.mark_group_without_drive(bot, event)
    size = 5
    tweet_count = await TwitterTransModel.filter(group_mark=group_mark).count()
    maxpage = math.ceil(tweet_count / size)
    if tweet_count == 0:
        finish_msgs = ["暂无推文~", "没有找到推文哟"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    tran_models = await TwitterTransModel.filter(group_mark=group_mark).offset(
        (arg.page - 1) * size).limit(size).order_by("-id")

    msg = f"{arg.page}/{maxpage}"
    for tran_model in tran_models:
        msg += f"\n{tran_model.id} | {tran_model.trans_text[:10].replace('\n', '')}"

    await matcher.finish(msg)


tweet_tran_history = on_command("全局烤推历史",
                                aliases={"全局历史烤推"},
                                permission=SUPERUSER,
                                block=True)


@tweet_tran_history.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    size = 5
    count = await TwitterTransModel.all().count()
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["暂无推文~", "没有找到推文哟"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    tran_models = await TwitterTransModel.all().offset(
        (arg.page - 1) * size).limit(size).order_by("-id")

    msg = f"{arg.page}/{maxpage}"
    for tran_model in tran_models:
        msg += f"\n{tran_model.id} | {tran_model.trans_text[:10].replace('\n', '')}"

    await matcher.finish(msg)


class TransIdArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "烤推参数"
        des = "烤推参数"

    tran_id: int = Field.Int("烤推结果序号", min=0)

    def __init__(self) -> None:
        super().__init__([self.tran_id])  # type: ignore


tweet_tran_history_view = on_command("烤推结果",
                                     aliases={"查看烤推结果", "查看烤推", "查看烤推历史"},
                                     block=True)


@tweet_tran_history_view.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: TransIdArg = ArgMatchDepend(TransIdArg),
            adapter: Adapter = AdapterDepend()):
    tran_model = await TwitterTransModel.get_or_none(id=arg.tran_id)
    if not tran_model:
        finish_msgs = ["是不存在的记录呢……", "再检查一下id……？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    msg = f"推文ID: {tran_model.tweet_id}"
    msg += f"\n译文：\n{tran_model.trans_text}"
    filename = tran_model.file_name
    file = os.path.join(twitterTransManage.screenshot_path, filename)
    if not os.path.isfile(file):
        msg += "\n结果已失效，可能是被清理掉了..."
    else:
        if config.os_twitter_trans_image_proxy:
            url = f"{config.os_twitter_trans_image_proxy}/{filename}"
            msg += f"\n {url} \n"
            msg += v11.MessageSegment.image(url)
        else:
            try:
                with open(file, 'rb') as f:
                    img_data = f.read()
                    base64_data = base64.b64encode(img_data)
            except Exception as e:
                logger.opt(exception=True).error("读取烤推文件时异常")
                await bot.send(event, "获取烤推结果时错误，请联系管理！")
                return
            msg += v11.MessageSegment.image(
                f"base64://{str(base64_data, 'utf-8')}")
