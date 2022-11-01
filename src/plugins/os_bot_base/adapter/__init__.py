"""
    # 通用适配器

    用于提供不同场景下的插件兼容性
"""
from typing import Dict, Type
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import Bot as V11Bot
from .adapter import BaseAdapter
from .onebot import V11Adapter
from ..exception import AdapterException


class AdapterFactory:
    """
        适配器工厂

        用于获取实例映射
    """
    _ADAPTER_MAP: Dict[Type[Bot], Type[BaseAdapter]] = {V11Bot: V11Adapter}

    @classmethod
    def get_adapter(cls, bot: Bot) -> BaseAdapter:
        if bot.__class__ not in cls._ADAPTER_MAP:
            raise AdapterException(f"不兼容的适配类型{bot.__class__.__name__}")
        return cls._ADAPTER_MAP[bot.__class__].get_instance()
