"""
    ## `onebot`缓存

    缓存必要数据
"""
import asyncio
import json
import os
import random
from time import time
from dataclasses import dataclass, field
from nonebot import get_driver, on_metaevent, require, on_message
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.message import event_preprocessor
from typing import Any, Dict, Optional, Set, Type, TypeVar
from typing_extensions import Self
from ..config import config
from ..logger import logger
from ..session import StoreSerializable, StoreEncoder
from ..exception import InfoCacheException

from nonebot_plugin_apscheduler import scheduler

driver = get_driver()


def _now_int() -> int:
    return int(time())


@dataclass(repr=False)
class BaseRecord(StoreSerializable):
    update_time: int = field(default_factory=_now_int, init=False)
    create_time: int = field(default_factory=_now_int, init=False)

    def merge_from_dict(self, merge_dict: Dict[str, Any]):
        for key in self.__dict__:
            if key in merge_dict:
                self.__dict__[key] = merge_dict[key]

    def _serializable(self) -> Dict[str, Any]:
        """
            序列化对象，该方法在保存时自动调用（通过JSONEncode）
            
            忽略以`_`或`tmp_`起始的属性。
            
            不以下划线开始且值为基础类型或实现了StoreSerializable的字段
        """
        rtn = {}

        for key in self.__dict__:
            if key.startswith("_") or key.startswith("tmp_"):
                continue
            val = self.__dict__[key]
            if not (val is None or isinstance(val, StoreSerializable)
                    or isinstance(val, int) or isinstance(val, str)
                    or isinstance(val, dict) or isinstance(val, float)
                    or isinstance(val, list) or isinstance(val, tuple)
                    or isinstance(val, bool)):
                # 如果不是基本类型或者实现了StoreSerializable则会被忽略
                continue
            if isinstance(val, StoreSerializable):
                val = val._serializable()
            rtn[key] = val
        return rtn

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        """
            初始化实例，该方法在加载时自动调用。

            如若需要自定义加载，请覆盖此方法。
        """
        self.__dict__.update(self_dict)
        return self

    @classmethod
    def _load_from_dict(cls, self_dict: Dict[str, Any]) -> Self:
        if "id" in self_dict:
            return cls(self_dict["id"])._init_from_dict(  # type: ignore
                self_dict)
        return cls()._init_from_dict(self_dict)


@dataclass
class UnitRecord(BaseRecord):
    """
        单账号记录
    """
    id: int
    name: Optional[str] = field(default=None, init=False)
    remark: Optional[str] = field(default=None, init=False)
    sex: Optional[str] = field(default=None, init=False)
    age: Optional[str] = field(default=None, init=False)

    def get_nick(self) -> str:
        if self.remark and self.remark.strip() != f"{self.id}":
            return self.remark
        return self.name or f"{self.id}"


@dataclass
class GroupInfoCard(UnitRecord):
    """
        群成员信息

        - group_id	int64	群号
        - user_id	int64	QQ 号
        - nickname	string	昵称
        - card	string	群名片／备注
        - sex	string	性别, male 或 female 或 unknown
        - age	int32	年龄
        - area	string	地区
        - join_time	int32	加群时间戳
        - last_sent_time	int32	最后发言时间戳
        - level	string	成员等级
        - role	string	角色, owner 或 admin 或 member
        - unfriendly	boolean	是否不良记录成员
        - title	string	专属头衔
        - title_expire_time	int64	专属头衔过期时间戳
        - card_changeable	boolean	是否允许修改群名片
        - shut_up_timestamp	int64	禁言到期时间
    """
    card: Optional[str] = field(default=None, init=False)

    title: Optional[str] = field(default=None, init=False)
    level: Optional[str] = field(default=None, init=False)
    role: Optional[str] = field(default=None, init=False)
    area: Optional[str] = field(default=None, init=False)

    join_time: Optional[int] = field(default=None, init=False)
    last_sent_time: Optional[int] = field(default=None, init=False)
    unfriendly: Optional[bool] = field(default=None, init=False)
    card_changeable: Optional[bool] = field(default=None, init=False)
    shut_up_timestamp: Optional[int] = field(default=None, init=False)
    title_expire_time: Optional[int] = field(default=None, init=False)

    def get_nick(self) -> str:
        return self.card or self.name or f"{self.id}"


