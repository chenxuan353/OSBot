import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from typing_extensions import Self
from pydantic import BaseSettings, Field
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base import Session
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_DEFAULT_SWITCH, META_PLUGIN_ALIAS

if TYPE_CHECKING:
    from .model import TwitterSubscribeModel


class Config(BaseSettings):
    os_twitter_stream_enable: bool = Field(default=False)
    """
        是否启用流式监听

        启用流式监听后轮询将被禁用
    """
    os_twitter_stream_rule_limit: int = Field(default=5)
    """
        推特流式监听规则限制

        一个规则约可监听13个账户，目前推特开发者基础版本是5个规则，提升版本是25个规则。
        可监听数量大致为65个及325个。
    """
    os_twitter_trans_api_enable: bool = Field(default=True)
    """通过推特API优化烤推"""
    os_twitter_poll_enable: bool = Field(default=False)
    """是否启用轮询"""
    os_twitter_poll_interval: int = Field(default=15)
    """推特轮询间隔"""
    os_twitter_proxy: str = Field(default="")
    """推特使用的代理"""
    os_twitter_key: str
    """应用程序 keyset"""
    os_twitter_secret: str
    """应用程序 密钥"""
    os_twitter_bearer: str
    """
        应用程序 Bearer

        os_twitter_bearer与os_twitter_key和os_twitter_secret的组合二选一
    """
    os_twitter_access_token: str
    """
        用户key

        必须拥有可写权限，否则只能手动维护关注列表

        写权限需要变更推特开发者账户的默认设置，然后重新生成token。

        可以获取写权限的APP，使用本插件附带的实用程序可生成其它用户的密钥对。
    """
    os_twitter_access_token_secret: str
    """用户密钥"""
    os_twitter_trans_engine: str = Field(default="")
    """推文机翻引擎，只有配置此项才会启用机翻"""

    os_data_path: str = Field(default=os.path.join(".", "data"))
    """数据目录"""
    os_twitter_trans_proxy: str = Field(default="")
    """烤推使用的代理"""
    os_twitter_trans_timeout: int = Field(default=15)
    """烤推超时时间，单位秒"""
    os_twitter_trans_script: str = Field(
        default=os.path.join(".", "twitter_trans_script.js"))
    """烤推使用的脚本路径"""
    os_twitter_trans_debug: bool = Field(default=False)
    """烤推的调试，开启后可以看到实时烤推界面（需要服务器图形化支持）"""
    os_twitter_trans_task_limit: int = Field(default=10)
    """烤推任务数限制"""
    os_twitter_trans_concurrent_limit: int = Field(default=2)
    """烤推并发处理限制"""
    os_twitter_trans_image_proxy: str = Field(default="")
    """烤推的图片代理，最终会拼接为 proxy/filename"""

    class Config:
        extra = "ignore"


class TwitterPlugSession(Session):
    _enable: bool
    """
        是否启用检测

        当遭遇问题时此开关可能自动关闭
    """
    following_list: List[str]
    """
        关注列表

        启动时获取，获取失败将使用缓存值
    """
    mention_following_list: List[str]
    """
        提及列表

        仅用于提及的列表
    """
    blacklist_following_list: List[str]
    """
        黑名单列表

        即使在监听中也无视的列表，也会视为无效监听
    """

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.following_list = []
        self.mention_following_list = []
        self.blacklist_following_list = []
        self._enable = True

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        return self


class TwitterSession(Session):
    failure_list: List[str]
    """发送失败的推文ID列表"""
    ban_users: List[str]
    """禁止推送"""
    num: int
    """推文序号"""
    tweet_map: Dict[str, str]
    """推文映射"""
    default_template: str
    """默认模版"""
    template_map: Dict[str, str]
    """模版映射"""
    default_sub_id: Optional[str]
    """当前的默认订阅（缓存推文列表等指令的默认订阅值）"""

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)
        self.failure_list = []
        self.ban_users = []
        self.num = 1
        self.tweet_map = {}
        self.default_template = "##无logo"
        self.template_map = {}
        self.default_sub_id = None

    def _init_from_dict(self, self_dict: Dict[str, Any]) -> Self:
        self.__dict__.update(self_dict)
        self.num = int(self.num)
        return self

    @classmethod
    def domain(cls):
        return "os_bot_twitter"


__plugin_meta__ = PluginMetadata(
    name="推特",
    description="OSBot推特功能支持，转推、烤推等",
    usage="""
        通过`推特用户 用户名`、`看推 链接/序号`查看推特数据
        通过`烤推 烤推配置`烤制推文
        其它命令`烤推历史`、`烤推结果 历史ID`
        可以通过`烤推帮助`命令查看详细介绍
        *在机翻可用的情况下，可以使用`机翻 #序号`来翻译指定推文
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["转推", "推特订阅", "烤推", "烤推模版"],
        META_ADMIN_USAGE: """
            通过`订阅推特 用户名 [选项]`、`取消推特订阅 用户名`、`推特订阅配置 用户名 [选项]`、`推特订阅列表`、`清空推特订阅`、`全局推特订阅列表`来管理订阅
            其它指令`看推 推文链接/序号`、`设置烤推模版 模版`、`设置用户烤推模版 用户 模版`
            维护指令`移除/添加转推黑名单`、`转推黑名单列表`、`全局烤推历史`、`清空推特缓存`、`检查流式监听`、`重载烤推脚本`、`重启烤推引擎`、`烤推引擎状态`
            可以通过`转推配置帮助`命令查看配置详细介绍，也可以通过`更新并重载烤推脚本`自动从git上更新烤推脚本。
            隐藏的常规命令`烤架`用于获取烤推状态，烤推绑定了默认授权的权限`烤推`，可以通过`权限禁用 烤推`来禁用烤推。
        """,  # 管理员可以获取的帮助
        META_SESSION_KEY: TwitterSession,
        META_DEFAULT_SWITCH: False
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
