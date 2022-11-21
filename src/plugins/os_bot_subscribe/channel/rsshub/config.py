from typing import List
from pydantic import BaseSettings, Field
from nonebot import get_driver
from ...exception import BaseException



class Config(BaseSettings):
    os_subscribe_rsshub_enable: bool = Field(default=False)
    """是否启用rsshub订阅"""
    os_subscribe_rsshub_timeout: int = Field(default=5)
    """订阅超时时间"""
    os_subscribe_rsshub_urls: List[str] = Field(default_factory=list)
    """订阅链接，默认使用列表中的第一个作为测试源"""

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())

if config.os_subscribe_rsshub_enable and not config.os_subscribe_rsshub_urls:
    raise BaseException("开启rsshub订阅必须设置订阅链接！")
