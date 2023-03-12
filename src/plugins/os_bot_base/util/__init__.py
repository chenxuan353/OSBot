"""
    # 工具集

    提供了一系列工具用于插件的编写

    包括插件是否被禁用、从关键词与标题列表中获取输入建议、处理matcher异常、消息转字符串、秒数转时间描述、
    多线程/多进程异步包裹器、限速桶、仅指令规则(用于on_command的rule)、获取插件session、获取session、
    字符串全角半角转换、移除字符串控制字符等
"""
from .normal import plug_is_disable, match_suggest, matcher_exception_try, message_to_str, seconds_to_dhms
from .async_pool import AsyncPool, AsyncPoolSimple
from .token_bucket import TokenBucket, TokenBucketTimeout, AsyncTokenBucket
from .rule import only_command
from ..depends import get_plugin_session, get_session
from .zh_util import stringQ2B, stringB2Q, stringpartQ2B, strip_control_characters
