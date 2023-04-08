from functools import partial
import random
from time import time
from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import MessageEvent


def only_command():
    """
        匹配无参数命令
    """

    async def checker(msg: Message = CommandArg()) -> bool:
        return not msg

    return Rule(checker)


pa = on_command("爪巴", aliases={"爬"}, block=True, rule=only_command())


@pa.handle()
async def _(matcher: Matcher):
    finish_msgs = ('我爬 我现在就爬Orz', '我爪巴', '你给爷爬OuO', '呜呜呜别骂了 再骂就傻了TAT',
                   '就不爬>_<', '欺负可爱BOT 建议超级加倍TuT')
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


zaima = on_command("在吗",
                   aliases={"zaima", "在", "zai"},
                   block=True)


@zaima.handle()
async def _(matcher: Matcher):
    finish_msgs = ('不在', '…！', '在！', '嗯', '嗯？', '~', '不在！')
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


ping = on_command("ping", block=True, rule=only_command())


@ping.handle()
async def _(matcher: Matcher, event: MessageEvent):
    delay = int(time() - event.time)
    if delay > 9:
        delay = "∞"
    if delay == 0:
        delay = ""
    finish_msgs = ('pang!', '咚!', "duang!", "哼!")
    await matcher.finish(
        f"{finish_msgs[random.randint(0, len(finish_msgs) - 1)]} {delay}".
        strip())
