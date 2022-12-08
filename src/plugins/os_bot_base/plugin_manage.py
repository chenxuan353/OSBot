"""
    插件管理器

    半侵入式，管理插件分群开关，生成插件帮助。

    当插件存在复杂逻辑时，完整的开关需要配合本插件管理器的`API`使用。
"""
from json import load
import math
import random
import textwrap
from typing import Dict, List
from functools import partial
from nonebot.exception import IgnoredException
from nonebot.adapters import Bot, Event
from nonebot.message import run_preprocessor
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot import get_driver, get_loaded_plugins, on_command
from cacheout import LRUCache
from cacheout.memoization import lru_memoize
from .model.plugin_manage import PluginModel, PluginSwitchModel
from .util import matcher_exception_try, match_suggest, only_command, plug_is_disable
from .consts import META_NO_MANAGE, META_ADMIN_USAGE, META_AUTHOR_KEY, META_DEFAULT_SWITCH
from .depends import AdapterDepend, ArgMatchDepend
from .exception import MatcherErrorFinsh
from .adapter import AdapterFactory, Adapter
from .argmatch import ArgMatch, Field, PageArgMatch
from .logger import logger

on_command = partial(on_command, block=True)
driver = get_driver()
cache_plugin_key_map: Dict[str, str] = {}
cache_plugin_keys: List[str] = []


async def plugin_manage_on_startup():
    """
        这个钩子函数会在 NoneBot2 启动时运行。
    """
    cache_plugin_keys.clear()
    try:
        plugins = get_loaded_plugins()
        await PluginModel.filter().all().update(load=False)
        for plugin in plugins:
            meta = plugin.metadata
            if meta and meta.extra.get(META_NO_MANAGE):
                continue
            if plugin.name == "nonebot_plugin_apscheduler":
                continue
            plugModel = await PluginModel.get_or_none(name=plugin.name)
            if not plugModel:
                plugModel = PluginModel(name=plugin.name)
            plugModel.module_name = plugin.module_name
            plugModel.load = True
            if meta:
                if meta.extra.get(META_AUTHOR_KEY) == "ChenXuan":
                    meta.usage = textwrap.dedent(meta.usage).strip()
                    if meta.extra.get(META_ADMIN_USAGE):
                        meta.extra[META_ADMIN_USAGE] = textwrap.dedent(
                            meta.extra[META_ADMIN_USAGE]).strip()

                plugModel.display_name = meta.name
                plugModel.des = meta.description
                plugModel.usage = meta.usage
                plugModel.admin_usage = meta.extra.get(META_ADMIN_USAGE)
                plugModel.author = meta.extra.get(META_AUTHOR_KEY)
                if plugModel.default_switch is None:
                    plugModel.default_switch = meta.extra.get(
                        META_DEFAULT_SWITCH, True)
            if plugModel.display_name:
                cache_plugin_key_map[plugModel.display_name] = plugModel.name
                cache_plugin_keys.append(plugModel.display_name)
            cache_plugin_key_map[plugModel.name] = plugModel.name
            cache_plugin_keys.append(plugModel.name)
            await plugModel.save()
    except Exception as e:
        logger.opt(exception=True).debug(f"执行插件管理-插件开关启动初始化时异常")
        raise e


@lru_memoize(maxsize=128)
async def _get_plug_model(name: str):
    return await PluginModel.get_or_none(name=name)


@lru_memoize(maxsize=1024)
async def _get_plug_switch_model(name: str, group_mark: str):
    return await PluginSwitchModel.get_or_none(**{
        "name": name,
        "group_mark": group_mark
    })


def plug_model_cache_clear():
    """
        清除插件管理的模型缓存

        此插件已通过内存lrc_cache进行了简单缓存，故出现状态变更后需要刷新缓存。
    """
    cache: LRUCache = _get_plug_model.cache
    cache.clear()
    cache: LRUCache = _get_plug_switch_model.cache
    cache.clear()


