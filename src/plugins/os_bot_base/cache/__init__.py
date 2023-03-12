"""
    # 缓存中心

    用于持久化缓存不同来源的数据，目前支持onebot v11协议。

    主要缓存的内容为昵称、群名片、群列表、成员列表、好友列表等信息。
"""
from .onebot import OnebotCache
