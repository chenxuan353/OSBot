from functools import partial
import random
import re
import time
from typing import Any, Dict, List, Optional
from nonebot import on_command, on_startswith, on_message, require
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.params import CommandArg, EventMessage
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.adapters.onebot import v11
from .config import config, TransSession, StreamUnit
from .logger import logger
from .engine import Engine, langs as base_langs, EngineError, deal_trans_text
from .engine.caiyun_engine import CaiyunEngine
from .engine.google_engine import GoogleEngine
from .engine.tencent_engine import TencentEngine
from .engine.baidu_engine import BaiduEngine

from ..os_bot_base.depends import SessionDepend, ArgMatchDepend
from ..os_bot_base import ArgMatch, Field, matcher_exception_try, Adapter, AdapterDepend, AdapterFactory
from ..os_bot_base import only_command
from ..os_bot_base.permission import PermManage, perm_check_permission
from ..os_bot_base.util import RateLimitDepend, RateLimitUtil

PermManage.register("机翻", "机翻权限", True, only_super_oprate=False)
on_command = partial(on_command, block=True)

_engines: List["Engine"] = [
    GoogleEngine(),
    CaiyunEngine(),
    TencentEngine(),
    BaiduEngine()
]

engines: Dict[str, "Engine"] = {}
engines_limit: Dict[str, List[Any]] = {}

for e in _engines:
    engines[e.name] = e
    engines_limit[e.name] = e.alias

try:
    default_engine: "Engine" = None  # type: ignore
    for e in _engines:
        if config.trans_default_engine.strip().lower() == e.name:
            default_engine = e
        if config.trans_default_engine.strip().lower() in e.alias:
            default_engine = e
    if default_engine is None:
        raise KeyError()
    default_engine_name: str = default_engine.name
except KeyError:
    logger.error("默认引擎配置错误，请检查trans_default_engine的配置")
    default_engine: "Engine" = _engines[0]
    default_engine_name: str = default_engine.name


def getLangCN(lang: str):
    return base_langs[lang][0]


engine_help = "目前支持的引擎：谷歌、腾讯、百度、彩云(彩云小译)"


class TransArgs(ArgMatch):

    class Meta(ArgMatch.Meta):  # noqa F811
        name = "机翻参数"
        des = "匹配机翻引擎参数"

    engine: str = Field.Keys("引擎",
                             keys=engines_limit,
                             default=default_engine_name,
                             help=engine_help,
                             require=False)

    source: str = Field.Keys("源语言",
                             keys=base_langs,
                             default="auto",
                             require=False)

    target: str = Field.Keys("目标语言",
                             keys=base_langs,
                             default="zh-cn",
                             require=False)

    def __init__(self) -> None:
        super().__init__([self.engine, self.source, self.target])


async def trans_before_handle(source, target, text, deftarget="ja"):
    """
        在翻译之前对语言进行简单识别

        用于优化用户体验及翻译准确度
    """
    if not config.trans_lang_optimize:
        return source, target, text
    text = deal_trans_text(text)  # 处理字符串
    if not text:
        return source, target, text
    if source == 'auto' and target == 'zh-cn':
        if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7A3]', text):
            target = deftarget
        if re.search(r'[\uAC00-\uD7A3]', text):
            source = 'ko'
            target = 'zh-cn'
        elif re.search(r'[ぁ-んァ-ヶ]', text):
            source = 'ja'
            target = 'zh-cn'
        elif re.match(r"""^[A-Za-z\s,\\.'"]+$""", text):
            source = 'en'
            target = 'zh-cn'
        else:
            pass
    return source, target, text


