import asyncio
import base64
import math
import os
import random
import re
import aiohttp
from time import time
from typing import Optional
from tortoise.expressions import Q
from tortoise.query_utils import Prefetch
from nonebot import on_command, Bot, get_driver, on_startswith
from nonebot.permission import SUPERUSER
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, EventMessage
from nonebot.adapters.onebot import v11
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, PRIVATE_FRIEND
from nonebot_plugin_apscheduler import scheduler
from . import polling
from .polling import twitter_subscribe_invalid_cache, update_all_listener
from .polling import user_follow_and_update, PollTwitterUpdate
from .model import TwitterUserModel, TwitterSubscribeModel, TwitterTweetModel, TweetTypeEnum, TwitterTransModel
from .exception import QueueFullException, MatcherErrorFinsh, TransException
from .config import TwitterSession, TwitterPlugSession
from .logger import logger
from .config import config
from .tran import TwitterTransManage
from .options import Options, Option

from ..os_bot_base.util import matcher_exception_try, only_command, inhibiting_exception, RateLimitDepend, RateLimitUtil
from ..os_bot_base.depends import SessionPluginDepend, SessionDepend
from ..os_bot_base.depends import Adapter, AdapterDepend, ArgMatchDepend
from ..os_bot_base.argmatch import ArgMatch, Field, PageArgMatch
from ..os_bot_base.notice import BotSend, LeaveGroupHook
from ..os_bot_base.adapter.onebot import V11Adapter
from ..os_bot_base.permission import PermManage, perm_check_rule

driver = get_driver()
twitterTransManage: TwitterTransManage = None  # type: ignore
PermManage.register("烤推", "烤推权限", True, only_super_oprate=False)
PermManage.register("推文链接", "推文链接推送", False, only_super_oprate=True)


@driver.on_startup
async def _():
    # 启动烤推
    global twitterTransManage
    twitterTransManage = TwitterTransManage()
    await twitterTransManage.startup()

    @scheduler.scheduled_job('cron', hour='3', minute='30', name="烤推清理")
    async def _():
        logger.info("开始烤推清理")
        await twitterTransManage.clear_screenshot_file()
        logger.info("烤推清理完成")

    # @scheduler.scheduled_job('cron', hour='4', minute='30', name="自动烤推重启")
    # async def _():
    #     logger.info("自动烤推引擎重启")
    #     await twitterTransManage.restart()
    #     logger.info("烤推引擎重启完成")


@driver.on_shutdown
async def _():
    await twitterTransManage.stop()
    logger.info("烤推引擎`playwright`已停止")


async def get_user_from_search(msg: str,
                               allow_api: bool = False
                               ) -> Optional[TwitterUserModel]:
    # 通过字符串检索用户
    msg = msg.strip()
    user = None
    if msg.isdigit():
        user = await polling.client.model_user_get_or_none(msg)
    if not user:
        user = await TwitterUserModel.get_or_none(username=msg)
    if not user:
        user = await TwitterUserModel.get_or_none(name=msg)
    if not user and allow_api:
        try:
            user = await polling.client.get_user(username=msg)
        except Exception as e:
            logger.opt(exception=True).debug("意外的报错")

    if user and not await polling.client.model_user_get_or_none(msg):
        # 在意外的情况下更新缓存，保证订阅正常进行
        polling.client.model_user_get_or_none_update(user.id, user)
    return user


class SubscribeOption(Options):

    tweet_trans: bool = Option.new(False, ["自动翻译", "翻译", "机翻"])
    update_mention: bool = Option.new(True, ["相关", "智能", "关联推送", "智能推送"])
    update_retweet: bool = Option.new(False, ["转推"])
    update_quote: bool = Option.new(True, ["转评", "转发评论"])
    update_replay: bool = Option.new(False, ["回复"])

    update_name: bool = Option.new(True, ["昵称", "昵称更新"])
    update_description: bool = Option.new(True, ["描述", "描述更新", "简介", "简介更新"])
    update_profile: bool = Option.new(True, ["头像", "头像更新"])
    update_followers: bool = Option.new(True, ["粉丝数", "粉丝数更新"])

    def _load_from_model(self, model: TwitterSubscribeModel):
        option_keys = self.tag_map
        for option_key in option_keys:
            setattr(self, option_key, getattr(model, option_key, False))

    def _submit_to_model(self, model: TwitterSubscribeModel):
        option_keys = self.tag_map
        for option_key in option_keys:
            setattr(model, option_key, getattr(self, option_key, False))

    def matcher_option_hook(self, key: str, value: bool,
                            source_option: str) -> bool:
        """
            option钩子

            可以针对性处理特定选项，返回True表明拦截默认操作。
        """
        if not value and key in ["用户资料", "用户", "用户信息"]:
            self.update_name = False
            self.update_description = False
            self.update_profile = False
            self.update_followers = False
            return True
        return False


