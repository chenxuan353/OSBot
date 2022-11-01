"""
    插件管理器

    半侵入式，管理插件分群开关，生成插件帮助。

    当插件存在复杂逻辑时，完整的开关需要配合本插件管理器的`API`使用。
"""
from functools import partial
import math
import textwrap
from typing import Dict, List
from nonebot.exception import IgnoredException
from nonebot.adapters import Bot, Event
from nonebot.message import run_preprocessor
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot.permission import SUPERUSER
from nonebot import get_driver, get_loaded_plugins, on_command
from .model.plugin_manage import PluginModel, PluginSwitchModel
from .util import matcher_exception_try, match_suggest, only_command
from .exception import MatcherErrorFinsh
from .adapter import AdapterFactory
from .argmatch import ArgMatch, Field, PageArgMatch
from .logger import logger
from .consts import STATE_ARGMATCH, META_NO_MANAGE, STATE_ARGMATCH_RESULT, META_ADMIN_USAGE, META_AUTHOR_KEY

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
        await PluginModel.filter().all().update(enable=False)
        for plugin in plugins:
            meta = plugin.metadata
            if meta and meta.extra.get(META_NO_MANAGE):
                continue
            if plugin.name == "nonebot_plugin_apscheduler":
                continue
            plugModel, _ = await PluginModel.get_or_create(name=plugin.name)
            plugModel.module_name = plugin.module_name
            plugModel.enable = True
            if meta:
                if meta.extra.get(META_AUTHOR_KEY) == "ChenXuan":
                    meta.usage = textwrap.dedent(meta.usage).strip()
                    if meta.extra.get(META_ADMIN_USAGE):
                        meta.extra[META_ADMIN_USAGE] = textwrap.dedent(meta.extra[META_ADMIN_USAGE]).strip()

                plugModel.display_name = meta.name
                plugModel.des = meta.description
                plugModel.usage = meta.usage
                plugModel.admin_usage = meta.extra.get(META_ADMIN_USAGE)
                plugModel.author = meta.extra.get(META_AUTHOR_KEY)
            if plugModel.display_name:
                cache_plugin_key_map[plugModel.display_name] = plugModel.name
                cache_plugin_keys.append(plugModel.display_name)
            cache_plugin_key_map[plugModel.name] = plugModel.name
            cache_plugin_keys.append(plugModel.name)
            await plugModel.save()
    except Exception as e:
        logger.opt(exception=True).debug(f"执行插件管理-插件开关启动初始化时异常")
        raise e


async def is_disable(name: str, group_mark: str) -> bool:
    """
        用于获取指定插件是否被禁用

        被禁用则返回`False`

        - `name` 插件标识名
        - `group_mark` 需要判断的组标识(一般通过`adapter.mark_group_without_drive(bot, event)`获取)
    """
    try:
        plugModel = await PluginModel.get_or_none(name=name)
        if not plugModel:
            return False
        if not plugModel.enable:
            return True
        plugSwitchModel = await PluginSwitchModel.get_or_none(
            **{
                "name": name,
                "group_mark": group_mark
            })
        if not plugSwitchModel:
            return False
        if plugModel and plugModel.enable is not None:
            if not plugModel.enable:
                return True

        if plugSwitchModel and plugSwitchModel.switch is not None:
            if not plugSwitchModel.switch:
                return True
            else:
                return False
        if plugModel and plugModel.switch is not None:
            if not plugModel.switch:
                return True
            else:
                return False
        return False
    except Exception as e:
        logger.opt(exception=True).debug(f"在检查{name} - {group_mark}是否被禁用时异常。")
        raise e


