"""
    基础常量
"""

# 插件元数据
META_SESSION_KEY: str = "session"
META_AUTHOR_KEY: str = "author"
META_NO_MANAGE: str = "bb_no_manage"
META_ADMIN_USAGE: str = "bb_admin_usage"

# Session
SESSION_SCOPE_PLUGIN: str = "plugin"

# ArgMatch
STATE_ARGMATCH: str = "_argmatch_check"
STATE_ARGMATCH_RESULT: str = "_argmatch_result"
"""
    在matcher运行前进行检查

    需要提供类本身而非实例
"""

BASE_PLUGIN_NAME: str = "BothBot核心"