def deal_subscribe_option(
    msg: str,
    subscribe_option: Optional[SubscribeOption] = None
) -> Optional[SubscribeOption]:
    if not subscribe_option:
        subscribe_option = SubscribeOption()
    subscribe_option.matcher_options(msg)
    return subscribe_option


class SubscribeArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "订阅参数"
        des = "订阅参数"

    user_search: str = Field.Str("订阅对象")

    def __init__(self) -> None:
        super().__init__([self.user_search])


subscribe_add = on_command("推特订阅",
                           aliases={"订阅推特", "加推", "添加转推"},
                           permission=SUPERUSER,
                           block=True)


@subscribe_add.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: SubscribeArg = ArgMatchDepend(SubscribeArg),
            session: TwitterSession = SessionDepend(TwitterSession),
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

    subscribe.send_param = await BotSend.pkg_send_params(bot, event)

    option = arg.tail.strip()
    if not option:
        option = "+通用"
    option_ins = SubscribeOption()
    # option_ins._load_from_model(subscribe)
    option_ins = deal_subscribe_option(option, option_ins)
    if not option_ins:
        finish_msgs = ["选项不正确哦……", "是不认识的配置，再检查一下吧"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    option_ins._submit_to_model(subscribe)
    await subscribe.save()
    twitter_subscribe_invalid_cache()
    if not session.default_sub_id:
        async with session:
            session.default_sub_id = user.id
    await matcher.finish(f"订阅了{user.name}@{user.username}~")


subscribe_del = on_command("取消推特订阅",
                           aliases={"取消订阅推特", "减推", "减少转推", "移除转推"},
                           block=True,
                           permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                           | PRIVATE_FRIEND)


@subscribe_del.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: SubscribeArg = ArgMatchDepend(SubscribeArg),
            session: TwitterSession = SessionDepend(TwitterSession),
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
    if session.default_sub_id and session.default_sub_id == user.id:
        async with session:
            session.default_sub_id = None
    await matcher.finish(f"取消了对{user.name}@{user.username}的订阅")


subscribe_clear = on_command("清空推特订阅",
                             aliases={"清空转推"},
                             block=True,
                             permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                             | PRIVATE_FRIEND)


@subscribe_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend()):
    group_mark = await adapter.mark_group_without_drive(bot, event)
    if not await TwitterSubscribeModel.filter(group_mark=group_mark).exists():
        await matcher.finish("订阅列表就是空的哟")
    await matcher.pause(f">>发送确认清空以继续操作<<")