@run_preprocessor
async def __run_preprocessor(bot: Bot, event: Event, matcher: Matcher):
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
        plugModel = await PluginModel.get_or_none(name=plugin.name)
        if not plugModel:
            logger.debug(f"开关预处理 `{bot.self_id}` `{plugin.name}` 插件缺失主记录")
            return
        if not plugModel.enable:
            logger.warning(
                f"开关预处理 `{bot.self_id}` `{plugin.name}` 插件缺失已禁用，但仍然在处理消息。")
            raise IgnoredException(f"插件管理器已限制`{plugin.name}`(插件主记录)!")
        group_mark = await adapter.mark_group_without_drive(bot, event)
        plugSwitchModel = await PluginSwitchModel.get_or_none(
            **{
                "name": plugin.name,
                "group_mark": group_mark
            })
        if not plugSwitchModel:
            logger.debug(f"开关预处理 `{bot.self_id}` `{plugin.name}` 插件无开关记录")
            return
        if plugModel and plugModel.enable is not None:
            if not plugModel.enable:
                raise IgnoredException(f"插件管理器已禁用`{plugin.name}`(插件全局)!")

        if plugSwitchModel and plugSwitchModel.switch is not None:
            if not plugSwitchModel.switch:
                raise IgnoredException(
                    f"插件管理器已限制`{plugin.name}`(群组默认值)! group={group_mark}")
            else:
                return
        if plugModel and plugModel.switch is not None:
            if not plugModel.switch:
                raise IgnoredException(f"插件管理器已限制`{plugin.name}`(插件默认值)!")
            else:
                return
    except IgnoredException as e:
        logger.debug(e.reason)
        raise e
    except Exception as e:
        logger.opt(exception=True).debug(f"{bot.self_id} 执行插件开关预处理时异常")


class ManageArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "插件管理的参数"
        des = "管理插件的开关"

    group_type: str = Field.Keys(
        "组标识", {
            "group": ["g", "group", "组", "群", "群聊"],
            "private": ["p", "private", "私聊", "好友", "私"],
        })  # type: ignore
    group_id: int = Field.Int("组ID", min=9999, max=99999999999)
    plugin_name: str = Field.Keys("插件名称", cache_plugin_keys)
    switch: bool = Field.Bool("状态", require=False)
    def __init__(self) -> None:
        super().__init__(
            [self.group_type, self.group_id, self.plugin_name,
             self.switch])  # type: ignore


class PlugArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "插件名参数"
        des = "匹配插件名"

    plugin_name: str = Field.Keys(
        "插件名称", keys_generate=lambda: cache_plugin_key_map)

    def __init__(self) -> None:
        super().__init__([self.plugin_name])  # type: ignore


async def get_plugin_suggest(name: str) -> List[str]:
    return match_suggest(cache_plugin_keys, name)


async def get_plugin(name: str) -> PluginModel:
    pluginModel = await PluginModel.get_or_none(name=name, enable=True)
    if pluginModel is None:
        pluginModel = await PluginModel.get_or_none(display_name=name,
                                                    enable=True)
    if pluginModel is None:
        suggest = await get_plugin_suggest(name)
        if suggest:
            raise MatcherErrorFinsh(f"让我看看……{'、'.join(suggest[:5])}是这些吗，是吗是吗？")
        raise MatcherErrorFinsh("啊，连相似的都没找到！")
    return pluginModel


manage = on_command("插件管理",
                    aliases={
                        "管理插件",
                    },
                    permission=SUPERUSER,
                    state={STATE_ARGMATCH: ManageArg})


@manage.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: Event, state: T_State):
    arg: ManageArg = state.get(STATE_ARGMATCH_RESULT)  # type: ignore
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    if arg.group_type == "group":
        group_nick = await adapter.get_group_nick(arg.group_id)
    else:
        group_nick = await adapter.get_unit_nick(arg.group_id)
    mark = f"{await adapter.mark_drive(bot, event)}-{arg.group_type}-{arg.group_id}"
    entity = {"name": arg.plugin_name, "group_mark": mark}
    switchModel, _ = await PluginSwitchModel.get_or_create(**entity)
    if switchModel.switch == arg.switch:
        await matcher.finish(f"{group_nick}的{pluginModel.display_name}的状态没有变化哦"
                             )
    switchModel.switch = arg.switch
    await switchModel.save()
    if not switchModel.switch:
        await matcher.finish(f"已经关掉{group_nick}的{pluginModel.display_name}了~")
    else:
        await matcher.finish(f"{group_nick}的{pluginModel.display_name}开了！")


disable_plug = on_command("全局禁用插件",
                          aliases={"全局插件禁用", "全局关闭插件", ""},
                          permission=SUPERUSER,
                          state={STATE_ARGMATCH: PlugArg})


@disable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: Event, state: T_State):
    arg: PlugArg = state.get(STATE_ARGMATCH_RESULT)  # type: ignore
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    if pluginModel.switch == False:
        await matcher.finish(f"{pluginModel.display_name}关得不能再关啦")
    pluginModel.switch = False
    await pluginModel.save()
    await matcher.finish(f"{pluginModel.display_name}>完全禁止<")


enable_plug = on_command("全局启用插件",
                         aliases={"全局插件启用", "全局打开插件", ""},
                         permission=SUPERUSER,
                         state={STATE_ARGMATCH: PlugArg})


