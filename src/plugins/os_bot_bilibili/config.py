from time import time
from typing import Any, Dict, Optional, List
from pydantic import BaseSettings, Field
from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from bilibili_api import Credential, user
from bilibili_api import settings
from .bilibili import BilibiliOprateUtil
from .exception import BilibiliCookieVaildFailure, BilibiliOprateFailure

from ..os_bot_base import Session
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_PLUGIN_ALIAS


class Config(BaseSettings):
    """
        B站操作

        - `os_bot_bilibili_proxy` B站请求代理地址
        - `os_bot_bilibili_timeout` B站请求超时时间（默认15秒）
    """

    os_bot_bilibili_proxy: str = Field(default="")
    os_bot_bilibili_timeout: int = Field(default=15)

    class Config:
        extra = "ignore"


class BilibiliSession(Session):
    sessdata: Optional[str]
    bili_jct: Optional[str]
    last_vaild: float
    live_rtmp_addr: Optional[str]
    live_rtmp_code: Optional[str]

    _user_info: Optional[Dict[str, Any]]
    _live_info: Optional[Dict[str, Any]]
    _credential: Optional[Credential]
    _tmp_msg: Optional[str]
    _tmp_imgs: Optional[List[str]]
    _tmp_mask: Optional[str]
    _tmp_wait_confirm: bool
    _tmp_time: float

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.sessdata = None
        self.bili_jct = None
        self.last_vaild = 0
        self._user_info = None
        self._live_info = None
        self._credential = None
        self._tmp_msg = None
        self._tmp_mask = None
        self._tmp_time = 0
        self._tmp_wait_confirm = False
        self.live_rtmp_addr = None
        self.live_rtmp_code = None

    async def logout(self):
        self.sessdata = None
        self.bili_jct = None
        self.last_vaild = 0
        self._user_info = None
        self._live_info = None
        self._credential = None
        self._tmp_msg = None
        self._tmp_mask = None
        self._tmp_time = 0
        self._tmp_wait_confirm = False
        self.live_rtmp_addr = None
        self.live_rtmp_code = None

    async def get_credential(self) -> Optional[Credential]:
        """获取验证类，返回None意味着未登录或验证失败"""
        if not self.sessdata and not self.bili_jct:
            return None
        if not self._credential:
            self._credential = Credential(sessdata=self.sessdata,
                                          bili_jct=self.bili_jct)
        bo = BilibiliOprateUtil(self._credential)
        if time() - self.last_vaild > 86400:
            if await bo.async_check_valid():
                self.last_vaild = time()
                await self.save()
            else:
                self.bili_jct = None
                self.sessdata = None
                await self.save()
                return None
        return self._credential

    async def get_self_info(self) -> Dict[str, Any]:
        if self._user_info:
            return self._user_info
        credential = await self.get_credential()
        if not credential:
            raise BilibiliCookieVaildFailure("登录验证失败，请重新登录")
        try:
            self._user_info = await user.get_self_info(credential)
        except Exception as e:
            raise BilibiliOprateFailure("获取用户信息失败！", cause=e)
        return self._user_info

    async def get_self_live_info(self) -> Dict[str, Any]:
        if self._live_info:
            return self._live_info
        credential = await self.get_credential()
        if not credential:
            raise BilibiliCookieVaildFailure("登录验证失败，请重新登录")
        try:
            bo = BilibiliOprateUtil(credential)
            self._live_info = await bo.get_self_live_info()
        except Exception as e:
            raise BilibiliOprateFailure("获取用户直播间信息失败！", cause=e)
        return self._live_info


__plugin_meta__ = PluginMetadata(
    name="B站",
    description="OSBot B站 B站相关功能支持",
    usage="""
        支持指令`开启直播间 分区名`、`关闭直播间`、`修改直播标题`、`登录B站`、`B站登出`、`开始发送动态`等
        通过`B站功能帮助`查看操作说明
        若需要授权其他人操作可使用`授权 B级人员 @群成员`进行
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY:
        "ChenXuan",
        META_PLUGIN_ALIAS: [
            "开启直播间", "关闭直播间", "设置直播间标题", "修改直播间标题", "设置直播标题", "修改直播标题", "登录B站",
            "注销B站", "发送动态", "开始发送动态", "写草稿", "B站Cookie登录", "B站操作"
        ],
        META_ADMIN_USAGE:
        "什么都没有~",  # 管理员可以获取的帮助
        META_SESSION_KEY:
        BilibiliSession
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())

settings.proxy = config.os_bot_bilibili_proxy or None
