from asyncio.log import logger
import json
import os
from time import time
from typing import Any, Dict, List, Optional, Type
from typing_extensions import Self
from tortoise.exceptions import DoesNotExist
from nonebot_plugin_apscheduler import scheduler
from .config import config
from .exception import StoreException
from .model.session import SessionModel


class StoreSerializable:
    """
        此类型用于支持Session自定义对象的Json的序列化与反序列化
    """

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
        """
            从字典中生成本类的实例，该方法在加载时自动调用，同时也会调用`_init_from_dict`方法
            
            **非必要请勿覆写此方法**
        """
        return cls()._init_from_dict(self_dict)


class StoreEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, StoreSerializable):
            return obj._serializable()
        else:
            return super(StoreEncoder, self).default(obj)


class Session(StoreSerializable):
    """Session

    继承`collections.UserDict`，并且实现了`__getattribute__`与`__setattr__`方法

    插件使用前请优先继承，而不是直接使用。

    以`_`或`tmp_`起始的键不会被持久化
    
    存储时调用`json.dump`，实现了自定义编码器，继承`StoreSerializable`类或基本类型均可以正常序列化。

    > 原则上不允许覆盖内置键`key`、`data`等。
    > 长时间不进行调用的`Session`可能会被意外回收，需要持久使用时可以通过`with`语法延长生命周期。
    > 通过`with`调用将自动保存
    > 被锁定的`Session`将不会自动保存
    """

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, **kws)
        self._key: str = f"{key}"
        self._keep: bool = False
        self._session_manage: "SessionManage" = None  # type: ignore

    @property
    def key(self) -> str:
        return self._key

    @classmethod
    def domain(cls) -> Optional[str]:
        """
            域

            覆盖此属性用以增强唯一性，默认使用的域为`nonebot`提供的插件标识符
        """
        return None

    def reset(self) -> None:
        """
            重置 `session`

            在需要重置`session`的时候会自动调用此方法
        """
        self.data = {}

    async def save(self):
        await self._session_manage.save(self)

    async def _lock(self) -> None:
        self._keep = True
        await self._session_manage._hook_session_activity(self.key)

    async def _unlock(self) -> None:
        self._keep = False
        await self._session_manage._hook_session_activity(self.key)

    async def __aenter__(self, *_, **kws) -> Self:
        await self._lock()
        return self

    async def __aexit__(self, *_, **kws):
        await self._unlock()
        await self.save()

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        """
            初始化实例，该方法在加载时自动调用。

            如若需要自定义加载，请覆盖此方法。
        """
        self.__dict__.update(self_dict)
        return self


class BaseStore:
    """
        Session存储器基类
    """

    def to_json(self, session: Session) -> str:
        try:
            return json.dumps(session._serializable(),
                              ensure_ascii=False,
                              sort_keys=True,
                              indent=2,
                              cls=StoreEncoder)
        except Exception as e:
            raise StoreException("Store JSON 序列化异常", cause=e)

    def load_json(self, json_str: str) -> Dict[str, Any]:
        try:
            return json.loads(json_str)
        except Exception as e:
            raise StoreException("Store JSON 反序列化异常", cause=e)

    async def read(self,
                   key: str,
                   SessionType: Type[Session] = Session) -> Session:
        raise NotImplementedError("need implemented read function!")

    async def save(self, session: Session):
        raise NotImplementedError("need implemented save function!")


class FileStore(BaseStore):
    """
        文件系统存储
    """

    def __init__(self) -> None:
        """
            base_path: str 文件存储基准路径
        """
        super().__init__()
        self.base_path: str = os.path.join(config.os_data_path, "session")
        self.encoding: str = "utf-8"

        if not os.path.isdir(self.base_path):
            try:
                os.makedirs(self.base_path)
            except IOError as e:
                raise StoreException(f"目录 {self.base_path} 创建失败！", e)

    def backup_file(self, key: str):
        file_path = os.path.join(self.base_path, key)
        if not os.path.isfile(file_path + ".json"):
            return
        i = 0
        while os.path.exists(file_path + f".{i}.bak"):
            i += 1

        try:
            os.rename(f"{file_path}.json", f"{file_path}.{i}.bak")
        except Exception as e:
            raise StoreException(f"文件`{file_path}.json`备份失败，可能导致数据异常或丢失！",
                                 cause=e)

    async def read(self,
                   key: str,
                   SessionType: Type[Session] = Session) -> Session:
        old_file_path = os.path.join(self.base_path, key + ".json")
        # 进行兼容性变换
        deal_key = key
        if deal_key.startswith("src.plugins."):
            deal_key = deal_key[len("src.plugins."):]
        key_splits = deal_key.split(".")
        deal_key = key_splits.pop()
        save_addpath = os.path.join(self.base_path, *key_splits)
        file_path = os.path.join(save_addpath, deal_key + ".json")

        if not os.path.isdir(save_addpath):
            try:
                os.makedirs(save_addpath)
            except IOError as e:
                raise StoreException(f"目录 {save_addpath} 创建失败！", e)

        if os.path.isfile(old_file_path):
            try:
                os.rename(old_file_path, file_path)
            except IOError as e:
                raise StoreException(
                    f"session兼容性更新失败 从`{old_file_path}`移动至`{file_path}`", e)

        if not os.path.isfile(file_path):
            return SessionType(key=key)
        try:
            with open(file_path, mode='r', encoding=self.encoding) as fr:
                json_str = fr.read()
                data = self.load_json(json_str)
                session = SessionType._load_from_dict(data)
                session._key = key
                return session
        except Exception as e:
            now_e = e
            try:
                self.backup_file(key)
            except Exception as e:
                now_e = e
            raise StoreException(f"数据文件`{file_path}`读取异常。", cause=now_e)

    async def save(self, session: Session):
        # 进行兼容性变换
        deal_key = session.key
        if deal_key.startswith("src.plugins."):
            deal_key = deal_key[len("src.plugins."):]
        key_splits = deal_key.split(".")
        deal_key = key_splits.pop()
        save_addpath = os.path.join(*key_splits)
        file_path = os.path.join(self.base_path, save_addpath,
                                 deal_key + ".json")
        try:
            with open(file_path, mode='w', encoding=self.encoding) as fw:
                fw.write(self.to_json(session))
        except Exception as e:
            raise StoreException(f"数据文件`{file_path}`写入异常", cause=e)