@enable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: Event, state: T_State):
    arg: PlugArg = state.get(STATE_ARGMATCH_RESULT)  # type: ignore
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    if pluginModel.switch == True:
        await matcher.finish(f"{pluginModel.display_name}")
    pluginModel.switch = True
    await pluginModel.save()
    await matcher.finish(f"{pluginModel.display_name}>完全禁止<")


disable_plug = on_command("禁用插件",
                          aliases={"插件禁用", "关闭插件", ""},
                          permission=SUPERUSER,
                          state={STATE_ARGMATCH: PlugArg})


@disable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: Event, state: T_State):
    arg: PlugArg = state.get(STATE_ARGMATCH_RESULT)  # type: ignore
    pluginModel = await get_plugin(arg.plugin_name)
    adapter = AdapterFactory.get_adapter(bot)
    mark = await adapter.mark_group(bot, event)
    entity = {"name": arg.plugin_name, "group_mark": mark}
    switchModel, _ = await PluginSwitchModel.get_or_create(**entity)
    if switchModel.switch == False:
        await matcher.finish(f"{pluginModel.display_name}不能再关了…")
    switchModel.switch = False
    await switchModel.save()
    await matcher.finish(f"已经关掉{pluginModel.display_name}咯！")


enable_plug = on_command("启用插件",
                         aliases={"插件启用", "打开插件", ""},
                         permission=SUPERUSER,
                         state={STATE_ARGMATCH: PlugArg})


@enable_plug.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: Event, state: T_State):
    arg: PlugArg = state.get(STATE_ARGMATCH_RESULT)  # type: ignore
    pluginModel = await get_plugin(arg.plugin_name)
    if pluginModel.switch == False:
        await matcher.finish(f"{pluginModel.display_name}在哪里都不能用哦。")
    adapter = AdapterFactory.get_adapter(bot)
    mark = await adapter.mark_group(bot, event)
    entity = {"name": arg.plugin_name, "group_mark": mark}
    switchModel, _ = await PluginSwitchModel.get_or_create(**entity)
    if switchModel.switch == True:
        await matcher.finish(f"{pluginModel.display_name}已经开了哦")
    switchModel.switch = True
    await switchModel.save()
    await matcher.finish(f"{pluginModel.display_name}>启动<")


plug_list = on_command("插件列表",
                       aliases={"pluglist", "功能列表"},
                       state={STATE_ARGMATCH: PageArgMatch})


@plug_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher, state: T_State):
    arg: PageArgMatch = state.get(STATE_ARGMATCH_RESULT)  # type: ignore
    size = 10
    count = await PluginModel.filter(enable=True).count()
    maxpage = math.ceil(count / size)

    if maxpage == 0:
        await matcher.finish(f"唔……什么也没有？")
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")

    plugs = await PluginModel.filter(enable=True).offset(
        (arg.page - 1) * size).limit(size)
    msg = f"{arg.page}/{maxpage}"
    for plug in plugs:
        status = "O"
        if plug.switch is True:
            status = "√"
        if plug.switch is False:
            status = "X"
        msg += f"\n{plug.display_name or plug.name}[{status}] - {plug.des or '没有描述'}"
    await matcher.finish(msg)


admin_help = on_command(
    "管理员插件帮助",
    aliases={"超管帮助", "超级管理员帮助", "超管功能", "超级管理员功能", "管理员功能帮助", "adminhelp"},
    permission=SUPERUSER,
    state={STATE_ARGMATCH: PlugArg})


@admin_help.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: Event, state: T_State):
    arg: PlugArg = state.get(STATE_ARGMATCH_RESULT)  # type: ignore
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


plug_help = on_command("插件帮助",
                       aliases={"plughelp", "功能帮助"},
                       state={STATE_ARGMATCH: PlugArg})


@plug_help.handle()
@matcher_exception_try()
async def _(matcher: Matcher, bot: Bot, event: Event, state: T_State):
    arg: PlugArg = state.get(STATE_ARGMATCH_RESULT)  # type: ignore
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

    await matcher.finish(f"{status}\n{pluginModel.usage or '空空如也'}")


help_msg = """
OSBot
大概能有点用吧（
维护者：晨轩(3309003591)

使用`功能列表 页码(可略)`及`功能帮助 插件名`来查看对应帮助
""".strip()

help = on_command("帮助", aliases={
    "help",
}, rule=only_command())


@help.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    await matcher.finish(help_msg)