class DefTransArgs(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "机翻参数"
        des = "匹配机翻引擎参数"

    target: str = Field.Keys("目标语言",
                             keys=base_langs,
                             default="ja",
                             require=False)

    def __init__(self) -> None:
        super().__init__([self.target])


set_def_trans = on_command("设置默认翻译语言",
                           aliases={"设置默认语言"},
                           priority=2,
                           permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)


@set_def_trans.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: DefTransArgs = ArgMatchDepend(DefTransArgs),
            session: TransSession = SessionDepend()):
    if session.default_trans == arg.target:
        finish_msgs = ["重复啦", "没有变化哟", "重 复 啦"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    async with session:
        session.default_trans = arg.target
    lang_cn = getLangCN(arg.target)
    finish_msgs = [f"已设置为{lang_cn}了哦", "设置完毕！", "已完成调整>>"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


trans = on_command("翻译",
                   aliases={"机翻"},
                   permission=perm_check_permission("机翻") | GROUP_ADMIN
                   | GROUP_OWNER | SUPERUSER)

trans_msg = on_startswith("机翻",
                          priority=4,
                          block=True,
                          permission=perm_check_permission("机翻") | GROUP_ADMIN
                          | GROUP_OWNER | SUPERUSER)


async def trans_handle(matcher: Matcher, arg: TransArgs, session: TransSession,
                       bot: Bot, event: Event):
    engine: Engine = engines[arg.engine]
    adapter = AdapterFactory.get_adapter(bot)
    source = arg.source
    target = arg.target
    text = arg.tail.strip()
    default_trans = session.default_trans
    if text.startswith("#"):
        try:
            from ..os_bot_twitter.os_bot_trans_interface import trans_tran_tweet
            tweet = await trans_tran_tweet(matcher, bot, event, text)
            text = tweet.text
            default_trans = "zh-cn"
        except ImportError as e:
            pass
    source, target, text = await trans_before_handle(source, target, text,
                                                     default_trans)
    if not text:
        await matcher.finish()
    if not engine.check_source_lang(source):
        await matcher.finish(F"{engine.name}不支持{getLangCN(source)}哦")
    if not engine.check_lang(source, target):
        await matcher.finish(
            F"{engine.name}的{getLangCN(source)}语言，不支持翻译到{getLangCN(target)}哦")
    try:
        res = await engine.trans(source, target, text)
        logger.debug(
            F"{engine.name}引擎翻译({source}->{target})：{text} -> {res.strip()}")
    except EngineError as e:
        logger.opt(exception=True).warning(F"翻译引擎异常：{repr(e)}")
        await matcher.finish(F"引擎错误：{e.replay}")
    user_id = await adapter.get_unit_id_from_event(bot, event)
    group_id = await adapter.get_group_id_from_event(
        bot, event) if await adapter.msg_is_multi_group(bot, event) else None
    await matcher.finish(
        f"@{await adapter.get_unit_nick(user_id, group_id=group_id)} 翻：{res.strip().replace('{', '').replace('}', '')}"
    )


@trans.handle(parameterless=[
    RateLimitDepend(RateLimitUtil.QPS(5), scope=RateLimitUtil.SCOPE_HANDLE),
    RateLimitDepend(RateLimitUtil.PER_M(15))
])
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: Event,
            arg: TransArgs = ArgMatchDepend(TransArgs),
            session: TransSession = SessionDepend()):
    await trans_handle(matcher, arg, session, bot, event)


@trans_msg.handle(parameterless=[
    RateLimitDepend(RateLimitUtil.QPS(5), scope=RateLimitUtil.SCOPE_HANDLE),
    RateLimitDepend(RateLimitUtil.PER_M(10))
])
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: Event,
            session: TransSession = SessionDepend()):
    text = event.get_plaintext().strip()
    if text.startswith("机翻"):
        text = text[len("机翻"):]
    else:
        await matcher.finish()
    arg = TransArgs()(text)
    await trans_handle(matcher, arg, session, bot, event)