@subscribe_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            message: v11.Message = EventMessage(),
            session: TwitterSession = SessionDepend(TwitterSession),
            adapter: Adapter = AdapterDepend()):
    msg = str(message).strip()
    if msg == "确认清空":
        group_mark = await adapter.mark_group_without_drive(bot, event)
        await TwitterSubscribeModel.filter(group_mark=group_mark).delete()
        twitter_subscribe_invalid_cache()
        async with session:
            session.default_sub_id = None

        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["未确认操作", "操作已取消"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


async def level_group_hook(group_id: int, bot_id: int) -> None:
    try:
        group_mark = f"{V11Adapter.get_type()}-global-group-{group_id}"
        await TwitterSubscribeModel.filter(group_mark=group_mark).delete()
        twitter_subscribe_invalid_cache()
    except Exception as e:
        logger.opt(exception=True).error("`TwitterSubscribeModel`退群处理时异常")


LeaveGroupHook.get_instance().add_hook(level_group_hook)

view_user = on_command("推特用户",
                       aliases={"查找推特用户", "查询推特用户", "检索推特用户"},
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
    update: PollTwitterUpdate = polling.client.update  # type: ignore
    finish_msgs = ["让我看看~\n", "找到了！\n"]
    await matcher.finish(
        v11.Message(finish_msgs[random.randint(0,
                                               len(finish_msgs) - 1)]) +
        await update.user_to_message(user, adapter.type))


def deal_tweet_link(msg: str, session: TwitterSession) -> str:
    msg = msg.strip()
    if msg.startswith(('https://twitter.com/', 'http://twitter.com/',
                       'twitter.com/', 'https://mobile.twitter.com/',
                       'http://mobile.twitter.com/', 'mobile.twitter.com/',
                       'https://mobile.x.com/','http://mobile.x.com/', 'mobile.x.com/',
                       'https://x.com/','http://x.com/', 'x.com/')):
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
    elif int(msg) < 100000:
        """小于10万时视为从缓存中获取数据"""
        return ""
    return msg


view_tweet = on_command("查看推文",
                        aliases={"检索推文", "看推", "推文", "看看推"},
                        rule=perm_check_rule("烤推"),
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

    trans_model = await TwitterTransModel.filter(
        tweet_id=tweet.id,
        group_mark=await
        adapter.mark_group_without_drive(bot, event)).order_by("-id").first()

    if tweet.possibly_sensitive and not has_perm:
        await matcher.finish("推文被标记可能存在敏感内容，不予显示。")
    if tweet.id in session.failure_list:
        async with session:
            session.failure_list.remove(tweet.id)
    update: PollTwitterUpdate = polling.client.update  # type: ignore
    finish_msgs = ["看看我发现了什么~\n", "合 成 推 文\n", "找到了\n"]
    msg = (v11.Message(finish_msgs[random.randint(0,
                                                  len(finish_msgs) - 1)]) +
           f"ID：{tweet.id}\n" +
           await update.tweet_to_message(tweet, None, adapter.type, False))
    if trans_model:
        # adapter.get_unit_nick()
        filename = trans_model.file_name
        file = os.path.join(twitterTransManage.screenshot_path, filename)
        if not os.path.isfile(file):
            msg += "\n烤推结果已失效，可能是被清理掉了..."
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
                    msg += "\n获取烤推结果时错误，请联系管理！"
                    return
                msg += f"\n序列 {trans_model.id}"
                if adapter.type == trans_model.bot_type:
                    group_id = event.group_id if isinstance(
                        event, v11.GroupMessageEvent) else None
                    msg += f"\n由 {await adapter.get_unit_nick(trans_model.user_id, group_id=group_id)}({trans_model.user_id}) 烤制"
                msg += v11.MessageSegment.image(
                    f"base64://{str(base64_data, 'utf-8')}")
    await matcher.finish(msg)


subscribe_option = on_command(
    "推特订阅配置",
    aliases={"查看推特订阅配置", "看看推特订阅配置", "推特订阅设置", "设置推特订阅", "转推配置", "配置转推"},
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=True)


@subscribe_option.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: SubscribeArg = ArgMatchDepend(SubscribeArg),
            session: TwitterSession = SessionDepend(TwitterSession),
            adapter: Adapter = AdapterDepend()):
    group_mark = await adapter.mark_group_without_drive(bot, event)
    if arg.user_search in ("def", "默认", "-"):
        if not session.default_sub_id:
            await matcher.finish("没有配置默认值哦")
        arg.user_search = session.default_sub_id
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
                            aliases={"转推列表"},
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
                                   aliases={"全局转推列表"},
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
    msg = f"{arg.page}/{maxpage} ({subscribes_count})"
    for user in users:
        msg += f"\n{user.name}@{user.username}"
    await matcher.finish(msg)


tweet_list = on_command("推文列表",
                        aliases={"仓库", "打开仓库", "看看仓库"},
                        rule=perm_check_rule("烤推"),
                        block=True)


@tweet_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            session: TwitterSession = SessionDepend(TwitterSession)):
    tweet_keys = [int(key) for key in session.tweet_map]
    tweet_keys.sort(reverse=True)
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
        tweet_ids.append(session.tweet_map[str(tweet_key)])

    group_mark = await adapter.mark_group_without_drive(bot, event)
    subscribes = await TwitterSubscribeModel.filter(
        group_mark=group_mark
    ).order_by("-id").only("subscribe").values_list("subscribe", flat=True)
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
        TweetTypeEnum.replay: "回",
        TweetTypeEnum.quote_replay: "引用回复"
    }

    msg = f"库"
    for tweet_key in tmp_tweet_keys:
        append_msg = ""
        for tweet in tweets:
            if tweet.id == session.tweet_map[str(tweet_key)]:
                if tweet.author_id in subscribes:
                    append_msg = f"\n{tweet_key} | {type_map[tweet.type]}"
                else:
                    append_msg = f"\n{tweet_key} | 相关"
                if not tweet.trans and session.tweet_map[str(
                        tweet_key)] in session.failure_list:
                    append_msg += " ★"
                if tweet.trans:
                    tran_models = list(tweet.relate_trans)
                    if tran_models:
                        tran_model = tran_models[0]
                        if tran_model.trans_text:
                            append_msg += " 熟 > {0}".format(
                                tran_model.trans_text[:10].replace('\n', ''))
                    else:
                        append_msg += " > {0}".format(
                            tweet.display_text[:10].replace('\n', ''))
                else:
                    append_msg += " > {0}".format(
                        tweet.display_text[:10].replace('\n', ''))
        if not append_msg:
            append_msg = f"\n{tweet_key} 缓存失效"

        msg += append_msg
    msg += f"\n{arg.page}/{maxpage}"
    await matcher.finish(msg)


class TweetArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "推文参数"
        des = "推文参数"

    user_search: str = Field.Str("订阅对象")
    page: int = Field.Int("页数", min=1, default=1,
                          help="页码，大于等于1。")  # type: ignore

    def __init__(self) -> None:
        super().__init__([self.user_search, self.page])


tweet_cache_list = on_command("查看缓存推文列表",
                              aliases={"缓存推文列表", "用户推文列表"},
                              permission=SUPERUSER,
                              block=True)


@tweet_cache_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: TweetArg = ArgMatchDepend(TweetArg),
            session: TwitterSession = SessionDepend(TwitterSession)):
    if arg.user_search in ("def", "默认", "-"):
        if not session.default_sub_id:
            await matcher.finish("没有配置默认值哦")
        arg.user_search = session.default_sub_id

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

    msg = f"{user.name}@{user.username}"
    for tweet in tweets:
        msg += "\n{0} | {1} | {2}{3}".format(
            tweet.type.value, tweet.id,
            tweet.display_text[:10].replace('\n', ''), tweet.display_text[10:]
            and '...')
    msg += f"\n{arg.page}/{maxpage}"
    await matcher.finish(msg)


tweet_def_user_set = on_command(
    "默认推特用户",
    aliases={"设置默认推特用户", "默认推特用户设置", "配置默认推特用户", "默认推特用户配置"},
    permission=SUPERUSER,
    block=True)


@tweet_def_user_set.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: SubscribeArg = ArgMatchDepend(SubscribeArg),
            session: TwitterSession = SessionDepend(TwitterSession)):
    if arg.user_search in ("def", "默认", "-"):
        if not session.default_sub_id:
            await matcher.finish("没有配置默认值哦")
        arg.user_search = session.default_sub_id

    user = await get_user_from_search(arg.user_search)
    if not user:
        finish_msgs = ["找不到用户哦……", "可能还没有订阅过哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    async with session:
        session.default_sub_id = user.id
    await matcher.finish(f"默认用户 {user.name}@{user.username}")


cache_clear = on_command("清空推特缓存",
                         permission=SUPERUSER,
                         rule=only_command(),
                         block=True)


@cache_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    twitter_subscribe_invalid_cache()
    polling.client.invalid_cache()
    await matcher.finish(f"完成啦！")


check_and_start = on_command("检查流式监听",
                             permission=SUPERUSER,
                             rule=only_command(),
                             block=True)


@check_and_start.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    if not config.os_twitter_stream_enable:
        await matcher.finish("流式监听未启用")
    if polling.stream.stream.isrunning():
        await matcher.finish("流式监听正常")
    await polling.stream.reconnect()
    await matcher.finish("流式监听已再次启动")


update_all = on_command("更新所有订阅",
                        permission=SUPERUSER,
                        rule=only_command(),
                        block=True)


@update_all.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: v11.PrivateMessageEvent):

    @inhibiting_exception()
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

    tweet_str: str = Field.Regex(
        "推文链接、序号",
        regex=
        r"(((http|https):\/{2})?(mobile.)?(twitter|x).com(\/(([~0-9a-zA-Z\#\+\%@\.\/_-]+))?(\?[0-9a-zA-Z\+\%@\/&\[\];=_-]+)?)?)|[1-9][0-9]*"
    )

    def __init__(self) -> None:
        super().__init__([self.tweet_str])


