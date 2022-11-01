from typing import Optional, Union
from typing_extensions import Self
from nonebot.adapters import Event, Bot


class BaseAdapter:
    """
        适配器基类
    """
    instance: Optional[Self] = None

    @classmethod
    def get_type(cls) -> str:
        raise NotImplementedError("need implemented function!")

    @property
    def type(self) -> str:
        return self.get_type()

    async def mark(self, bot: Bot, event: Event) -> str:
        """
            获取事件的完整唯一标识

            **标识说明**

            驱动组标识-驱动标识-消息组父标识-消息组子标识-消息发送源父标识-消息发送源子标识

            **例**

            `cqhttp-123456-group-66543201-normal-65468248`

            `cqhttp-123456-private-12345-system-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_group(self, bot: Bot, event: Event) -> str:
        """
            获取事件的组唯一标识

            **标识说明**

            驱动组标识-驱动标识-消息组父标识-消息组子标识

            **例**

            `cqhttp-123456-group-66543201`

            `cqhttp-123456-private-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_without_drive(self, bot: Bot, event: Event) -> str:
        """
            获取事件的唯一标识（不含驱动）

            **标识说明**

            消息组父标识-消息组子标识-消息发送源父标识-消息发送源子标识

            **例**

            `group-66543201-normal-65468248`

            `private-12345-system-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_group_without_drive(self, bot: Bot, event: Event) -> str:
        """
            获取组的唯一标识（不含驱动）

            **标识说明**

            消息组父标识-消息组子标识

            **例**

            `group-66543201`

            `private-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_drive(self, bot: Bot, event: Event) -> str:
        """
            获取事件的驱动唯一标识

            **标识说明**

            驱动组标识-驱动标识

            **例**

            `cqhttp-123456`

            `cqhttp-123456`
        """
        return f"{self.type}-{bot.self_id}"

    async def get_group_nick(self,
                             group_id: Union[str, int],
                             bot: Optional[Bot] = None) -> str:
        return f"{group_id}"

    async def get_unit_nick(self,
                            user_id: Union[str, int],
                            bot: Optional[Bot] = None) -> str:
        return f"{user_id}"

    async def get_unit_nick_from_event(self,
                                       user_id: Union[str, int],
                                       bot: Optional[Bot],
                                       event: Optional[Event] = None) -> str:
        return f"{user_id}"

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance
