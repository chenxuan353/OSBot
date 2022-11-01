from typing import Optional
from nonebot.adapters.onebot import v11
from .adapter import BaseAdapter
from ..exception import AdapterException
from ..cache.onebot import OnebotCache


class V11Adapter(BaseAdapter):

    @classmethod
    def get_type(cls) -> str:
        return "ob11"

    async def mark(self, bot: v11.Bot, event: v11.Event) -> str:
        """
            获取事件的完整唯一标识

            **标识说明**

            驱动组标识-驱动标识-消息组父标识-消息组子标识-消息发送源父标识-消息发送源子标识

            **例**

            `ob11-123456-group-66543201-normal-65468248`

            `ob11-123456-private-12345-system-12345`
            ``
        """
        if isinstance(event, v11.MetaEvent):
            return f"{self.type}-{bot.self_id}-event-{event.post_type}-subtype-{event.meta_event_type}"
        if isinstance(event, v11.RequestEvent):
            return f"{self.type}-{bot.self_id}-event-{event.post_type}-subtype-{event.request_type}"
        if isinstance(event, v11.NoticeEvent):
            return f"{self.type}-{bot.self_id}-event-{event.post_type}-subtype-{event.notice_type}"
        if isinstance(event, v11.MessageEvent):
            if isinstance(event, v11.PrivateMessageEvent):
                return f"{self.type}-{bot.self_id}-private-{event.post_type}-{event.sub_type}-{event.user_id}"
            if isinstance(event, v11.GroupMessageEvent):
                return f"{self.type}-{bot.self_id}-group-{event.group_id}-{event.sub_type}-{event.user_id}"

        raise AdapterException(
            f"onebot-v11适配器不支持的事件类型`{bot.self_id}-{event.get_type()}-{event.get_event_name()}-{event.get_user_id()}`"
        )

    async def mark_group(self, bot: v11.Bot, event: v11.Event) -> str:
        """
            获取事件的组唯一标识

            **标识说明**

            驱动组标识-驱动标识-消息组父标识-消息组子标识

            **例**

            `ob11-123456-group-66543201`

            `ob11-123456-private-12345`
        """
        if isinstance(event, v11.MetaEvent):
            return f"{self.type}-{bot.self_id}-event-{event.post_type}"
        if isinstance(event, v11.RequestEvent):
            return f"{self.type}-{bot.self_id}-event-{event.post_type}"
        if isinstance(event, v11.NoticeEvent):
            return f"{self.type}-{bot.self_id}-event-{event.post_type}"
        if isinstance(event, v11.MessageEvent):
            if isinstance(event, v11.PrivateMessageEvent):
                return f"{self.type}-{bot.self_id}-private-{event.post_type}"
            if isinstance(event, v11.GroupMessageEvent):
                return f"{self.type}-{bot.self_id}-group-{event.group_id}"

        raise AdapterException(
            f"onebot-v11适配器不支持的事件类型`{self.type}-{bot.self_id}-{event.get_type()}-{event.get_event_name()}-{event.get_user_id()}`"
        )

    async def mark_without_drive(self, bot: v11.Bot, event: v11.Event) -> str:
        """
            获取事件的完整唯一标识

            **标识说明**

            驱动组标识-驱动标识-消息组父标识-消息组子标识-消息发送源父标识-消息发送源子标识

            **例**

            `ob11-123456-group-66543201-normal-65468248`

            `ob11-123456-private-12345-system-12345`
            ``
        """
        if isinstance(event, v11.MetaEvent):
            return f"event-{event.post_type}-subtype-{event.meta_event_type}"
        if isinstance(event, v11.RequestEvent):
            return f"event-{event.post_type}-subtype-{event.request_type}"
        if isinstance(event, v11.NoticeEvent):
            return f"event-{event.post_type}-subtype-{event.notice_type}"
        if isinstance(event, v11.MessageEvent):
            if isinstance(event, v11.PrivateMessageEvent):
                return f"private-{event.post_type}-{event.sub_type}-{event.user_id}"
            if isinstance(event, v11.GroupMessageEvent):
                return f"group-{event.group_id}-{event.sub_type}-{event.user_id}"

        raise AdapterException(
            f"onebot-v11适配器不支持的事件类型`{bot.self_id}-{event.get_type()}-{event.get_event_name()}-{event.get_user_id()}`"
        )

    async def mark_group_without_drive(self, bot: v11.Bot,
                                       event: v11.Event) -> str:
        """
            获取事件的组唯一标识

            **标识说明**

            驱动组标识-驱动标识-消息组父标识-消息组子标识

            **例**

            `ob11-123456-group-66543201`

            `ob11-123456-private-12345`
        """
        if isinstance(event, v11.MetaEvent):
            return f"event-{event.post_type}"
        if isinstance(event, v11.RequestEvent):
            return f"event-{event.post_type}"
        if isinstance(event, v11.NoticeEvent):
            return f"event-{event.post_type}"
        if isinstance(event, v11.MessageEvent):
            if isinstance(event, v11.PrivateMessageEvent):
                return f"private-{event.post_type}"
            if isinstance(event, v11.GroupMessageEvent):
                return f"group-{event.group_id}"

        raise AdapterException(
            f"onebot-v11适配器不支持的事件类型`{bot.self_id}-{event.get_type()}-{event.get_event_name()}-{event.get_user_id()}`"
        )

    async def get_group_nick(self,
                             group_id: int,
                             bot: Optional[v11.Bot] = None) -> str:
        group_id = int(group_id)
        nick = OnebotCache.get_instance().get_group_nick(group_id)
        if nick:
            return nick
        if bot:
            result = await bot.get_group_info(group_id=group_id)
            if result and "group_name" in result and result["group_name"]:
                nick = result["group_name"]
        if nick:
            return nick
        return f"{group_id}"

    async def get_unit_nick(self,
                            user_id: int,
                            bot: Optional[v11.Bot] = None) -> str:
        """
            获取昵称，或群内昵称。
        """
        user_id = int(user_id)
        nick = OnebotCache.get_instance().get_unit_nick(user_id)
        if nick:
            return nick
        if bot:
            result = await bot.get_stranger_info(user_id=user_id)
            if "nickname" in result and result["nickname"]:
                nick = result["nickname"]
        if nick:
            return nick
        return f"{user_id}"

    async def get_unit_nick_from_event(
            self,
            user_id: str or int,
            bot: Optional[v11.Bot],
            event: Optional[v11.Event] = None) -> str:
        nick = f"{user_id}"
        if not isinstance(event, v11.MessageEvent):
            return nick
        if event.sender.nickname:
            nick = event.sender.nickname
        if isinstance(event, v11.GroupMessageEvent):
            if event.sender.card:
                nick = event.sender.card
        return nick