async def download_to_base64(url: str,
                             maxsize_kb=500,
                             ignore_exception: bool = False) -> str:
    maxsize = maxsize_kb * 1024
    timeout = 15
    try:
        req = aiohttp.request("get",
                              url,
                              timeout=aiohttp.ClientTimeout(total=10))
        async with req as resp:
            code = resp.status
            if code != 200:
                raise MatcherErrorFinsh("获取图片失败，状态看起来不是很好的样子。")
            if resp.content_length and resp.content_length > maxsize:
                raise MatcherErrorFinsh(f'图片太大！要小于{maxsize_kb}kb哦')
            size = 0
            start = time()
            filedata = bytes()
            async for chunk in resp.content.iter_chunked(1024):
                if time() - start > timeout:
                    raise MatcherErrorFinsh('下载超时了哦')
                filedata += chunk
                size += len(chunk)
                if size > maxsize:
                    raise MatcherErrorFinsh(f'图片太大！要小于{maxsize_kb}kb哦')
            urlbase64 = str(base64.b64encode(filedata), "utf-8")
    except MatcherErrorFinsh as e:
        if ignore_exception:
            logger.warning("图片下载失败：{} | {}", url, e)
            return ""
        raise e
    except Exception as e:
        logger.warning("图片下载失败：{} | {} | {}", url, e.__class__.__name__, e)
        return ""
    return urlbase64


tweet_tran = on_command("烤推",
                        aliases={"烤", "烤制"},
                        block=True,
                        rule=perm_check_rule("烤推"))
tweet_tran_startswith = on_startswith("##",
                                      priority=4,
                                      rule=perm_check_rule("烤推"))


