from typing import Dict, List, Optional
from typing_extensions import Self
from .channel import Channel
from ..exception import BaseException
from ..logger import logger


class ChannelFactory:
    instance: Optional[Self] = None

    def __init__(self) -> None:
        self.channels: List[Channel] = []
        """注册的频道列表"""
        self.channel_name_map: Dict[str, Channel] = {}
        """注册表"""
        self.channel_alias_map: Dict[str, Channel] = {}
        """别名注册表"""

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance

    def register(self, channel: Channel):
        """
            注册一个频道

            channel 频道对应的类
            aliases 频道别名（始终被更明确的频道类型覆盖）
        """
        if self.channel_name_map.get(channel.channel_id, None):
            raise BaseException(f"无法映射重名频道 {channel.channel_id}")

        self.channels.append(channel)
        self.channel_name_map[channel.channel_id] = channel

        for name in channel.aliases:
            if self.channel_alias_map.get(name, None):
                logger.warning("一个重复的别名设置被忽略 名称 {} 冲突频道 {} -> {}", name,
                               channel.channel_id,
                               self.channel_alias_map[name].channel_id)
            else:
                self.channel_alias_map[name] = channel

    def get(self, name: str) -> Channel:
        return self.channel_alias_map[name]
    
    def get_map(self) -> Dict[str, Channel]:
        return self.channel_alias_map


channel_factory = ChannelFactory.get_instance()