@run_preprocessor
async def _(bot: Bot, event: Event, matcher: Matcher):
    """
        这个钩子函数会在 NoneBot2 运行 matcher 前运行。
    """
    plugin = matcher.plugin
    if not plugin:
        return
    meta = plugin.metadata
    if meta and meta.extra.get(META_NO_MANAGE):
        return
    if plugin.name == "nonebot_plugin_apscheduler":
        return
    try:
        adapter = AdapterFactory.get_adapter(bot)
        plugModel = await _get_plug_model(plugin.name)
        if not plugModel:
            logger.debug(f"开关预处理 `{bot.self_id}` `{plugin.name}` 插件缺失主记录")
            return
        if not plugModel.load:
            logger.warning(
                f"开关预处理 `{bot.self_id}` `{plugin.name}` 插件缺失未加载，但仍然在处理消息。")
            raise IgnoredException(f"插件管理器已限制`{plugin.name}`(插件主记录)!")
        group_mark = await adapter.mark_group_without_drive(bot, event)
        plugSwitchModel = await _get_plug_switch_model(plugin.name, group_mark)
        if plugModel and not plugModel.switch:
            raise IgnoredException(f"插件管理器已禁用`{plugin.name}`(插件全局)!")

        if plugSwitchModel:
            if plugSwitchModel.switch:
                logger.debug(
                    f"插件管理器已放行`{plugin.name}`(组设置)! group={group_mark}")
                return
            else:
                raise IgnoredException(
                    f"插件管理器已限制`{plugin.name}`(组设置)! group={group_mark}")
        if plugModel and not plugModel.default_switch:
            raise IgnoredException(f"插件管理器已限制`{plugin.name}`(插件默认值)! group={group_mark}")

        logger.debug(f"插件管理器已放行`{plugin.name}`(插件默认值)! group={group_mark}")
    except IgnoredException as e:
        logger.debug(e.reason)
        raise e
    except Exception as e:
        logger.opt(exception=True).debug(f"{bot.self_id} 执行插件开关预处理时异常")


class ManageArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "插件管理的参数"
        des = "管理插件的开关"

    drive_type: str = Field.Keys(
        "驱动", {
            "ob11": ["onebot11", "gocqhttp"],
        }, default="ob11", require=False)

    group_type: str = Field.Keys(
        "组标识", {
            "group": ["g", "group", "组", "群", "群聊"],
            "private": ["p", "private", "私聊", "好友", "私"],
        })
    group_id: int = Field.Int("组ID", min=9999, max=99999999999)
    plugin_name: str = Field.Keys("插件名称",
                                  keys_generate=lambda: cache_plugin_key_map)
    switch: bool = Field.Bool("状态", require=False)

    def __init__(self) -> None:
        super().__init__(
            [self.drive_type, self.group_type, self.group_id, self.plugin_name,
             self.switch])


class PlugArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "插件名参数"
        des = "匹配插件名"

    plugin_name: str = Field.Keys("插件名称",
                                  keys_generate=lambda: cache_plugin_key_map)

    def __init__(self) -> None:
        super().__init__([self.plugin_name])


async def get_plugin_suggest(name: str) -> List[str]:
    return match_suggest(cache_plugin_keys, name)


async def get_plugin(name: str) -> PluginModel:
    pluginModel = await PluginModel.get_or_none(name=name, load=True)
    if pluginModel is None:
        pluginModel = await PluginModel.get_or_none(display_name=name,
                                                    load=True)
    if pluginModel is None:
        suggest = await get_plugin_suggest(name)
        if suggest:
            raise MatcherErrorFinsh(f"让我看看……{'、'.join(suggest[:5])}是这些吗，是吗是吗？")
        raise MatcherErrorFinsh("啊，连相似的都没找到！")
    return pluginModel


manage = on_command("插件管理", aliases={
    "管理插件",
}, permission=SUPERUSER)