@dataclass
class GroupRecord(BaseRecord):
    """
        群记录
    """
    id: int
    name: Optional[str] = field(default=None, init=False)
    remark: Optional[str] = field(default=None, init=False)

    member_count: Optional[int] = field(default=0, init=False)
    max_member_count: Optional[int] = field(default=0, init=False)

    group_create_time: Optional[int] = field(default=0, init=False)  # gocqhttp
    group_level: Optional[int] = field(default=0, init=False)  # gocqhttp

    users: Dict[int, GroupInfoCard] = field(default_factory=dict, init=False)

    def get_nick(self) -> str:
        return self.remark or self.name or f"{self.id}"

    def get_user_record(self, id: int) -> Optional[GroupInfoCard]:
        if id not in self.users:
            return None
        return self.users[id]

    def _get_or_create_user_record(self, id: int) -> GroupInfoCard:
        if id not in self.users:
            self.users[id] = GroupInfoCard(id)
        return self.users[id]

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        """
            初始化实例，该方法在加载时自动调用。

            如若需要自定义加载，请覆盖此方法。
        """
        self.users = {}

        self.__dict__.update(self_dict)
        for key in self.users:
            record: Dict[str, Any] = self.users[key]  # type: ignore
            self.users[key] = GroupInfoCard._load_from_dict(record)
        return self


@dataclass
class BotGroupStatusRecord(BaseRecord):
    """
        对应Bot的群状态记录
    """
    id: int
    shut_up_timestamp: Optional[int] = field(default=None, init=False)


@dataclass
class BotRecord(BaseRecord):
    """
        对应Bot的状态记录
    """
    id: int
    name: Optional[str] = field(default=None, init=False)
    des: Optional[str] = field(default="", init=False)

    groups: Dict[int, GroupRecord] = field(default_factory=dict, init=False)
    friends: Dict[int, UnitRecord] = field(default_factory=dict, init=False)

    receive_event_count: int = field(default=0, init=False)
    receive_message_count: int = field(default=0, init=False)
    call_send_msg_count: int = field(default=0, init=False)
    call_api_count: int = field(default=0, init=False)
    call_api_error_count: int = field(default=0, init=False)
    disconnect_count: int = field(default=0, init=False)

    last_activity: int = field(default=0, init=False)
    last_call_api_time: int = field(default=0, init=False)
    last_disconnect_time: int = field(default=0, init=False)
    last_connect_time: int = field(default=0, init=False)

    def get_nick(self) -> str:
        return self.name or f"{self.id}"

    def clear_count(self) -> None:
        """
            移除所有计数
        """
        self.receive_event_count = 0
        self.receive_message_count = 0
        self.call_api_count = 0
        self.call_api_error_count = 0
        self.call_send_msg_count = 0
        self.disconnect_count = 0

    def clear_api_count(self) -> None:
        """
            移除`Api`计数(call_api_count、call_api_error_count、call_send_msg_count)
        """
        self.call_api_count = 0
        self.call_api_error_count = 0
        self.call_send_msg_count = 0

    def clear_disconnect_count(self) -> None:
        """
            移除`connect`计数(call_api_count、call_api_error_count、call_send_msg_count)
        """
        self.disconnect_count = 0

    def get_or_create_group_record(self, id: int) -> GroupRecord:
        if id not in self.groups:
            self.groups[id] = GroupRecord(id)
        return self.groups[id]

    def get_or_create_friend_record(self, id: int) -> UnitRecord:
        if id not in self.friends:
            self.friends[id] = UnitRecord(id)
        return self.friends[id]

    def get_group_record(self, id: int) -> Optional[GroupRecord]:
        if id not in self.groups:
            return None
        return self.groups[id]

    def get_friend_record(self, id: int) -> Optional[UnitRecord]:
        if id not in self.friends:
            return None
        return self.friends[id]

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        """
            初始化实例，该方法在加载时自动调用。

            如若需要自定义加载，请覆盖此方法。
        """
        self.__dict__.update(self_dict)
        # for key in self.groups:
        #     record: Dict[str, Any] = self.groups[key]  # type: ignore
        #     self.groups[key] = GroupRecord._load_from_dict(record)
        # for key in self.friends:
        #     record: Dict[str, Any] = self.friends[key]  # type: ignore
        #     self.friends[key] = UnitRecord._load_from_dict(record)
        self.groups = {}
        self.friends = {}

        return self


