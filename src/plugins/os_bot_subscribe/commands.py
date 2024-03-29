import math
import random
from typing import Any, Dict, Optional, Union
from nonebot import on_command
from nonebot.adapters import Bot
from nonebot.matcher import Matcher
from nonebot.params import EventMessage
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from .channel.channel import Channel
from .channel.factory import ChannelFactory
from .model import SubscribeModel
from .logger import logger

from ..os_bot_base.argmatch import ArgMatch, Field, PageArgMatch
from ..os_bot_base.util import matcher_exception_try, only_command
from ..os_bot_base.depends import ArgMatchDepend, AdapterDepend, Adapter
from ..os_bot_base.notice import BotSend, LeaveGroupHook
from ..os_bot_base.adapter.onebot import V11Adapter


class ChannelArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "频道匹配"
        des = "匹配频道参数"

    channel: Optional[Channel] = Field.Keys(
        "频道",
        keys_generate=lambda: ChannelFactory.get_instance().channel_alias_map,
        require=False)
    subscribe: str = Field.Str("订阅标识")

    def __init__(self) -> None:
        super().__init__([self.channel, self.subscribe])


subscribe = on_command(
    "订阅",
    block=True,
    permission=SUPERUSER,
)


@subscribe.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: ChannelArg = ArgMatchDepend(ChannelArg),
            adapter: Adapter = AdapterDepend()):
    subscribe_arg = arg.subscribe.strip()
    channel: Optional[Channel] = arg.channel
    option_str: str = arg.tail.strip()
    subscribe_state: Dict[str, Any] = {}
    if not channel:
        # 没有匹配到频道时尝试遍历取得
        for match_channel in ChannelFactory.get_instance().channels:
            if await match_channel.precheck(subscribe_arg, option_str,
                                            subscribe_state, await
                                            match_channel.get_session()):
                channel = match_channel
                break

    if not channel:
        finish_msgs = ["不确定要订阅什么哦！", "无法确定频道哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    subscribe = await channel.deal_subscribe(subscribe_arg, subscribe_state,
                                             await channel.get_session())
    group_mark = await adapter.mark_group_without_drive(bot, event)
    subscribe_model = await SubscribeModel.get_or_none(
        group_mark=group_mark,
        channel_type=channel.channel_type,
        channel_subtype=channel.channel_subtype,
        channel_id=channel.channel_id,
        subscribe=subscribe)
    if subscribe_model:
        finish_msgs = ["不能重复订阅！", "不能重复订阅哦！", "已经订阅过了喲"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    subscribe_model = SubscribeModel()
    subscribe_model.group_mark = group_mark
    subscribe_model.channel_type = channel.channel_type
    subscribe_model.channel_subtype = channel.channel_subtype
    subscribe_model.channel_id = channel.channel_id
    subscribe_model.subscribe = subscribe
    subscribe_model.drive_mark = await adapter.mark_drive(bot, event)
    subscribe_model.bot_type = adapter.get_type()
    subscribe_model.bot_id = await adapter.get_bot_id(bot, event)
    subscribe_model.options = {}
    subscribe_model.options = channel.deal_options(subscribe_model, option_str,
                                                   await channel.get_session())

    subscribe_model.send_param = await BotSend.pkg_send_params(bot, event)

    await subscribe_model.save()
    await channel.subscribe_update()
    finish_msgs = ["订阅成功~", "成功啦", "好，已经加入订阅啦。"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


unsubscribe = on_command(
    "取消订阅",
    block=True,
    permission=SUPERUSER,
)


@unsubscribe.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: ChannelArg = ArgMatchDepend(ChannelArg),
            adapter: Adapter = AdapterDepend()):
    subscribe_arg = arg.subscribe.strip()
    channel: Optional[Channel] = arg.channel
    option_str: str = arg.tail.strip()
    subscribe_state: Dict[str, Any] = {}
    if not channel:
        # 没有匹配到频道时尝试遍历取得
        for match_channel in ChannelFactory.get_instance().channels:
            options = {}
            if await match_channel.precheck(subscribe_arg, option_str,
                                            subscribe_state, await
                                            match_channel.get_session()):
                channel = match_channel
                break

    if not channel:
        finish_msgs = ["不确定要订阅什么哦！", "无法确定频道哦！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    subscribe = await channel.deal_subscribe(subscribe_arg, subscribe_state,
                                             await channel.get_session())
    group_mark = await adapter.mark_group_without_drive(bot, event)
    subscribe_model = await SubscribeModel.get_or_none(
        group_mark=group_mark,
        channel_type=channel.channel_type,
        channel_subtype=channel.channel_subtype,
        channel_id=channel.channel_id,
        subscribe=subscribe)
    if not subscribe_model:
        finish_msgs = ["订阅不存在", "没有这个订阅哦", "或许……它不存在？"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    await subscribe_model.delete()
    await channel.subscribe_update()

    finish_msgs = ["取消工作完成啦", "已取消订阅", "从订阅中移除啦"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


subscribe_settings = on_command(
    "订阅配置",
    aliases={"配置订阅"},
    block=True,
    permission=SUPERUSER,
)


@subscribe_settings.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: ChannelArg = ArgMatchDepend(ChannelArg),
            adapter: Adapter = AdapterDepend()):
    subscribe_arg = arg.subscribe.strip()
    channel: Optional[Channel] = arg.channel
    option_str: str = arg.tail.strip()
    subscribe_state: Dict[str, Any] = {}
    if not channel:
        # 没有匹配到频道时尝试遍历取得
        for match_channel in ChannelFactory.get_instance().channels:
            options = {}
            if await match_channel.precheck(subscribe_arg, option_str,
                                            subscribe_state, await
                                            match_channel.get_session()):
                channel = match_channel
                break

    if not channel:
        finish_msgs = ["不确定要订阅什么哦！", "频道的确定是必要的！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    subscribe = await channel.deal_subscribe(subscribe_arg, subscribe_state,
                                             await channel.get_session())
    group_mark = await adapter.mark_group_without_drive(bot, event)
    subscribe_model = await SubscribeModel.get_or_none(
        group_mark=group_mark,
        channel_type=channel.channel_type,
        channel_subtype=channel.channel_subtype,
        channel_id=channel.channel_id,
        subscribe=subscribe)
    if not subscribe_model:
        finish_msgs = ["订阅不存在", "没有这个订阅哦"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    if not option_str.strip():
        model_option_str = channel.options_to_string(
            subscribe_model.options, await channel.get_session())
        finish_msgs = ["配置 ", "ok~ ", "有这些 "]
        await matcher.finish(
            finish_msgs[random.randint(0,
                                       len(finish_msgs) - 1)] +
            model_option_str)

    subscribe_model.options = channel.update_options(
        subscribe_model, option_str, await channel.get_session())

    await subscribe_model.save()
    await channel.subscribe_update()

    finish_msgs = ["已更新~", "更新成功啦", "配置完成！"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


subscribe_list = on_command(
    "订阅列表",
    block=True,
    permission=SUPERUSER,
)


@subscribe_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch),
            adapter: Adapter = AdapterDepend()):
    group_mark = await adapter.mark_group_without_drive(bot, event)
    size = 5
    count = await SubscribeModel.filter(group_mark=group_mark).count()
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["暂无订阅~", "没有找到订阅哟", "订阅为空！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    models = await SubscribeModel.filter(group_mark=group_mark).offset(
        (arg.page - 1) * size).limit(size).order_by("-id")

    msg = f"{arg.page}/{maxpage}"
    for model in models:
        channel = ChannelFactory.get_instance().channel_name_map[
            model.channel_id]
        info = channel.get_subscribe_info(model.subscribe, await
                                          channel.get_session())
        if info:
            msg += f"\n{model.id} | {info.title} | {channel.options_to_string(model.options, await channel.get_session())}"
        else:
            msg += f"\n{model.id} | - | {channel.options_to_string(model.options, await channel.get_session())}"

    await matcher.finish(msg)


subscribe_clear = on_command(
    "清空订阅",
    block=True,
    rule=only_command(),
    permission=SUPERUSER,
)


@subscribe_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend()):
    group_mark = await adapter.mark_group_without_drive(bot, event)
    if not await SubscribeModel.filter(group_mark=group_mark).exists():
        await matcher.finish("订阅列表就是空的哟")
    await matcher.pause(f">>发送确认清空以继续操作<<")


@subscribe_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: v11.MessageEvent,
            message: v11.Message = EventMessage(),
            adapter: Adapter = AdapterDepend()):
    msg = str(message).strip()
    if msg == "确认清空":
        group_mark = await adapter.mark_group_without_drive(bot, event)
        await SubscribeModel.filter(group_mark=group_mark).delete()
        # twitter_subscribe_invalid_cache()
        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["未确认操作", "操作已取消"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


async def level_group_hook(group_id: int, bot_id: int) -> None:
    try:
        group_mark = f"{V11Adapter.get_type()}-global-group-{group_id}"
        await SubscribeModel.filter(group_mark=group_mark).delete()
    except Exception as e:
        logger.opt(exception=True).error("`SubscribeModel`退群处理时异常")


LeaveGroupHook.get_instance().add_hook(level_group_hook)

global_subscribe_list = on_command(
    "全局订阅列表",
    block=True,
    permission=SUPERUSER,
)


@global_subscribe_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    size = 5
    count = await SubscribeModel.all().only("channel_id",
                                            "subscribe").distinct().count()
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["暂无订阅~", "没有找到订阅哟", "订阅为空！"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    models = await SubscribeModel.all().only("channel_id", "subscribe").offset(
        (arg.page - 1) * size).limit(size)

    msg = f"{arg.page}/{maxpage}"
    for model in models:
        channel = ChannelFactory.get_instance().channel_name_map[
            model.channel_id]
        info = channel.get_subscribe_info(model.subscribe, await
                                          channel.get_session())
        if info:
            msg += f"\n{channel.name} | {model.subscribe} | {info.title}"
        else:
            msg += f"\n{channel.name} | {model.subscribe} | -"

    await matcher.finish(msg)