class StreamArgs(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "机翻参数"
        des = "匹配机翻引擎参数"

    switch: bool = Field.Bool("状态", require=False)

    unit_uuid: int = Field.Int("开启流式翻译的对象",
                               min=9999,
                               max=99999999999,
                               require=False)

    engine: str = Field.Keys("引擎",
                             keys=engines_limit,
                             default=default_engine_name,
                             help=engine_help,
                             require=False)

    source: str = Field.Keys("源语言",
                             keys=base_langs,
                             default="auto",
                             require=False)

    target: str = Field.Keys("目标语言",
                             keys=base_langs,
                             default="zh-cn",
                             require=False)

    def __init__(self) -> None:
        super().__init__([
            self.switch, self.unit_uuid, self.engine, self.source, self.target
        ])


stream = on_command("流式翻译",
                    aliases={"自动翻译", "全自动翻译"},
                    priority=4,
                    permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)


@stream.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            message: v11.Message = CommandArg(),
            session: TransSession = SessionDepend(),
            adapter: Adapter = AdapterDepend()):
    arg: StreamArgs = StreamArgs()
    text = ArgMatch.message_to_str(message)
    arg = arg(text)

    streamlist = session.stream_list
    unit_uuit: Optional[int] = arg.unit_uuid if arg.unit_uuid else None
    if unit_uuit is None:
        unit_uuit = event.user_id
    if arg.switch is None:
        arg.switch = not (unit_uuit in streamlist)

    group_id = event.group_id if isinstance(event,
                                            v11.GroupMessageEvent) else None

    unit_nick = await adapter.get_unit_nick(unit_uuit, group_id=group_id)
    if not arg.switch:
        if unit_uuit not in streamlist:
            await stream.finish("不在翻译中的样子，再检查一下……？")
        async with session:
            del streamlist[unit_uuit]

        finish_msgs = [
            f"{unit_nick}从翻译列表中拿走啦", f"{unit_nick}的翻译成功关闭>>", "remove!"
        ]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if unit_uuit in streamlist:
        finish_msgs = [
            f"{unit_nick}已经在列表中咯", "不许重复加入！", ">>重复加入<<", "让我数数，已经有了……？"
        ]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    # 开启流式翻译
    engine: Engine = engines[arg.engine]
    source = arg.source
    target = arg.target
    oprate_log = f"{await adapter.mark(bot, event)}_{time.strftime('%Y-%m-%d %H:%M:%S')}"  # 溯源信息
    if not engine.check_source_lang(source):
        await matcher.finish(F"{engine.name}不支持{getLangCN(source)}哦")
    if not engine.check_lang(source, target):
        await matcher.finish(
            F"{engine.name}不支持{getLangCN(source)}到{getLangCN(target)}哦")

    async with session:
        streamlist[unit_uuit] = StreamUnit(user_id=unit_uuit,
                                           engine=arg.engine,
                                           source=source,
                                           target=target,
                                           oprate_log=oprate_log)

    finish_msgs = [f"{unit_nick}现已加入", "完成了", "一切OK！", f"{unit_nick}加入了翻译列表"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


trans_engine_list = on_command("翻译引擎列表",
                               aliases={"机翻引擎列表"},
                               priority=2,
                               rule=only_command(),
                               permission=GROUP_ADMIN | GROUP_OWNER
                               | SUPERUSER)


@trans_engine_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    engine_names = []
    for engine_name in engines:
        if engines[engine_name].enable:
            engine_names.append(engine_name)
    await matcher.finish(f"当前启用：{'、'.join(engine_names)}")


stream_list = on_command("查看流式翻译列表",
                         aliases={"打开流式翻译列表", "翻译列表", "流式翻译列表"},
                         priority=2,
                         rule=only_command(),
                         permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)


@stream_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            session: TransSession = SessionDepend(),
            adapter: Adapter = AdapterDepend()):
    streamlist = session.stream_list
    if len(streamlist) == 0:
        finish_msgs = ["列表空荡荡……", "空空如也", "列表就像咱的钱包，空荡荡♪"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    group_id = event.group_id if isinstance(event,
                                            v11.GroupMessageEvent) else None

    if len(streamlist) == 1:
        for uid in streamlist:
            await matcher.finish(
                f"只有{await adapter.get_unit_nick(uid, bot, group_id=group_id)}在列表中~"
            )

    nicks = []
    for uid in streamlist:
        nicks.append(
            f"{await adapter.get_unit_nick(uid, bot, group_id=group_id)}")
    await matcher.finish(f"列表！\n{'、'.join(nicks)}")


stream_clear = on_command("清空流式翻译列表",
                          aliases={"清空流式翻译", "流式翻译列表清空", "流式翻译清空"},
                          priority=3,
                          rule=only_command(),
                          permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)


@stream_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher, session: TransSession = SessionDepend()):
    streamlist = session.stream_list
    if len(streamlist) == 0:
        finish_msgs = ["列表空荡荡……", "空空如也", "列表就像咱的钱包，空荡荡♪"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    finish_msgs = ["请发送`确认清空`确认~", "通过`确认清空`继续操作哦"]
    await matcher.pause(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


@stream_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            message: v11.Message = EventMessage(),
            session: TransSession = SessionDepend()):
    streamlist = session.stream_list
    msg = str(message).strip()
    if msg == "确认清空":
        async with session:
            streamlist.clear()
        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["未确认操作", "操作已取消"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


try:
    require('os_bot_shutup')
    from ..os_bot_shutup.const import STATE_PASSIVE_IGNORE
    stream_spy_state = {STATE_PASSIVE_IGNORE: True}
except Exception:
    stream_spy_state = {}

stream_spy = on_message(priority=5,
                        block=False,
                        rule=None,
                        state=stream_spy_state)


@stream_spy.handle()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            session: TransSession = SessionDepend()):
    streamlist = session.stream_list
    if event.user_id in streamlist:
        item = streamlist[event.user_id]
        engine: "Engine" = engines[item.engine]
        source = "auto"
        target = item.target
        msg = event.get_plaintext().strip()
        msg = msg.replace("{", "").replace("}", "").strip()
        source, target, msg = await trans_before_handle(source, target, msg)
        if not msg:
            await matcher.finish()
        try:
            res = await engine.trans(source, target, msg)
            res = res.replace("{", "").replace("}", "")
        except EngineError as e:
            logger.opt(exception=True).warning(F"翻译引擎异常：{repr(e)}")
            await matcher.finish()
        await matcher.finish(f"翻:{res}")