@manage.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: Event,
            arg: ManageArg = ArgMatchDepend(ManageArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    if arg.group_type == "group":
        group_nick = await adapter.get_group_nick(arg.group_id)
    else:
        group_nick = await adapter.get_unit_nick(arg.group_id)
    mark = f"{arg.drive_type}-global-{arg.group_type}-{arg.group_id}"
    entity = {"name": pluginModel.name, "group_mark": mark}
    if arg.switch is None:
        arg.switch = await plug_is_disable(pluginModel.name, mark)
    switchModel = await PluginSwitchModel.get_or_none(**entity)
    if not switchModel:
        switchModel = PluginSwitchModel(**entity)
    elif switchModel.switch == arg.switch:
        await matcher.finish(f"`{group_nick}`的`{pluginModel.display_name}`的状态没有变化哦"
                             )
    switchModel.switch = arg.switch
    await switchModel.save()
    plug_model_cache_clear()
    if not switchModel.switch:
        await matcher.finish(f"已经关掉`{group_nick}`的`{pluginModel.display_name}`了~")
    else:
        await matcher.finish(f"`{group_nick}`的`{pluginModel.display_name}`开了！")


disable_plug = on_command("全局禁用插件",
                          aliases={"全局插件禁用", "全局关闭插件"},
                          permission=SUPERUSER)


@disable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot,
            arg: PlugArg = ArgMatchDepend(PlugArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    if pluginModel.switch == False:
        await matcher.finish(f"{pluginModel.display_name}关得不能再关啦")
    pluginModel.switch = False
    await pluginModel.save()
    plug_model_cache_clear()
    await matcher.finish(f"{pluginModel.display_name} >完全禁止<")


enable_plug = on_command("全局启用插件",
                         aliases={"全局插件启用", "全局打开插件"},
                         permission=SUPERUSER)


@enable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot,
            arg: PlugArg = ArgMatchDepend(PlugArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    if pluginModel.switch == True:
        await matcher.finish(f"{pluginModel.display_name}开过啦")
    pluginModel.switch = True
    await pluginModel.save()
    plug_model_cache_clear()
    await matcher.finish(f"{pluginModel.display_name} >已开启<")


def_disable_plug = on_command("默认禁用插件",
                              aliases={"默认插件禁用", "默认关闭插件"},
                              permission=SUPERUSER)


@def_disable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot,
            arg: PlugArg = ArgMatchDepend(PlugArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    if pluginModel.default_switch == False:
        await matcher.finish(f"{pluginModel.display_name}默认就是关闭的哦！")
    pluginModel.default_switch = False
    await pluginModel.save()
    plug_model_cache_clear()
    await matcher.finish(f"{pluginModel.display_name} >默认禁止<")


def_enable_plug = on_command("默认启用插件",
                             aliases={"默认插件启用", "默认打开插件"},
                             permission=SUPERUSER)


@def_enable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot,
            arg: PlugArg = ArgMatchDepend(PlugArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    if pluginModel.default_switch == True:
        await matcher.finish(f"{pluginModel.display_name}默认就是打开的哦！")
    pluginModel.default_switch = True
    await pluginModel.save()
    plug_model_cache_clear()
    await matcher.finish(f"{pluginModel.display_name} >默认启用<")


disable_plug = on_command("禁用插件",
                          aliases={"插件禁用", "关闭插件"},
                          permission=SUPERUSER)


@disable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: Event,
            arg: PlugArg = ArgMatchDepend(PlugArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    mark = await adapter.mark_group_without_drive(bot, event)
    entity = {"name": pluginModel.name, "group_mark": mark}
    switchModel = await PluginSwitchModel.get_or_none(**entity)
    if not switchModel:
        switchModel = PluginSwitchModel(**entity)
    elif switchModel.switch == False:
        await matcher.finish(f"{pluginModel.display_name}不能再关了…")
    switchModel.switch = False
    await switchModel.save()
    plug_model_cache_clear()
    await matcher.finish(f"{pluginModel.display_name} >关闭<")


enable_plug = on_command("启用插件",
                         aliases={"插件启用", "打开插件"},
                         permission=SUPERUSER)


@enable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: Event,
            arg: PlugArg = ArgMatchDepend(PlugArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    if pluginModel.switch == False:
        await matcher.finish(f"{pluginModel.display_name}在哪里都不能用哦。")
    adapter = AdapterFactory.get_adapter(bot)
    mark = await adapter.mark_group_without_drive(bot, event)
    entity = {"name": pluginModel.name, "group_mark": mark}
    switchModel = await PluginSwitchModel.get_or_none(**entity)
    if not switchModel:
        switchModel = PluginSwitchModel(**entity)
    elif switchModel.switch == True:
        await matcher.finish(f"{pluginModel.display_name}已经开了哦")
    switchModel.switch = True
    await switchModel.save()
    plug_model_cache_clear()
    await matcher.finish(f"{pluginModel.display_name} >启动<")


plug_list = on_command("插件列表", aliases={"pluglist", "功能列表"})


@plug_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: Event,
            adapter: Adapter = AdapterDepend(),
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    size = 5
    count = await PluginModel.filter(load=True).count()
    maxpage = math.ceil(count / size)

    if count == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    plugs = await PluginModel.filter(load=True).offset(
        (arg.page - 1) * size).limit(size)
    msg = f"{arg.page}/{maxpage}"
    for plug in plugs:
        disable = await plug_is_disable(
            plug.name, await adapter.mark_group_without_drive(bot, event))
        msg += f"\n{plug.display_name or plug.name}[{'X' if disable else '√'}] - {plug.des or '没有描述'}"
    await matcher.finish(msg)


admin_plug_help = on_command(
    "管理员插件帮助",
    aliases={"超管功能", "超级管理员功能", "管理员功能帮助", "adminplughelp"},
    priority=3,
    permission=SUPERUSER)


@admin_plug_help.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: Event,
            arg: PlugArg = ArgMatchDepend(PlugArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    try:
        adapter = AdapterFactory.get_adapter(bot)
        group_mark = await adapter.mark_group_without_drive(bot, event)
        plugSwitchModel = await PluginSwitchModel.get_or_none(
            **{
                "name": pluginModel.name,
                "group_mark": group_mark
            })
        status = "绝赞运转中>>"
        if plugSwitchModel:
            if plugSwitchModel.switch is False:
                status = "关掉了呢，关掉了。"
        if pluginModel.switch is False:
            status = "啊……完全关掉了。"
    except Exception as e:
        logger.opt(exception=True).debug(f"{bot.self_id}执行指令时异常")
        await matcher.finish(f"{pluginModel.usage or '空空如也'}")

    await matcher.finish(f"{status}\n{pluginModel.admin_usage or '空空如也'}")


plug_help = on_command("插件帮助", aliases={"plughelp", "功能帮助"})


@plug_help.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: Bot,
            event: Event,
            arg: PlugArg = ArgMatchDepend(PlugArg)):
    pluginModel = await get_plugin(arg.plugin_name)
    try:
        adapter = AdapterFactory.get_adapter(bot)
        group_mark = await adapter.mark_group_without_drive(bot, event)
        plugSwitchModel = await PluginSwitchModel.get_or_none(
            **{
                "name": pluginModel.name,
                "group_mark": group_mark
            })
        status_msgs = ["绝赞运转中>>", "running...", "诸事顺利", "万事大吉"]
        status = status_msgs[random.randint(0, len(status_msgs) - 1)]
        if plugSwitchModel:
            if plugSwitchModel.switch is False:
                status = "关掉了呢，关掉了。"
            else:
                if not pluginModel.default_switch:
                    status = "no running..."
        if pluginModel.switch is False:
            status = "啊……完全关掉了。"
    except Exception as e:
        logger.opt(exception=True).debug(f"{bot.self_id}执行指令时异常")
        await matcher.finish(f"{pluginModel.usage or '空空如也'}")

    await matcher.finish(f"{status}\n{pluginModel.usage or '空空如也'}")

version = "v0.5beta"

help_msg = f"""
OSBot {version}
包含多引擎翻译、烤推、转推、转动态等功能~
维护者：晨轩(3309003591)
仓库：https://github.com/chenxuan353/OSBot

使用`功能列表 页码(可略)`及`功能帮助 插件名`来查看帮助信息
使用指令时使用空格分隔参数执行更准确哦。
遇到问题可以使用`反馈 内容`，会尽快处理。

>>非必要请勿禁言<<
""".strip()

help = on_command("帮助", aliases={
    "help",
}, rule=only_command())


@help.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    await matcher.finish(help_msg)


admin_help_msg = f"""
OSBot {version}

使用`超管功能帮助 插件名`来查看超级管理员专属帮助（大部分插件应该都没有）
可通过`全局禁用/启用插件 插件名`、`启用/禁用插件 插件名`、`默认启用/禁用插件 插件名`等命令进行插件管理
需要远程控制插件状态可以通过`插件管理 群/私聊 ID 插件名称 状态`来远程设置
通过`紧急通知列表`、`减少/增加紧急通知人`、`重载紧急通知列表`、`查看紧急通知列表`、`清空紧急通知列表`、`发送紧急通知(组)`对紧急通知进行管理
通过`封禁 Q号 时间`、`群封禁 群号 时间`、`解封 Q号`、`群解封 群号`、`封禁列表`、`系统封禁列表`等指令管理黑名单
通过`还得是你/优先响应`切换优先响应
其它命令 `运行数据统计`、`系统状态`
""".strip()

admin_help = on_command("管理员帮助",
                        aliases={"超管帮助", "超级管理员帮助", "adminhelp"},
                        priority=2,
                        rule=only_command(),
                        permission=SUPERUSER)


@admin_help.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    await matcher.finish(admin_help_msg)
