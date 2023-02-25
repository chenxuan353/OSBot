"""
# 基础插件

为其它插件提供基础服务。

## 核心功能

持久化作用域Session、数据库统一维护、插件工具、插件管理(非侵入式)、插件帮助（基于插件元数据）、权限管理（侵入式）、数据缓存中心（昵称、群名片、群列表、成员列表、好友列表等）
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
    backup.pool._pool.shutdown(wait=True) # 平滑的关闭进程
    logger.logger.info("备份进程已停止")


from .meta import __plugin_meta__
