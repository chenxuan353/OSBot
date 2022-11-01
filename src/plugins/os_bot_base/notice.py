import asyncio
import json
import os
import random
from typing_extensions import Self
from nonebot import get_bots, on_command
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot import v11
from typing import Any, List, Union
from .config import config
from .logger import logger
from .cache.onebot import OnebotCache
from .exception import InfoCacheException
from .util import matcher_exception_try


class BotSend:
    """
        发送消息

        尽最大努力
    """

    @staticmethod
    async def ob_send_private_msg(uid: int, msg: Union["v11.Message",
                                                       str]) -> bool:
        """
            尽力发送一条私聊消息
        """
        uid = int(uid)
        bots = get_bots()
        for id in bots:
            bot = bots[id]
            if not isinstance(bot, v11.Bot):
                continue
            obcache = OnebotCache.get_instance()
            b_record = obcache.get_bot_record(int(bot.self_id))
            if not b_record:
                continue
            # 发送私聊消息
            u_record = b_record.get_friend_record(uid)
            if not u_record:
                continue
            try:
                await bot.send_private_msg(user_id=uid, message=msg)
                logger.debug(f"已通过`{bot.self_id}-{uid}`成功发送一条私聊通知")
                return True
            except Exception as e:
                logger.opt(exception=True).warning(
                    f"尝试通过`{bot.self_id}-{uid}`发送私聊通知时异常 - {e}")
                continue
        return False

    @staticmethod
    async def ob_send_group_msg(gid: int, msg: Union["v11.Message",
                                                     str]) -> bool:
        """
            尽力发送一条群聊消息
        """
        gid = int(gid)
        bots = get_bots()
        for id in bots:
            bot = bots[id]
            if not isinstance(bot, v11.Bot):
                continue
            obcache = OnebotCache.get_instance()
            b_record = obcache.get_bot_record(int(bot.self_id))
            if not b_record:
                continue
            # 发送私聊消息
            g_record = b_record.get_group_record(gid)
            if not g_record:
                continue
            try:
                await bot.send_group_msg(group_id=gid, message=msg)
                logger.debug(f"已通过`{bot.self_id}-{gid}`成功发送一条群聊通知")
                return True
            except Exception as e:
                logger.opt(exception=True).warning(
                    f"尝试通过`{bot.self_id}-{gid}`发送群聊通知时异常 - {e}")
                continue
        return False


class UrgentNotice:
    """
        紧急通知
        
        用于在程序错误时发送提醒

        - 实现了`Onebot`端的群聊与私聊推送
    """
    instance: Self

    def __init__(self) -> None:
        self.onebot_notify: List[int] = []
        self.onebot_group_notify: List[int] = []

        self.base_path = os.path.join(config.bb_data_path, "cache", "notice")
        self.file_base = os.path.join(self.base_path, "notice")

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance

    @classmethod
    async def send(cls, message: str, send_group: bool = False):
        """
            广播一条紧急通知

            `send_group` 是否发送给群聊（默认否）
        """
        ins = cls.get_instance()
        # 发送私聊消息
        for uid in ins.onebot_notify:
            success = await BotSend.ob_send_private_msg(uid, message)
            if not success:
                logger.warning(f"尝试给`{uid}`发送私聊通知失败，消息内容：{message}")
            await asyncio.sleep(1 + random.randint(20, 100) / 100)

        # 发送群聊消息
        if not send_group:
            return
        await cls.send_group(message)

    @classmethod
    async def send_group(cls, message: str):
        """
            广播一条群聊紧急通知
        """
        ins = cls.get_instance()
        for gid in ins.onebot_group_notify:
            success = await BotSend.ob_send_group_msg(gid, message)
            if not success:
                logger.warning(f"尝试给`{gid}`发送群聊通知失败，消息内容：{message}")
            await asyncio.sleep(1 + random.randint(20, 100) / 100)

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

    def load(self) -> None:
        self.onebot_notify = self.__read("onebot")
        self.onebot_group_notify = self.__read("onebot_group")


notify_reload = on_command("重载通知配置",
                           aliases={"reload_notify", "重新加载紧急通知配置", "重新加载通知配置"},
                           block=True,
                           permission=SUPERUSER)


@notify_reload.handle()
@matcher_exception_try()
async def _(matcher: Matcher):
    UrgentNotice.reload()
    await matcher.finish(
        f"已经完成了哦！在记录的数量"
        f"{len(UrgentNotice.get_instance().onebot_notify)}"
        f"+{len(UrgentNotice.get_instance().onebot_group_notify)}(组)")
