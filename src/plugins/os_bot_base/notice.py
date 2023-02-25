import asyncio
from collections import deque
from datetime import datetime
import json
import math
import os
import random
from typing_extensions import Self
from nonebot import get_bots, on_command, get_driver, on_notice
from nonebot.adapters import Bot, Event
from nonebot.params import CommandArg, EventMessage
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from typing import Any, Callable, Coroutine, Deque, Dict, List, Optional, Union
from .config import config
from .logger import logger
from .exception import InfoCacheException, MatcherErrorFinsh
from .cache import OnebotCache
from .util import matcher_exception_try, only_command
from .adapter import V11Adapter
from .depends import ArgMatchDepend
from .argmatch import ArgMatch, Field, PageArgMatch

driver = get_driver()


class BotSend:
    """
        发送消息

        尽最大努力
    """

    @staticmethod
    async def pkg_send_params(bot: Bot, event: Event) -> Dict[str, Any]:
        """
            封装发送参数（保证参数可以正常序列化）

            可以在推送通知时使用

            不支持的类型会报错 MatcherErrorFinsh("不支持的事件类型")
        """
        if isinstance(bot, v11.Bot):
            if isinstance(event, v11.GroupMessageEvent):
                return {"group_id": event.group_id}
            elif isinstance(event, v11.PrivateMessageEvent):
                return {"user_id": event.user_id}
            else:
                raise MatcherErrorFinsh("不支持的事件类型")
        else:
            raise MatcherErrorFinsh("不支持的驱动器")

    @classmethod
    async def send_msg(cls,
                       bot_type: str,
                       send_params: Dict[str, Any],
                       msg: Any,
                       priority_bot_id: Optional[str] = None) -> bool:
        """
            尽力发送消息，失败返回False

            bot_type 适配器type

            send_params 发送参数

            msg 待发送的数据

            priority_bot_id 优先使用的botid（优先使用什么bot发送，为空时依据优先响应配置）
        """
        if not msg:
            logger.debug("消息通知尝试发送空消息 {} - {}", bot_type, send_params)
            return True
        if bot_type == V11Adapter.get_type():
            if "user_id" in send_params:
                return await cls.ob_send_private_msg(send_params["user_id"],
                                                     msg, priority_bot_id)
            elif "group_id" in send_params:
                return await cls.ob_send_group_msg(send_params["group_id"],
                                                   msg, priority_bot_id)
            else:
                logger.warning("{} 消息通知不支持的参数 {}", bot_type, send_params)
                return False
        logger.warning("消息通知不支持的Bot类型 {} 参数 {}", bot_type, send_params)
        return False

    @staticmethod
    async def ob_send_private_msg(
            uid: int,
            msg: Union["v11.Message", str],
            priority_bot_id: Optional[str] = None) -> bool:
        """
            尽力发送一条私聊消息，失败返回False
        """
        uid = int(uid)
        bots = get_bots()

        async def send_use_bot(bot: Bot) -> Optional[bool]:
            if not isinstance(bot, v11.Bot):
                return
            obcache = OnebotCache.get_instance()
            b_record = obcache.get_bot_record(int(bot.self_id))
            if not b_record:
                return
            # 发送私聊消息
            u_record = b_record.get_friend_record(uid)
            if not u_record:
                return
            try:
                await bot.send_private_msg(user_id=uid, message=msg)
                logger.debug(f"已通过`{bot.self_id}-{uid}`成功发送一条私聊通知")
                return True
            except Exception as e:
                logger.opt(exception=True).warning(
                    f"尝试通过`{bot.self_id}-{uid}`发送私聊通知时异常 - {e}")
                return

        if priority_bot_id and priority_bot_id in bots:
            status = await send_use_bot(bots[priority_bot_id])
            if status is not None:
                return status
        for id in bots:
            status = await send_use_bot(bots[id])
            if status is not None:
                return status
        return False

    @staticmethod
    async def ob_send_group_msg(gid: int,
                                msg: Union["v11.Message", str],
                                priority_bot_id: Optional[str] = None) -> bool:
        """
            尽力发送一条群聊消息，失败返回False
        """
        gid = int(gid)
        bots = get_bots()

        async def send_use_bot(bot: Bot) -> Optional[bool]:
            if not isinstance(bot, v11.Bot):
                return
            obcache = OnebotCache.get_instance()
            b_record = obcache.get_bot_record(int(bot.self_id))
            if not b_record:
                return
            # 发送私聊消息
            g_record = b_record.get_group_record(gid)
            if not g_record:
                return
            try:
                await bot.send_group_msg(group_id=gid, message=msg)
                logger.debug(f"已通过`{bot.self_id}-{gid}`成功发送一条群聊通知")
                return True
            except Exception as e:
                logger.opt(exception=True).warning(
                    f"尝试通过`{bot.self_id}-{gid}`发送群聊通知时异常 - {e}")
                return

        if priority_bot_id and priority_bot_id in bots:
            status = await send_use_bot(bots[priority_bot_id])
            if status is not None:
                return status
        for id in bots:
            status = await send_use_bot(bots[id])
            if status is not None:
                return status
        return False


class UrgentNotice:
    """
        紧急通知
        
        用于在程序错误时发送提醒，或是存储一些可能需要的通知。

        - 实现了`Onebot`端的群聊与私聊推送
    """
    instance: Optional[Self] = None

    def __init__(self) -> None:
        self.onebot_notify: List[int] = []
        self.onebot_group_notify: List[int] = []
        self.some_notice_list: Deque[str] = deque(maxlen=512)  # 一些可能有用的数据

        self.base_path = os.path.join(config.os_data_path, "cache", "notice")
        self.file_base = os.path.join(self.base_path, "notice")

        if not os.path.isdir(self.base_path):
            try:
                os.makedirs(self.base_path)
            except IOError as e:
                raise InfoCacheException(f"目录 {self.base_path} 创建失败！", e)

        # 加载通知人
        self.load()

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance

    @classmethod
    async def send(cls,
                   message: str,
                   send_group: bool = False,
                   low_sleep=False,
                   fast_send=False):
        """
            广播一条紧急通知

            `send_group` 是否发送给群聊（默认否）
            `low_sleep` 低延迟，默认情况下随机1-10秒，低延迟时保持1秒
            `fast_send` 快速发送（无等待）
        """

        async def inner_send():
            if not message:
                logger.debug(f"尝试广播空消息！")
                return
            ins = cls.get_instance()
            # 发送私聊消息
            for uid in ins.onebot_notify:
                success = await BotSend.ob_send_private_msg(uid, message)
                if not success:
                    logger.warning(f"尝试给`{uid}`(动态)发送私聊通知失败，消息内容：{message}")
                await asyncio.sleep(1 if low_sleep else random.randint(1, 10) +
                                    random.randint(20, 100) / 100)

            for uid in config.os_ob_notice_user_list:
                success = await BotSend.ob_send_private_msg(uid, message)
                if not success:
                    logger.warning(f"尝试给`{uid}`(配置)发送私聊通知失败，消息内容：{message}")
                await asyncio.sleep(1 if low_sleep else random.randint(1, 10) +
                                    random.randint(20, 100) / 100)

            # 发送群聊消息
            if not send_group:
                return
            await cls.send_group(message)

        if fast_send:
            asyncio.gather(inner_send())
        else:
            await inner_send()

    @classmethod
    async def send_group(cls, message: str):
        """
            广播一条群聊紧急通知
        """
        ins = cls.get_instance()
        for gid in ins.onebot_group_notify:
            success = await BotSend.ob_send_group_msg(gid, message)
            if not success:
                logger.warning(f"尝试给`{gid}`(动态)发送群聊通知失败，消息内容：{message}")
            await asyncio.sleep(1 + random.randint(20, 100) / 100)

        for gid in config.os_ob_notice_group_list:
            success = await BotSend.ob_send_group_msg(gid, message)
            if not success:
                logger.warning(f"尝试给`{gid}`(配置)发送群聊通知失败，消息内容：{message}")
            await asyncio.sleep(1 + random.randint(20, 100) / 100)

    @classmethod
    def has_onebot_notify(cls, pid: int):
        pid = int(pid)
        ins = cls.get_instance()
        return pid in ins.onebot_notify

    @classmethod
    def has_onebot_notify_group(cls, gid: int):
        gid = int(gid)
        ins = cls.get_instance()
        return gid in ins.onebot_group_notify

    @classmethod
    def add_onebot_notify(cls, pid: int):
        pid = int(pid)
        ins = cls.get_instance()
        ins.onebot_notify.append(pid)
        ins.__save("onebot", ins.onebot_notify)

    @classmethod
    def add_onebot_group_notify(cls, gid: int):
        gid = int(gid)
        ins = cls.get_instance()
        ins.onebot_group_notify.append(gid)
        ins.__save("onebot_group", ins.onebot_group_notify)

    @classmethod
    def add_notice(cls, msg: str):
        """
            添加一个提醒，应当以简练为主，保持20字以内。
        """
        ins = cls.get_instance()
        ins.some_notice_list.append(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}> {msg}")
        ins.__save("notice_list", list(ins.some_notice_list))

    @classmethod
    def del_onebot_notify(cls, pid: int):
        pid = int(pid)
        ins = cls.get_instance()
        ins.onebot_notify.remove(pid)
        ins.__save("onebot", ins.onebot_notify)

    @classmethod
    def del_onebot_group_notify(cls, gid: int):
        gid = int(gid)
        ins = cls.get_instance()
        ins.onebot_group_notify.remove(gid)
        ins.__save("onebot_group", ins.onebot_group_notify)

    @classmethod
    def clear(cls):
        ins = cls.get_instance()
        ins.onebot_group_notify = []
        ins.onebot_notify = []
        ins.save()

    @classmethod
    def clear_notice(cls):
        ins = cls.get_instance()
        ins.some_notice_list = deque(maxlen=512)
        ins.__save("notice_list", list(ins.some_notice_list))

    @classmethod
    def empty(cls) -> bool:
        ins = cls.get_instance()
        return not ins.onebot_group_notify and not ins.onebot_notify

    @classmethod
    def reload(cls):
        ins = cls.get_instance()
        ins.load()

    def backup_file(self, key: str):
        if not os.path.isfile(f"{self.file_base}_{key}.json"):
            return
        i = 0
        while os.path.exists(f"{self.file_base}_{key}.{i}.bak"):
            i += 1

        try:
            os.rename(f"{self.file_base}_{key}.json",
                      f"{self.file_base}_{key}.{i}.bak")
        except Exception as e:
            raise InfoCacheException(
                f"文件`{self.file_base}_{key}.json`备份失败，可能导致数据异常或丢失！", cause=e)

    def __save(self, key: str, value: List[Any]) -> None:
        file_path = f"{self.file_base}_{key}.json"
        try:
            json_str = json.dumps(value,
                                  ensure_ascii=False,
                                  sort_keys=True,
                                  indent=2)
        except Exception as e:
            raise InfoCacheException("JSON 序列化异常", cause=e)
        try:
            with open(file_path, mode='w', encoding="utf-8") as fw:
                fw.write(json_str)
        except Exception as e:
            raise InfoCacheException(f"数据文件`{file_path}`写入异常", cause=e)

    def __read(self, key: str) -> List[Any]:
        file_path = f"{self.file_base}_{key}.json"
        if not os.path.isfile(file_path):
            return []
        try:
            with open(file_path, mode='r', encoding="utf-8") as fr:
                json_str = fr.read()
                data = json.loads(json_str)
                return list(data)
        except Exception as e:
            now_e = e
            try:
                self.backup_file(key)
            except Exception as e:
                now_e = e
            raise InfoCacheException(f"数据文件`{file_path}`读取异常。", cause=now_e)

    def save(self) -> None:
        self.__save("onebot", self.onebot_notify)
        self.__save("onebot_group", self.onebot_group_notify)
        self.__save("notice_list", list(self.some_notice_list))

    def load(self) -> None:
        self.onebot_notify = self.__read("onebot")
        self.onebot_group_notify = self.__read("onebot_group")
        self.some_notice_list = deque(self.__read("notice_list"), maxlen=512)


class LeaveGroupHook:
    """
        退出群聊钩子
        
        需要处理的退群相关任务的可以利用此类添加钩子函数进行处理
        
        注意，此类任务也被将用于主动指定的失效群聊清理。

        钩子函数示例

        ```python
            async def _(group_id: int, bot_id: int) -> None:
                ...
        ```
    """
    instance: Optional[Self] = None

    def __init__(self) -> None:
        self.hooks: List[Callable[[int, int], Coroutine[Any, Any, None]]] = []

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance

    def add_hook(self, func: Callable[[int, int], Coroutine[Any, Any, None]]):
        self.hooks.append(func)

    async def run_hooks(self, group_id: int, bot_id: int, wait: bool = True):
        coros: List[Coroutine[Any, Any, None]] = []

        for hook in self.hooks:
            coros.append(hook(group_id, bot_id))

        if wait:
            await asyncio.gather(*coros)
        else:
            asyncio.gather(*coros)


driver_shutdown = False


@driver.on_shutdown
async def _():
    global driver_shutdown
    driver_shutdown = True


@driver.on_bot_disconnect
async def _(bot: v11.Bot):
    # bot断开提醒
    if config.os_ob_notice_disconnect:
        nick = OnebotCache.get_instance().get_unit_nick(int(bot.self_id))
        name = f"{nick}({bot.self_id})"

        async def await_send():
            await asyncio.sleep(10)
            if driver_shutdown:
                return
            bots = get_bots()
            if bot.self_id not in bots:
                finish_msgs = [
                    f"{name}断开连接！", f"{name}失去了连接", f"嗯……{name}好像出了一些问题？"
                ]
                msg = finish_msgs[random.randint(0, len(finish_msgs) - 1)]
                await UrgentNotice.send(msg)
                UrgentNotice.add_notice(msg)

        asyncio.gather(await_send())


leave_group = on_notice()


@leave_group.handle()
async def _(matcher: Matcher, bot: v11.Bot,
            event: v11.GroupDecreaseNoticeEvent):
    if event.sub_type not in ["kick_me", "leave"
                              ] or event.operator_id != event.user_id:
        return
    cache = OnebotCache.get_instance()
    if event.sub_type == "kick_me":
        msg = (
            f"{cache.get_unit_nick(int(bot.self_id))}({bot.self_id}) 已被移出群聊 "
            f"{cache.get_group_nick(event.group_id)}({event.group_id})")
        await UrgentNotice.send(msg)
        UrgentNotice.add_notice(msg)
        # 被移出群聊时执行
        await LeaveGroupHook.get_instance().run_hooks(event.group_id,
                                                      event.user_id,
                                                      wait=False)
    elif event.sub_type == "leave":
        msg = (f"{cache.get_unit_nick(int(bot.self_id))}({bot.self_id}) 退出群聊 "
               f"{cache.get_group_nick(event.group_id)}({event.group_id})")
        await UrgentNotice.send(msg)
        UrgentNotice.add_notice(msg)


class ManageArg(ArgMatch):

    class Meta(ArgMatch.Meta):
        name = "退出hook的参数"
        des = "触发退出hook的参数"

    unit_id: int = Field.Int("ID", min=9999, max=99999999999)

    def __init__(self) -> None:
        super().__init__([self.unit_id])


group_leave_clear = on_command("触发退群操作", block=True, permission=SUPERUSER)


@group_leave_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            arg: ManageArg = ArgMatchDepend(ManageArg)):
    await LeaveGroupHook.get_instance().run_hooks(arg.unit_id,
                                                    int(bot.self_id))
    await matcher.finish(f"已触发{arg.unit_id}的退群操作")


notice_view = on_command("通知列表", block=True, permission=SUPERUSER)


@notice_view.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            arg: PageArgMatch = ArgMatchDepend(PageArgMatch)):
    some_notice_list = list(UrgentNotice.get_instance().some_notice_list)
    some_notice_list.reverse()
    size = 5
    count = len(some_notice_list)
    maxpage = math.ceil(count / size)
    if count == 0:
        finish_msgs = ["暂无通知~", "没有通知哦"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    if arg.page > maxpage:
        await matcher.finish(f"超过最大页数({maxpage})了哦")
    notice_list_page = some_notice_list[(arg.page - 1) * size:arg.page * size]
    msg = f"{arg.page}/{maxpage}"
    for notice in notice_list_page:
        msg += f"\n{notice}"
    await matcher.finish(msg)


notice_clear = on_command("清空通知",
                          block=True,
                          rule=only_command(),
                          permission=SUPERUSER)


@notice_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    if UrgentNotice.empty():
        await matcher.finish("通知列表就是空的哟")
    finish_msgs = ["请发送`确认清空`确认~", "通过`确认清空`继续操作哦"]
    await matcher.pause(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


@notice_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher, message: v11.Message = EventMessage()):
    msg = str(message).strip()
    if msg == "确认清空":
        UrgentNotice.clear_notice()
        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["pass！", "要发送确认清空哦"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


notify_clear = on_command("清空紧急通知列表",
                          block=True,
                          rule=only_command(),
                          permission=SUPERUSER)


@notify_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    if UrgentNotice.empty():
        await matcher.finish("紧急通知列表就是空的哟")
    finish_msgs = ["请发送`确认清空`确认~", "通过`确认清空`继续操作哦"]
    await matcher.pause(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


@notify_clear.handle()
@matcher_exception_try()
async def _(matcher: Matcher, message: v11.Message = EventMessage()):
    msg = str(message).strip()
    if msg == "确认清空":
        UrgentNotice.clear()
        finish_msgs = ["已清空！", ">>操作已执行<<"]
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    finish_msgs = ["确认……失败。", "无法确认"]
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


notify_reload = on_command("重载通知配置",
                           aliases={"reload_notify", "重新加载紧急通知配置", "重新加载通知配置"},
                           block=True,
                           rule=only_command(),
                           permission=SUPERUSER)


@notify_reload.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    UrgentNotice.reload()
    await matcher.finish(
        f"已经完成了哦！在记录的数量"
        f"{len(UrgentNotice.get_instance().onebot_notify)}"
        f"+{len(UrgentNotice.get_instance().onebot_group_notify)}(组)")


notify_add = on_command(
    "增加紧急通知人",
    aliases={"增加紧急通知", "添加紧急通知", "加入紧急通知", "添加紧急通知人", "加入紧急通知人"},
    block=True,
    permission=SUPERUSER,
)


@notify_add.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            message: v11.Message = CommandArg()):
    pid = message.extract_plain_text().strip()
    if pid:
        try:
            pid = int(pid)
        except Exception:
            await matcher.finish("Q号看起来有问题……？")
    else:
        pid = event.user_id
    if UrgentNotice.has_onebot_notify(pid):
        await matcher.finish("已经在列表中了哦！")
    notice = UrgentNotice.get_instance()
    cache = OnebotCache.get_instance()
    notice.add_onebot_notify(pid)
    await matcher.finish(f"{cache.get_unit_nick(pid)}加入列表")


notify_add_group = on_command(
    "增加紧急通知组",
    aliases={"添加紧急通知组", "加入紧急通知组", "添加紧急通知群", "加入紧急通知群", "增加紧急通知群"},
    block=True,
    permission=SUPERUSER,
)


@notify_add_group.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            message: v11.Message = CommandArg()):
    gid = message.extract_plain_text().strip()
    if gid:
        try:
            gid = int(gid)
        except Exception:
            await matcher.finish("群号看起来有问题……？")
    else:
        await matcher.finish("群号不能为空哦！")
    if UrgentNotice.has_onebot_notify_group(gid):
        await matcher.finish("已经在组列表中了哦！")
    notice = UrgentNotice.get_instance()
    cache = OnebotCache.get_instance()
    notice.add_onebot_group_notify(gid)
    await matcher.finish(f"{cache.get_group_nick(gid)}加入列表")


notify_del = on_command(
    "减少紧急通知",
    aliases={"移除紧急通知人", "移出紧急通知人", "移除紧急通知", "移出紧急通知"},
    block=True,
    permission=SUPERUSER,
)


@notify_del.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            message: v11.Message = CommandArg()):
    pid = message.extract_plain_text().strip()
    if pid:
        try:
            pid = int(pid)
        except Exception:
            await matcher.finish("Q号看起来有问题……？")
    else:
        pid = event.user_id
    if not UrgentNotice.has_onebot_notify(pid):
        await matcher.finish("不在列表中哦！")
    notice = UrgentNotice.get_instance()
    cache = OnebotCache.get_instance()
    notice.del_onebot_notify(pid)
    await matcher.finish(f"{cache.get_unit_nick(pid)}加入列表")


notify_del_group = on_command(
    "减少紧急通知组",
    aliases={"移除紧急通知组", "移出紧急通知组", "移除紧急通知群", "移出紧急通知群", "减少紧急通知群"},
    block=True,
    permission=SUPERUSER,
)


@notify_del_group.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            message: v11.Message = CommandArg()):
    gid = message.extract_plain_text().strip()
    if gid:
        try:
            gid = int(gid)
        except Exception:
            await matcher.finish("群号看起来有问题……？")
    else:
        await matcher.finish("群号不能为空哦！")
    if not UrgentNotice.has_onebot_notify_group(gid):
        await matcher.finish("不在组列表中哦！")
    notice = UrgentNotice.get_instance()
    cache = OnebotCache.get_instance()
    notice.del_onebot_group_notify(gid)
    await matcher.finish(f"{cache.get_group_nick(gid)}加入列表")


notify_list = on_command("紧急通知列表",
                         aliases={"查看紧急通知列表", "打开紧急通知列表"},
                         block=True,
                         permission=SUPERUSER,
                         rule=only_command())


@notify_list.handle()
@matcher_exception_try()
async def _(matcher: Matcher, event: v11.PrivateMessageEvent):
    notice = UrgentNotice.get_instance()
    cache = OnebotCache.get_instance()
    if UrgentNotice.empty():
        await matcher.finish("通知列表是空的！")
    msg = f"通知人：{'、'.join({cache.get_unit_nick(uid) for uid in notice.onebot_notify})}"
    msg += f"\n通知组：{'、'.join({cache.get_group_nick(gid) for gid in notice.onebot_group_notify})}"
    await matcher.finish(msg)


notify_send = on_command("发送紧急通知", block=True, permission=SUPERUSER)


@notify_send.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            message: v11.Message = CommandArg()):
    await UrgentNotice.send(str(message))
    await matcher.finish("投递成功~")


notify_send_group = on_command("发送紧急通知组", block=True, permission=SUPERUSER)


@notify_send_group.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            event: v11.PrivateMessageEvent,
            message: v11.Message = CommandArg()):
    await UrgentNotice.send_group(str(message))
    await matcher.finish("投递成功~")
