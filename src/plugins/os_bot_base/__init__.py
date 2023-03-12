"""
# OSBot核心基础插件

集成了核心服务，为其它插件提供支持。

## 支持功能

- `Session`支持（自动持久化、自动缓存、自动清理）
- 统一数据库维护（`tortoise`）
- 故障转移与优先响应（保证多个Bot在同一个群时同时只有一个Bot提供服务）
- 全局黑名单（支持自动屏蔽连接到此后端的bot之间的消息）
- 消息提醒（Bot离线、上线、内存异常、磁盘异常、功能异常等）
- 自动备份（非阻塞式的子进程备份）
- 日志重写（将日志重定向输出到数据目录）
- 基础运行数据收集（系统状态、数据分析）
- 插件管理（微侵入式）
- 插件帮助（基于插件元数据）
- 权限管理（侵入式）
- 数据缓存中心（昵称、群名片、群列表、成员列表、好友列表等）
- 参数解析工具（`Argmatch`）
- 插件工具集
- 插件依赖集
"""
from nonebot import get_driver, require

require("nonebot_plugin_apscheduler")

# 保证初始化
from . import logger
from . import config
from . import plugin_manage
from . import session
from . import cache
from . import database
from . import blacklist
from . import statistics
from . import failover
from . import apscheduler
from . import backup
from . import request
from . import permission
from . import infomation

from .exception import BaseException, StoreException

from .session import SessionManage, Session
from .cache import OnebotCache
from .adapter import AdapterFactory, AdapterException, Adapter
from .argmatch import ArgMatch, PageArgMatch, IntArgMatch, Field
from .consts import META_ADMIN_USAGE, META_NO_MANAGE, META_AUTHOR_KEY, META_SESSION_KEY, META_DEFAULT_SWITCH
from .database import DatabaseManage
from .depends import ArgMatchDepend, SessionDepend, AdapterDepend
from .util import matcher_exception_try, match_suggest, only_command, plug_is_disable, message_to_str

# 注入模型
from . import model

# 绑定启动注入
driver = get_driver()


@driver.on_startup
async def _():
    from .plugin_manage import plugin_manage_on_startup
    # 初始化缓存
    OnebotCache.get_instance()
    await DatabaseManage.get_instance()._init_()
    await plugin_manage_on_startup()


@driver.on_shutdown
async def _():
    from . import backup
    await DatabaseManage.get_instance()._close_()
    logger.logger.info("数据库链接已关闭")
    backup.pool._pool.shutdown(wait=True)  # 平滑的关闭进程
    logger.logger.info("备份进程已停止")


from .meta import __plugin_meta__
