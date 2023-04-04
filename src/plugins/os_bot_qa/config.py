from time import time
from typing import Any, Dict, List
from typing_extensions import Self
from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from dataclasses import dataclass, field

from ..os_bot_base.session import Session, StoreSerializable
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_PLUGIN_ALIAS, META_DEFAULT_SWITCH


class Config(BaseSettings):
    """
        工具插件
    """

    class Config:
        extra = "ignore"


class QAMode:
    """
        问答模式：关键词、完全匹配、模糊匹配
    """
    KEY: int = 0
    FULL: int = 1
    LIKE: int = 2


@dataclass
class QAUnit(StoreSerializable):
    """
        问答模块单条记录

        - `queston` 问题，不能与已有问题重复
        - `alias` 问题的别名，可以与已有问题重复，重复时将逐条比对直至
        - `answer` 答复
        - `mode` 问答模式
        - `hit_probability` 命中概率(1-100)
        - `oprate_log`  操作日志
        - `create_by`  创建者
        - `update_by`  最近更新人
        - `create_time` 创建时间
    """
    queston: str = field(default=None)  # type: ignore
    answers: List[str] = field(default_factory=list)  # type: ignore
    alias: List[str] = field(default_factory=list)  # type: ignore
    mode: int = field(default=None)  # type: ignore
    hit_probability: int = field(default=None)  # type: ignore
    oprate_log: str = field(default=None)  # type: ignore
    create_by: int = field(default=None)  # type: ignore
    update_by: int = field(default=None)  # type: ignore
    create_time: int = field(default_factory=(lambda: int(time())), init=False)


class QASession(Session):

    QAList: Dict[str, QAUnit]
    _alias_index: Dict[str, List[QAUnit]]
    _alias_index_generate_time: float

    global_enable: bool = True

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.QAList = {}
        self._alias_index = {}
        self._alias_index_generate_time = 0

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)

        # 加载 shut_list
        tmp_list: Dict[str, Any] = self.QAList
        self.QAList = {}
        for key in tmp_list:
            unit = QAUnit._load_from_dict(tmp_list[key])
            self.QAList[unit.queston] = unit

        self.generate_index()

        return self

    async def save(self):
        self.generate_index()
        return await super().save()

    def generate_index(self):
        self._alias_index = {}
        self._alias_index_generate_time = time()
        for queston in self.QAList:
            unit = self.QAList[queston]
            for alia in unit.alias:
                if alia not in self._alias_index:
                    self._alias_index[alia] = []
                self._alias_index[alia].append(unit)


__plugin_meta__ = PluginMetadata(
    name="问答",
    description="OSBot 简单问答模块",
    usage="""
        可以通过`教你 问题>回复`或是`添加问答 问题>回复1>回复2`来添加一条问答
        通过`问答列表`、`查看问答 问题[>页码]`、`忘掉问答 问题`、`忘记问答回复 问题>问答ID`、`设置问题完全/关键词/模糊匹配 问题`及`添加别名 问题>别名`来管理问答
        另外可以通过`设置问题回复率 问题=回复概率`来管理此问题的回复概率，概率取值为1-100，默认为100。
        全局问答库设置`启用/禁用全局问答库`
        关于模式的说明：
        模糊 默认模式，类似关键词，但是进行了优化，不会回复过长的消息
        关键词 包含关键词就可触发
        完全 需要完全匹配才会触发
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["问答库", "问答列表"],
        META_ADMIN_USAGE: """
            可以通过`清空问答库`来清空所有问答。
            问答库同时绑定了`问答库`权限，拥有`问答库`权限的成员可以对问答进行除清空以外的管理。
            授权指令参考 `权限授予 @某人 问答库 [时限]`
            通过`添加全局问答`、`全局问答列表`、`查看全局问答`、`删除全局问答`、`删除全局问答回复`、`设置全局问题回复率`及`设置全局问答完全/关键词/模糊匹配`等指令来管理全局问答
            全局问答库默认设置`默认启用/禁用全局问答库`
        """,  # 管理员可以获取的帮助
        META_SESSION_KEY: QASession,
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