T_Record = TypeVar("T_Record", BotRecord, UnitRecord, GroupRecord, BaseRecord)


class OnebotCache:
    """
        `Onebot` 全局缓存

        适用于对实时性要求不高但需要显示或判定的情况，会通过API及消息钩子尽可能保持最新

        默认情况下基础数据会以设定的时间定时更新

        - 指定`Bot`好友列表 20分钟，执行相关请求后立即更新
        - 指定`Bot`群列表 20分钟，执行相关请求后立即更新
        - 指定`Bot`状态数据(登录号信息、运行状态、版本、状态) 60分钟，部分信息仅获取一次
        - 全局陌生人信息缓存（仅通过`API`与`Event`钩子更新）
        - 全局群数据缓存（仅通过`API`与`Event`钩子更新）

        > 所有的数据节点均包含获取时间戳记录（仍无法保证最新），且可能因延迟导致快速变更。
    """

    instance: Optional[Self] = None

    def __init__(self) -> None:
        self.cache_units: Dict[int, UnitRecord] = {}
        self.cache_groups: Dict[int, GroupRecord] = {}
        self.cache_bots: Dict[int, BotRecord] = {}

        self.base_path = os.path.join(config.os_data_path, "cache", "info")
        self.file_base = os.path.join(self.base_path, "onebot")

        if not os.path.isdir(self.base_path):
            try:
                os.makedirs(self.base_path)
            except IOError as e:
                raise InfoCacheException(f"目录`{self.base_path}`创建失败！", e)

        # 加载缓存
        self.load()

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance

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

    def __save(self, key: str, value: Any) -> None:
        file_path = f"{self.file_base}_{key}.json"
        try:
            json_str = json.dumps(value,
                                  ensure_ascii=False,
                                  sort_keys=True,
                                  indent=2,
                                  cls=StoreEncoder)
        except Exception as e:
            raise InfoCacheException("JSON 序列化异常", cause=e)
        try:
            with open(file_path, mode='w', encoding="utf-8") as fw:
                fw.write(json_str)
        except Exception as e:
            logger.opt(exception=True).error(f"数据文件`{file_path}`写入异常。信息：{e}")

    def __read(self, key: str, Cls: Type[T_Record]) -> Dict[int, T_Record]:
        file_path = f"{self.file_base}_{key}.json"
        if not os.path.isfile(file_path):
            return {}
        try:
            with open(file_path, mode='r', encoding="utf-8") as fr:
                json_str = fr.read()
                data = json.loads(json_str)
                result: Dict[int, T_Record] = {}
                for index in data:
                    result[int(index)] = Cls._load_from_dict(data[index])
                return result
        except Exception as e:
            now_e = e
            try:
                self.backup_file(key)
            except Exception as e:
                now_e = e
            logger.opt(
                exception=True).error(f"数据文件`{file_path}`读取异常。信息：{now_e}")
            return {}

    def save(self) -> None:
        self.__save("bots", self.cache_bots)
        self.__save("groups", self.cache_groups)
        self.__save("units", self.cache_units)

    def load(self) -> None:
        self.cache_bots = self.__read("bots", BotRecord)
        self.cache_groups = self.__read("groups", GroupRecord)
        self.cache_units = self.__read("units", UnitRecord)

    def get_or_create_bot_record(self, bot: Bot) -> BotRecord:
        self_id: int = int(bot.self_id)
        if self_id not in self.cache_bots:
            self.cache_bots[self_id] = BotRecord(self_id)
        return self.cache_bots[self_id]

    def get_or_create_group_record(self, id: int) -> GroupRecord:
        if id not in self.cache_groups:
            self.cache_groups[id] = GroupRecord(id)
        return self.cache_groups[id]

    def get_or_create_unit_record(self, id: int) -> UnitRecord:
        if id not in self.cache_units:
            self.cache_units[id] = UnitRecord(id)
        return self.cache_units[id]

    def get_bot_record(self, id: int) -> Optional[BotRecord]:
        if id not in self.cache_bots:
            return None
        return self.cache_bots[id]

    def get_group_record(self, id: int) -> Optional[GroupRecord]:
        if id not in self.cache_groups:
            return None
        return self.cache_groups[id]

    def get_unit_record(self, id: int) -> Optional[UnitRecord]:
        if id not in self.cache_units:
            return None
        return self.cache_units[id]

    def get_group_nick(self, id: int) -> str:
        if id not in self.cache_groups:
            return f"{id}"
        return self.cache_groups[id].get_nick()

    def get_unit_nick(self, id: int, group_id: Optional[int] = None) -> str:
        if group_id:
            group_record = self.get_group_record(group_id)
            if group_record:
                record = group_record.get_user_record(id)
                if record:
                    nick = record.get_nick()
                    if nick != f"{id}":
                        return nick
        if id not in self.cache_units:
            return f"{id}"
        return self.cache_units[id].get_nick()


def __merge_unit_info_to_global(unit: UnitRecord):
    """
        合并单元信息至全局
    """
    record = OnebotCache.get_instance().get_unit_record(unit.id)
    if record and record.update_time > unit.update_time:
        return
    if not record:
        record = OnebotCache.get_instance().get_or_create_unit_record(unit.id)
    record.update_time = _now_int()
    if unit.name and unit.name != f"{unit.id}":
        record.name = unit.name
    if unit.sex:
        record.sex = unit.sex
    if unit.age:
        record.age = unit.age
    # if unit.remark and unit.remark != f"{unit.id}":
    #     record.remark = unit.remark


def __merge_group_info_to_global(group: GroupRecord):
    """
        合并组信息至全局缓存
    """
    record = OnebotCache.get_instance().get_group_record(group.id)
    if record and record.update_time > group.update_time:
        return
    if not record:
        record = OnebotCache.get_instance().get_or_create_group_record(
            group.id)
    record.update_time = _now_int()
    if group.name and group.name != f"{group.id}":
        record.name = group.name
    if group.member_count:
        record.member_count = group.member_count
    if group.max_member_count:
        record.max_member_count = group.max_member_count
    if group.group_create_time:
        record.group_create_time = group.group_create_time
    if group.group_level:
        record.group_level = group.group_level

    if group.users:
        record.users = group.users
        for id in record.users:
            __merge_unit_info_to_global(record.users[id])