class DatabaseStore(BaseStore):
    """
        数据库存储
    """

    def __init__(self) -> None:
        super().__init__()

    async def read(self,
                   key: str,
                   SessionType: Type[Session] = Session) -> Session:
        try:
            try:
                model = await SessionModel.get(**{"key": key})
            except DoesNotExist as e:
                return SessionType(key=key)

            if not model:
                raise Exception(f"未知异常，数据模型`{key}`获取失败")
            json_str = model.json
            data = self.load_json(json_str)
            return SessionType._load_from_dict(data)
        except Exception as e:
            raise StoreException(f"数据库读取`{key}` Session 失败", cause=e)

    async def save(self, session: Session):
        key: str = session.key
        try:
            model, _ = await SessionModel.get_or_create({"key": key},
                                                        **{"key": key})
            model.json = self.to_json(session)
            await model.save()
        except Exception as e:
            raise StoreException(f"数据库保存`{key}` Session 失败", cause=e)


class SessionManage:
    """
        Session管理器

        维护Session的完整生命周期
    """
    __STORE_MAP: Dict[str, Type[BaseStore]] = {"file": FileStore}
    session_manage: Optional["SessionManage"] = None

    def __init__(self) -> None:
        self.__sessions: Dict[str, Session] = {}

        self.store: BaseStore = self.__STORE_MAP[
            config.os_session_save_model]()

        self.timeout = config.os_session_timeout * 60
        self.timeout_map: Dict[str, float] = {}

        if self.timeout < 60:
            self.timeout = -1

    @property
    def sessions(self):
        return self.__sessions

    async def _hook_session_activity(self, key: str):
        self.timeout_map[key] = time()

    async def _recycling_sessions(self, session_keys: List[str]):
        """
            回收`session`，保存并从缓存中移除
        """
        for key in session_keys:
            session = self.sessions[key]
            await session.save()
            del self.sessions[key]
            del self.timeout_map[key]

    async def _collect_invalid_session(self) -> List[str]:
        """
            收集无效的`session key`
        """
        if self.timeout == -1:
            return []
        now_time = time()
        sessions: List[str] = []
        for key in self.timeout_map:
            if now_time - self.timeout_map[key] > self.timeout:
                if self.sessions[key]._keep:
                    """持久化的`session`"""
                    await self._hook_session_activity(key)
                else:
                    sessions.append(key)
        return sessions

    async def _sessions_check_and_recycling(self):
        """
            检查并回收`session`
        """
        if self.timeout == -1:
            return
        session_keys = await self._collect_invalid_session()
        await self._recycling_sessions(session_keys)

    async def generate_session(
            self,
            key: str,
            plug_scope: str = "global",
            SessionType: Type[Session] = Session) -> Session:
        """
            生成`session`
        """
        key = f"{plug_scope}_{key}_{SessionType.__name__}"
        if not self.sessions.get(key):
            self.sessions[key] = await self.store.read(key, SessionType)
        if not self.sessions.get(key):
            self.sessions[key] = SessionType(key=key)
        self.sessions[key]._session_manage = self
        await self._hook_session_activity(key)
        return self.sessions[key]

    async def get(self,
                  key: str,
                  plug_scope: str = "global",
                  SessionType: Type[Session] = Session) -> Session:
        """
            从持久化存储中获取`session`
        """
        return self.sessions.get(f"{plug_scope}_{key}_{SessionType.__name__}"
                                 ) or await self.generate_session(
                                     key, plug_scope, SessionType)

    async def save(self, session: Session) -> None:
        """
            保存`session`（持久化至存储）
        """
        await self.store.save(session)

    async def reset_session(self,
                            key: str,
                            plug_scope: str = "global",
                            SessionType: Type[Session] = Session) -> None:
        """
            重置指定`session`
        """
        key = f"{plug_scope}_{key}"
        if not self.sessions.get(key):
            self.sessions[key] = await self.store.read(key, SessionType)
        if not self.sessions.get(key):
            self.sessions[key] = SessionType(key=key)
        self.sessions[key].reset()

    @classmethod
    def get_instance(cls) -> Self:
        if not cls.session_manage:
            cls.session_manage = cls()
        return cls.session_manage


@scheduler.scheduled_job("interval", minutes=5, name="Session回收")
async def sessions_check_and_recycling():
    sm = SessionManage.get_instance()
    logger.debug("执行`Session`回收，当前：{}", len(sm.sessions))
    await SessionManage.get_instance()._sessions_check_and_recycling()
    logger.debug("`Session`回收完毕，当前：{}", len(sm.sessions))
