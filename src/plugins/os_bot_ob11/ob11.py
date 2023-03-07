from typing import Optional
from nonebot import on_command
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from ..os_bot_base.cache.onebot import GroupRecord
from ..os_bot_base.argmatch import ArgMatch, Field
from ..os_bot_base.depends import Adapter, AdapterDepend, OBCacheDepend, ArgMatchDepend, OnebotCache
from ..os_bot_base.util import matcher_exception_try


class SetGroupCardArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "设置群名片参数"
        des = "设置群名片参数"

    group_id: int = Field.Int("群ID", min=9999, max=99999999999)

    card: str = Field.Str("名片", default="", require=False, min=0, max=40)

    def __init__(self) -> None:
        super().__init__([self.group_id, self.card])


set_group_card = on_command("设置群名片", block=True, permission=SUPERUSER)


@set_group_card.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.GroupMessageEvent,
            msg: v11.Message = CommandArg(),
            cache: OnebotCache = OBCacheDepend(),
            adapter: Adapter = AdapterDepend()):
    bot_record = cache.get_bot_record(int(bot.self_id))
    if not bot_record:
        await matcher.finish()

    group: Optional[GroupRecord] = bot_record.get_group_record(event.group_id)

    if not group:
        await matcher.finish()

    card = msg.extract_plain_text().strip()
    await bot.set_group_card(group_id=group.id,
                             user_id=int(bot.self_id),
                             card=card)

    await matcher.finish(
        f"咱的名片设置为 {card or '与昵称一致'} 啦")


@set_group_card.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.PrivateMessageEvent,
            arg: SetGroupCardArg = ArgMatchDepend(SetGroupCardArg),
            cache: OnebotCache = OBCacheDepend(),
            adapter: Adapter = AdapterDepend()):
    bot_record = cache.get_bot_record(int(bot.self_id))
    if not bot_record:
        await matcher.finish()

    group: Optional[GroupRecord] = bot_record.get_group_record(arg.group_id)

    if not group:
        await matcher.finish()
    if not group:
        await matcher.finish("没有找到这个群哦！")
    await bot.set_group_card(group_id=arg.group_id,
                             user_id=int(bot.self_id),
                             card=arg.card)

    await matcher.finish(
        f"已将{group.get_nick()}({group.id})内咱的名片设置为{arg.card or '与昵称一致'}")