def _conversion_to_card_info(user_card: GroupInfoCard, data: Dict[str, Any]):
    """
        合并字典的值到群成员数据中（包含时间戳更新）
    """
    if not data:
        return
    if not isinstance(data, dict):
        data = dict(data)
    if "nickname" in data:
        user_card.name = data["nickname"]
    if "card" in data:
        user_card.card = data["card"]
    if "sex" in data:
        user_card.sex = data["sex"]
    if "age" in data:
        user_card.age = data["age"]
    if "area" in data:
        user_card.area = data["area"]
    if "join_time" in data:
        user_card.join_time = data["join_time"]
    if "last_sent_time" in data:
        user_card.last_sent_time = data["last_sent_time"]
    if "level" in data:
        user_card.level = data["level"]
    if "role" in data:
        user_card.role = data["role"]
    if "unfriendly" in data:
        user_card.unfriendly = data["unfriendly"]
    if "title" in data:
        user_card.title = data["title"]
    if "title_expire_time" in data:
        user_card.title_expire_time = data["title_expire_time"]
    if "card_changeable" in data:
        user_card.card_changeable = data["card_changeable"]
    user_card.update_time = _now_int()


@driver.on_bot_connect
async def _(bot: Bot):
    if not isinstance(bot, Bot):
        return
    bot_record = OnebotCache.get_instance().get_or_create_bot_record(bot)

    bot_record.last_activity = _now_int()
    bot_record.last_connect_time = _now_int()
    try:
        result = await bot.get_version_info()
        if "app_name" in result and "app_version" in result:
            bot_record.des = f'{result["app_name"]}{result["app_version"]}'

        protocol_map = {
            -1: "unknown",
            1: "Android Phone",
            2: "Android Watch",
            3: "MacOS",
            4: "企点",
            5: "iPad",
        }
        if "protocol" in result:
            if result["protocol"] in protocol_map:
                bot_record.des = f'{bot_record.des} - {protocol_map[result["protocol"]]}'
        bot_record.update_time = _now_int()
    except Exception as e:
        logger.opt(exception=True).debug(f"获取OB11-{bot.self_id}版本信息时异常")

    logger.info(
        f"Bot接入 {bot_record.get_nick()}({bot_record.id}) | {bot_record.des}")

    try:
        await bot.get_login_info()
    except Exception as e:
        logger.opt(exception=True).debug(f"获取OB11-{bot.self_id}登录号信息时异常")
    try:
        await bot.get_group_list()
    except Exception as e:
        logger.opt(exception=True).debug(f"获取OB11-{bot.self_id}群列表信息时异常")
    try:
        await bot.get_friend_list()
    except Exception as e:
        logger.opt(exception=True).debug(f"获取OB11-{bot.self_id}好友列表信息时异常")


@driver.on_bot_disconnect
async def _(bot: Bot):
    if not isinstance(bot, Bot):
        return
    bot_record = OnebotCache.get_instance().get_bot_record(int(bot.self_id))
    if bot_record:
        bot_record.last_activity = _now_int()
        bot_record.last_disconnect_time = _now_int()
        bot_record.disconnect_count += 1
        bot_record.friends = {}
        bot_record.groups = {}
        logger.info(
            f"Bot断开连接 {bot_record.get_nick()}({bot_record.id}) | {bot_record.des}"
        )
    else:
        logger.info(f"Bot断开连接 {bot.self_id} - 未处于缓存中")


@event_preprocessor
async def _(bot: Bot):
    """
        这个钩子函数会在 Event 上报到 NoneBot2 时运行
    """
    if not isinstance(bot, Bot):
        return
    bot_record = OnebotCache.get_instance().get_bot_record(int(bot.self_id))
    if bot_record:
        bot_record.last_activity = _now_int()
        bot_record.receive_event_count += 1


meta_matcher = on_metaevent(priority=1, block=False)


@meta_matcher.handle()
async def _(bot: Bot):
    if not isinstance(bot, Bot):
        return
    bot_record = OnebotCache.get_instance().get_bot_record(int(bot.self_id))
    if not bot_record:
        logger.debug(f"元事件来自未处于缓存中的来源 - {bot.self_id}")


