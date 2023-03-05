from typing import Optional, Union
from typing_extensions import Self
from nonebot.adapters import Event, Bot


class Adapter:
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

    async def get_bot_id(self, bot: Bot, event: Event) -> str:
        """
            获取此驱动的bot唯一ID
        """
        raise NotImplementedError("need implemented function!")

    async def mark(self, bot: Bot, event: Event) -> str:
        """
            获取事件的完整唯一标识

            **标识说明**

            驱动组标识-驱动ID-消息组父标识-消息组子标识-消息发送源父标识-消息发送源子标识

            **例**

            `cqhttp-123456-group-66543201-normal-65468248`

            `cqhttp-123456-private-12345-system-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_group(self, bot: Bot, event: Event) -> str:
        """
            获取事件的组唯一标识

            **标识说明**

            驱动组标识-驱动ID-消息组父标识-消息组子标识

            **例**

            `cqhttp-123456-group-66543201`

            `cqhttp-123456-private-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_only_unit(self, bot: Bot, event: Event) -> str:
        """
            获取事件的用户唯一标识

            **标识说明**

            驱动组标识-驱动ID-global-global-消息发送源父标识-消息发送源子标识

            **例**

            `cqhttp-123456-global-global-normal-65468248`

            `cqhttp-123456-global-global-system-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_only_unit_without_drive(self, bot: Bot,
                                           event: Event) -> str:
        """
            获取事件的用户唯一标识

            **标识说明**

            驱动组标识-global-global-global-消息发送源父标识-消息发送源子标识

            **例**

            `cqhttp-global-global-global-normal-65468248`

            `cqhttp-global-global-global-system-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_without_drive(self, bot: Bot, event: Event) -> str:
        """
            获取事件的唯一标识（不含驱动标识）

            **标识说明**

            驱动组标识-global-消息组父标识-消息组子标识-消息发送源父标识-消息发送源子标识

            **例**

            `cqhttp-global-group-66543201-normal-65468248`

            `cqhttp-global-private-12345-system-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_group_without_drive(self, bot: Bot, event: Event) -> str:
        """
            获取组的唯一标识（不含驱动标识）

            **标识说明**

            驱动组标识-global-消息组父标识-消息组子标识

            **例**

            `cqhttp-global-group-66543201`

            `cqhttp-global-private-12345`
        """
        raise NotImplementedError("need implemented function!")

    async def mark_drive(self, bot: Bot, event: Event) -> str:
        """
            获取事件的驱动唯一标识

            **标识说明**

            驱动组标识-驱动ID

            **例**

            `cqhttp-123456`

            `cqhttp-123456`
        """
        return f"{self.type}-{bot.self_id}"

    async def get_group_nick(self,
                             group_id: Union[str, int],
                             bot: Optional[Bot] = None) -> str:
        """
            获取群昵称 提供bot参数时视为可通过api获取
        """
        return f"{group_id}"

    async def get_unit_nick(self,
                            user_id: Union[str, int],
                            bot: Optional[Bot] = None,
                            group_id: Optional[int] = None) -> str:
        """
            获取用户昵称 提供bot参数时视为可通过api获取
        """
        return f"{user_id}"

    async def get_unit_nick_from_event(self,
                                       user_id: Union[str, int],
                                       bot: Optional[Bot],
                                       event: Optional[Event] = None) -> str:
        """
            从事件中获取用户昵称
        """
        return f"{user_id}"

    async def msg_is_multi_group(self, bot: Bot, event: Event) -> bool:
        """
            消息是否来自多人群组
        """
        raise NotImplementedError("need implemented function!")

    async def msg_is_private(self, bot: Bot, event: Event) -> bool:
        """
            消息是否来自私聊
        """
        raise NotImplementedError("need implemented function!")

    async def get_unit_id_from_event(self, bot: Bot,
                                     event: Event) -> Union[str, int]:
        return event.get_user_id()

    async def get_group_id_from_event(self, bot: Bot,
                                      event: Event) -> Union[str, int]:
        raise NotImplementedError("need implemented function!")

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance
