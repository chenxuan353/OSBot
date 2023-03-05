from functools import partial
import random
from time import time
from nonebot import on_command as base_on_command
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent

on_command = partial(base_on_command, block=True)

pa = on_command("爪巴", aliases={"爬"}, block=True)


@pa.handle()
async def _(matcher: Matcher):
    finish_msgs = ('我爬 我现在就爬Orz', '我爪巴', '你给爷爬OuO', '呜呜呜别骂了 再骂就傻了TAT',
                   '就不爬>_<', '欺负可爱BOT 建议超级加倍TuT')
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


zaima = on_command("在吗", block=True, aliases={"zaima", "在", "zai"})


@zaima.handle()
async def _(matcher: Matcher):
    finish_msgs = ('不在', '…！', '在！', '嗯', '嗯？', '~', '不在！')
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


ping = on_command("ping", block=True)


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