@event_preprocessor
async def _(bot: Bot, event: GroupMessageEvent):
    if event.sub_type != "normal":
        logger.debug(
            f"不支持缓存的群消息 {bot.self_id}-{event.sub_type}-{event.user_id}:{event.message_id}"
        )
        return
    bot_record = OnebotCache.get_instance().get_bot_record(int(bot.self_id))
    if not bot_record:
        logger.debug(f"群消息事件来自未处于缓存中的源 - {bot.self_id}")
        return
    group_record = bot_record.get_group_record(event.group_id)
    if not group_record:
        logger.debug(
            f"群消息来自未处于缓存中的群 {bot.self_id}-{event.group_id}-{event.user_id}:{event.message_id}"
        )
        return
    user_record = group_record._get_or_create_user_record(event.user_id)
    _conversion_to_card_info(user_record, event.sender)  # type: ignore
    __merge_group_info_to_global(group_record)


@event_preprocessor
async def _(bot: Bot, event: PrivateMessageEvent):
    if not event.sub_type == "friend":
        logger.debug(
            f"不支持缓存的私聊类消息 {bot.self_id}-{event.sub_type}-{event.user_id}:{event.message_id}"
        )
        return
    bot_record = OnebotCache.get_instance().get_bot_record(int(bot.self_id))
    if not bot_record:
        logger.debug(f"私聊类事件来自未处于缓存中的源 - {bot.self_id}")
        return
    friend = bot_record.get_or_create_friend_record(event.user_id)
    sender: Dict[str, Any] = event.sender  # type: ignore
    if "nickname" in sender:
        friend.name = sender["nickname"]
    if "sex" in sender:
        friend.sex = sender["sex"]
    if "age" in sender:
        friend.age = sender["age"]
    friend.update_time = _now_int()
    __merge_unit_info_to_global(friend)


@Bot.on_calling_api
async def _(bot: BaseBot, api: str, data: Dict[str, Any]):
    """
        API 请求前
    """
    if not isinstance(bot, Bot):
        return
    bot_record = OnebotCache.get_instance().get_bot_record(int(bot.self_id))
    if bot_record:
        bot_record.call_api_count += 1
    else:
        logger.debug(f"Api请求来自未处于缓存中的源 - {bot.self_id}")


@Bot.on_called_api
async def _(bot: BaseBot, exception: Optional[Exception], api: str,
            data: Dict[str, Any], result: Any):
    """
        API 请求后
    """
    if not isinstance(bot, Bot):
        return
    bot_record = OnebotCache.get_instance().get_bot_record(int(bot.self_id))
    if bot_record:
        bot_record.last_activity = _now_int()
        if exception:
            bot_record.call_api_error_count += 1
            return
    else:
        logger.debug(f"Api响应来自未处于缓存中的源 - {bot.self_id}")
        return

    # 通过`Api`钩子自动更新缓存
    try:
        if api == "get_friend_list":
            friends: Dict[int, UnitRecord] = {}
            for entity in result:
                id = int(entity["user_id"])
                unit = UnitRecord(id)
                unit.name = entity["nickname"]
                unit.remark = entity["remark"]
                friends[id] = unit
                __merge_unit_info_to_global(unit)
            bot_record.friends = friends

        if api == "get_group_list":
            groups: Dict[int, GroupRecord] = {}
            for entity in result:
                id = int(entity["group_id"])
                group = GroupRecord(id)
                group.name = entity["group_name"]
                group.member_count = entity["member_count"]
                group.max_member_count = entity["max_member_count"]

                if "group_memo" in entity:
                    group.remark = entity["group_memo"]
                if "group_create_time" in entity:
                    group.group_create_time = entity["group_create_time"]
                if "group_level" in entity:
                    group.group_level = entity["group_level"]
                groups[id] = group
                __merge_group_info_to_global(group)
            bot_record.groups = groups

        if api in ("get_stranger_info", "get_group_member_info"):
            unit = OnebotCache.get_instance().get_or_create_unit_record(
                int(result["user_id"]))
            if "nickname" in result and result["nickname"]:
                unit.name = result["nickname"]
            unit.sex = result["sex"]
            unit.age = result["age"]
            unit.update_time = _now_int()

        if api == "get_group_info":
            bot_group = bot_record.get_or_create_group_record(
                int(result["group_id"]))
            if "group_name" in result and result["group_name"]:
                bot_group.name = result["group_name"]
            bot_group.member_count = result["member_count"]
            bot_group.max_member_count = result["max_member_count"]

            if "group_create_time" in result:
                bot_group.group_create_time = result["group_create_time"]
            if "group_level" in result:
                bot_group.group_level = result["group_level"]

            bot_group.update_time = _now_int()
            __merge_group_info_to_global(bot_group)

        if api == "get_group_member_info":
            bot_group = bot_record.get_or_create_group_record(
                int(result["group_id"]))
            bot_group.update_time = _now_int()
            user_record = bot_group._get_or_create_user_record(
                int(result["user_id"]))
            _conversion_to_card_info(user_record, result)
            __merge_group_info_to_global(bot_group)

        if api == "get_group_member_list":
            bot_group = bot_record.get_or_create_group_record(
                int(data["group_id"]))
            for res_data in result:
                user_record = bot_group._get_or_create_user_record(
                    int(res_data["user_id"]))
                _conversion_to_card_info(user_record, data)
            __merge_group_info_to_global(bot_group)

        if api == "get_login_info":
            if "nickname" in result and result["nickname"]:
                bot_record.name = result["nickname"]
            bot_record.update_time = _now_int()

    except Exception as e:
        logger.opt(exception=True).warning(f"缓存数据时异常！`{bot.self_id}`调用`{api}`")
        logger.debug("缓存数据时异常！`{}`调用`{}` \n\n 请求体 {} \n\n 响应 {}", bot.self_id,
                     api, data, result)