async def tweet_tran_deal(matcher: Matcher, bot: Bot, event: v11.MessageEvent,
                          message: v11.Message, adapter: Adapter,
                          session: TwitterSession,
                          session_plug: TwitterPlugSession):
    if not twitterTransManage.enable:
        await matcher.finish("烤推机能未启动！")
    maximgnum = 5  # 至多允许几张图
    imgnum = 0
    msg = ""
    for msgseg in message:
        if msgseg.is_text():
            msg += msgseg.data.get("text", "")
        elif msgseg.type == "image":
            url = msgseg.data.get("url", "")
            if url:
                msg += f'<img src="data:image/jpg;base64,{await download_to_base64(url, maxsize_kb=1024)}" alt="图片"/>'
                imgnum += 1
                if imgnum <= maximgnum:
                    continue
                finish_msgs = ["图太多啦", "不要放置太多图片哦！", f"{maximgnum}张图，不能再多了！"]
                await matcher.finish(finish_msgs[random.randint(
                    0,
                    len(finish_msgs) - 1)])
    if msg.startswith("#"):
        msg = msg[1:]
    if msg.startswith("#"):
        msg = msg[1:]
    msg = msg.strip()
    arg = TransArg()(msg)
    tweet_id = deal_tweet_link(arg.tweet_str, session)
    tweet_username = ""
    if not tweet_id:
        await matcher.finish("格式可能不正确哦……可以是链接、序号什么的。")

    tweet = None
    if config.os_twitter_trans_api_enable:
        try:
            tweet = await polling.client.get_tweet(tweet_id, use_limit=False)
            if tweet:
                tweet_username = tweet.author_username
        except Exception as e:
            logger.warning("烤推时，通过API获取推文数据失败 {}", e)

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
            logger.info("用户被禁用，烤推操作取消 QQ {} -> user {}", event.user_id,
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

    @inhibiting_exception()
    async def wait_result():
        tran_user_nick = await adapter.get_unit_nick_from_event(
            event.user_id, bot, event)
        try:
            filename = await task
        except TransException as e:
            await bot.send(event, f"@{tran_user_nick}\n{e.info}")
            logger.opt(exception=True).error("烤推时异常")
            return
        except Exception as e:
            logger.opt(exception=True).error("烤推时异常")
            await bot.send(event, "烤推时异常，请联系管理员")
            return

        # 存档
        try:
            # 非截图时存档
            if arg.tail:
                trans_model = TwitterTransModel()
                trans_model.group_mark = await adapter.mark_group_without_drive(
                    bot, event)
                if tweet:
                    trans_model.subscribe = tweet.author_id
                trans_model.drive_mark = await adapter.mark_drive(bot, event)

                trans_model.bot_type = adapter.get_type()
                trans_model.bot_id = await adapter.get_bot_id(bot, event)
                trans_model.user_id = f"{event.user_id}"
                trans_model.trans_text = arg.tail
                trans_model.tweet_id = tweet_id
                trans_model.file_name = filename
                await trans_model.save()

                if tweet:
                    tweet.trans = True
                    await tweet.save(update_fields=["trans"])
        except Exception as e:
            logger.opt(exception=True).error("保存烤推记录时异常！")
            await bot.send(event, "烤推时异常，请联系管理员")
            return

        finish_msgs = ["烤好啦", "熟啦", "叮！", "出锅！", "", "好耶！", "十分！", "完成啦！"]
        msg = f"@{tran_user_nick} " + finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)] + "\n"
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
        if random.randint(0, 100) > 70:
            tips = [
                "遇到无法载图可以重试哦", "使用`看推 序号`查看历史推文", "可以用推文列表检查历史推文~",
                "遇到BUG及时反馈~"
            ]
            tip = tips[random.randint(0, len(tips) - 1)]
            msg += v11.MessageSegment.text(tip)
        elif not arg.tail:
            msg += v11.MessageSegment.text("推荐使用`看推 序号/链接`查看推文")
        # 发送消息
        await bot.send(event, msg)

    asyncio.gather(wait_result())
    wait_time = math.ceil(wait_time)
    if wait_num == 0:
        finish_msgs = [
            "烤！", f"烤制{wait_time}秒~", "制作中~", f"定时{wait_time}秒", "放入烤架！",
            "烤架已就绪", "烤架准备好啦", "武火速烤！", "开始厨艺表演~", "大火烤制~", "微波加热！", "核心烘焙中~",
            "窑炉烧制>"
        ]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    else:
        finish_msgs = [
            f"稍等一会哦，大概{wait_time:.0f}秒。", f"收到订单！{wait_time:.0f}秒后出餐！",
            f"前方{wait_num}人，稍等片刻。", f"烤架忙碌，等待{wait_time:.0f}秒",
            f"计时开始，等待{wait_time:.0f}秒", f"烤架忙碌，{wait_num}人在排队",
            f"文火慢烤{wait_time:.0f}秒"
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
    await tweet_tran_deal(matcher, bot, event, message, adapter, session,
                          session_plug)


@tweet_tran.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            message: v11.Message = CommandArg(),
            adapter: Adapter = AdapterDepend(),
            session: TwitterSession = SessionDepend(TwitterSession),
            session_plug: TwitterPlugSession = SessionPluginDepend(
                TwitterPlugSession)):
    await tweet_tran_deal(matcher, bot, event, message, adapter, session,
                          session_plug)


set_tweet_template = on_command("设置烤推模版",
                                aliases={"设置烤推模板"},
                                permission=SUPERUSER | GROUP_ADMIN
                                | GROUP_OWNER,
                                block=True)


