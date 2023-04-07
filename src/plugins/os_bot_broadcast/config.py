from pydantic import BaseSettings
from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from ..os_bot_base import Session
from ..os_bot_base.consts import META_AUTHOR_KEY, META_ADMIN_USAGE, META_SESSION_KEY, META_PLUGIN_ALIAS


class Config(BaseSettings):
    """
        工具插件
    """

    class Config:
        extra = "ignore"


class UtilSession(Session):

    def __init__(self, *args, key: str = "default", **kws):
        super().__init__(*args, key=key, **kws)


__plugin_meta__ = PluginMetadata(
    name="广播",
    description="OSBot 广播，仅支持Onebot协议",
    usage="""
        收听就好
    """,
    config=Config,
    extra={
        META_AUTHOR_KEY: "ChenXuan",
        META_PLUGIN_ALIAS: ["broadcast"],
        META_ADMIN_USAGE: """
            通过`广播 频道`开始广播~
            通过`频道列表 [频道] [页码]`、`加入频道`、`退出频道`、`创建/清空/移除广播频道 频道名`、`添加/删除广播对象 [驱动] 组标识 组ID [昵称]`来管理频道
            支持通过`合并频道 [原频道] [目标频道]`合并两个频道，合并后原频道不变，目标频道将包含原频道的所有成员。
            特殊指令`同步推特/搬运组插件广播频道`用于生成所有启用了推特插件或搬运组插件的群列表，频道名为`推特`或`搬运组`

            特殊指令`同步群列表至频道 [频道名]`及`同步好友列表至频道 [频道名]`用于创建包含完整群与好友列表的广播频道
            注：可将`广播`指令的`广播`替换为`无感广播`来屏蔽标题
        """,  # 管理员可以获取的帮助
        META_SESSION_KEY: UtilSession,
    },
)

global_config = get_driver().config
config = Config(**global_config.dict())