@scheduler.scheduled_job("interval", minutes=10, name="OB缓存_持久化")
async def sessions_check_and_recycling():
    OnebotCache.get_instance().save()


@scheduler.scheduled_job("interval", minutes=60, name="OB缓存_连接信息更新")
async def _():
    for key in driver.bots:
        bot = driver.bots[key]
        if not isinstance(bot, Bot):
            continue
        try:
            await bot.get_login_info()
        except Exception as e:
            logger.opt(exception=True).debug(f"获取OB11-{bot.self_id}登录号信息时异常")


@scheduler.scheduled_job("interval", minutes=20, name="OB缓存_群列表信息更新")
async def _():
    for key in driver.bots:
        bot = driver.bots[key]
        if not isinstance(bot, Bot):
            continue
        try:
            await bot.get_group_list()
        except Exception as e:
            logger.opt(exception=True).debug(f"获取OB11-{bot.self_id}群列表信息时异常")


@scheduler.scheduled_job("interval", minutes=20, name="OB缓存_好友列表信息更新")
async def _():
    for key in driver.bots:
        bot = driver.bots[key]
        if not isinstance(bot, Bot):
            continue
        try:
            await bot.get_friend_list()
        except Exception as e:
            logger.opt(exception=True).debug(f"获取OB11-{bot.self_id}好友列表信息时异常")


# @scheduler.scheduled_job('cron', hour='1', minute='30', name="OB缓存_群成员列表信息更新")
# async def _():
#     group_cache_info: Set[int] = set()
#     for key in driver.bots:
#         bot = driver.bots[key]
#         if not isinstance(bot, Bot):
#             continue
#         try:
#             group_list = await bot.get_group_list()
#             for group in group_list:
#                 if "group_id" in group:
#                     group_id = group["group_id"]
#                     if group_id in group_cache_info:
#                         continue
#                     await bot.get_group_member_list(group_id=group_id)
#                     group_cache_info.add(int(group_id))
#                     await asyncio.sleep(random.randint(60, 120))
#         except Exception as e:
#             logger.opt(exception=True).debug(f"获取OB11-{bot.self_id}群成员列表信息更新")