@set_tweet_template.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            message: v11.Message = CommandArg(),
            adapter: Adapter = AdapterDepend(),
            session: TwitterSession = SessionDepend(TwitterSession),
            session_plug: TwitterPlugSession = SessionPluginDepend(
                TwitterPlugSession)):
    maximgnum = 3  # 至多允许几张图
    imgnum = 0
    msg = ""
    for msgseg in message:
        if msgseg.is_text():
            msg += msgseg.data.get("text", "")
        elif msgseg.type == "image":
            url = msgseg.data.get("url", "")
            if url:
                msg += f'<img src="data:image/jpg;base64,{await download_to_base64(url)}" alt="图片"/>'
                imgnum += 1
                if imgnum <= maximgnum:
                    continue
                finish_msgs = ["图太多啦", "不要放置太多图片哦！", f"{maximgnum}张图，不能再多了！"]
                await matcher.finish(finish_msgs[random.randint(
                    0,
                    len(finish_msgs) - 1)])
    async with session:
        session.default_template = msg

    finish_msgs = ["设置成功~", "成功啦", "成功设置！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


class TweetUserArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "用户参数"
        des = "用户参数"

    user_search: str = Field.Str("用户")

    def __init__(self) -> None:
        super().__init__([self.user_search])


set_tweet_user_template = on_command("设置用户烤推模版",
                                     aliases={"设置用户烤推模板"},
                                     permission=SUPERUSER | GROUP_ADMIN
                                     | GROUP_OWNER,
                                     block=True)


@set_tweet_user_template.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            message: v11.Message = CommandArg(),
            adapter: Adapter = AdapterDepend(),
            session: TwitterSession = SessionDepend(TwitterSession),
            session_plug: TwitterPlugSession = SessionPluginDepend(
                TwitterPlugSession)):
    msg = ""
    for msgseg in message:
        if msgseg.is_text():
            msg += msgseg.data.get("text", "")
        elif msgseg.type == "image":
            url = msgseg.data.get("url", "")
            if url:
                msg += f'<img src="data:image/jpg;base64,{await download_to_base64(url)}" alt="图片"/>'
    arg = TweetUserArg()(msg)
    user = await get_user_from_search(arg.user_search, await
                                      SUPERUSER(bot, event))
    if not user:
        finish_msgs = ["没有找到用户哦！", "找不到用户哦……", "谁？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    async with session:
        if arg.tail.strip():
            session.template_map[user.username] = arg.tail
        else:
            if user.username in session.template_map:
                del session.template_map[user.username]

    finish_msgs = ["设置成功~", "成功啦", f"成功设置{user.name}的模版！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


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
        msg += "\n{0} | {1}".format(
            tran_model.id, tran_model.trans_text[:10].replace('\n', ''))

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
        msg += "\n{0} | {1}".format(
            tran_model.id, tran_model.trans_text[:10].replace('\n', ''))

    await matcher.finish(msg)


tweet_tran_engine_status = on_command("烤推引擎状态",
                                      rule=only_command(),
                                      permission=SUPERUSER,
                                      block=True)


@tweet_tran_engine_status.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    status_strs = [
        '繁忙' if twitterTransManage.queue.queue_status[status] else '空闲'
        for status in twitterTransManage.queue.queue_status
    ]
    await matcher.finish(
        f"待处理任务数：{twitterTransManage.queue.queue.qsize()}/{twitterTransManage.queue.queue_size}\n"
        f"平均处理时间：{twitterTransManage.queue.avg_deal_ms()/1000:.2f}s\n"
        f"并行处理数：{twitterTransManage.queue.concurrent}\n"
        f"并行处理状态：{'、'.join(status_strs)}")


tweet_tran_status = on_command("烤推状态",
                               aliases={"烤架状态", "烤架"},
                               rule=only_command(),
                               block=True)


@tweet_tran_status.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    finish_msgs = ["烤架~烤架~烤架~\n", "目前是这样，", f"好，有"]
    queue = twitterTransManage.queue
    msg = finish_msgs[random.randint(0, len(finish_msgs) - 1)]
    await matcher.finish(
        f"{msg}"
        f"{queue.queue.qsize() + await queue.get_deal_loop_count()}"
        f"个在烤，烤架大小{queue.queue_size + queue.concurrent}")


class TransIdArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "烤推参数"
        des = "烤推参数"

    tran_id: int = Field.Int("烤推结果序号", min=0)

    def __init__(self) -> None:
        super().__init__([self.tran_id])


tweet_tran_history_view = on_command("烤推结果",
                                     aliases={"查看烤推结果", "查看烤推", "查看烤推历史"},
                                     rule=perm_check_rule("烤推"),
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
    await matcher.finish(msg)


tweet_tran_help = on_command("烤推帮助",
                             aliases={"烤推机帮助", "烤推姬帮助"},
                             rule=only_command() & perm_check_rule("烤推"),
                             block=True)


@tweet_tran_help.handle({
    RateLimitDepend(RateLimitUtil.QPS(0.1)),
})
@matcher_exception_try()
async def _(matcher: Matcher):
    await matcher.finish(
        "格式\n"
        "##序号/推文链接 ##标记 内容\n"
        "正文标记：回复、引用、替换图片、投票、层x\n"
        "选项：覆盖、回复、模版\n"
        "标记为空时默认为回复或主推文，序号之后的空格(或者换行)是必要的，标记后可以不包含空格\n"
        "默认情况下不覆盖，默认模版为翻译自日语\n"
        "例\n"
        "烤推 ##序号 内容\n"
        "烤转评 ##序号 内容 ##引用 看这里\n"
        "烤投票 ##序号 精神状态 ##投票1 摸鱼 ##投票2 开摆desu ##投票3 活着\n"
        "烤回复 ##序号 ##阿哲 ##引用 如果有引用推文，可以这样烤 ##这是回复1 ##这是回复2\n"
        "注意，回复超过回复链时会自动截断，烤制指定回复可以使用层x标记(x为整数)\n"
        ">警告< 译文前两个字与标记重复时将产生识别错误，可通过在译文前添加\\i解决 例如 ##\\i图片 不会被识别为图片标记\n"
        "管理员通过`设置烤推模版 内容`可以设置默认参数")


tweet_help = on_command("转推配置帮助",
                        aliases={"转推帮助"},
                        rule=only_command() & perm_check_rule("烤推"),
                        block=True)


@tweet_help.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    await matcher.finish("推特配置选项 机翻、相关、转推、转评、回复、昵称、描述、头像、粉丝数、重置及`-用户资料`")


tweet_tran_reload_script = on_command("重载烤推脚本",
                                      permission=SUPERUSER,
                                      rule=only_command(),
                                      block=True)


@tweet_tran_reload_script.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    await twitterTransManage.reload_script()
    await matcher.finish("完成")


tweet_tran_reload_inreload = False
tweet_tran_reload = on_command("重启烤推引擎",
                               permission=SUPERUSER,
                               rule=only_command(),
                               block=True)


@tweet_tran_reload.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    if not twitterTransManage.twitter_trans._enable:
        await matcher.finish("引擎离线，可能正在重启！")
    if tweet_tran_reload_inreload:
        await matcher.finish("正在重启，请勿重复使用此命令")
    await matcher.pause(f">>警告，导致烤推功能暂不可用，回复`确认`继续<<")


@tweet_tran_reload.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.Event,
            message: v11.Message = EventMessage()):
    msg = str(message).strip()
    if msg == "确认":
        if not twitterTransManage.twitter_trans._enable:
            global tweet_tran_reload_inreload
            tweet_tran_reload_inreload = False
            await matcher.finish("引擎离线，可能正在重启！")

        @inhibiting_exception()
        async def restart():
            global tweet_tran_reload_inreload
            tweet_tran_reload_inreload = True
            await twitterTransManage.restart()
            tweet_tran_reload_inreload = False
            await bot.send(event, "重新启动完成")

        asyncio.gather(restart())
        await matcher.finish("开始重启，可能需要60秒时间，请耐心等待~")
    await matcher.finish("取消操作")


tweet_tran_update_script = on_command("更新烤推脚本",
                                      permission=SUPERUSER,
                                      rule=only_command(),
                                      block=True)


@tweet_tran_update_script.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    os.system(
        "nohup sh -c 'git fetch && git checkout origin/master -- twitter_trans_script.js' >/dev/null 2>&1 &"
    )
    await matcher.finish("已自动执行更新脚本")


tweet_tran_update_and_reload_script = on_command("更新并重载烤推脚本",
                                                 permission=SUPERUSER,
                                                 rule=only_command(),
                                                 block=True)


@tweet_tran_update_and_reload_script.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    os.system(
        "nohup sh -c 'git fetch && git checkout origin/master -- twitter_trans_script.js' >/dev/null 2>&1 &"
    )
    await matcher.send("执行更新脚本，请等待……")
    await asyncio.sleep(15)
    await twitterTransManage.reload_script()
    await matcher.finish("更新完成")
