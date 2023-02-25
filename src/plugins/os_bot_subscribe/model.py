from datetime import datetime
from typing import Any, Dict
from tortoise.models import Model
from tortoise import fields
from ..os_bot_base import DatabaseManage


class SubscribeModel(Model):

    class Meta:
        table = "os_subscribe"
        table_description = "订阅表"

    id: int = fields.IntField(pk=True)
    group_mark: str = fields.CharField(index=True,
                                       max_length=255,
                                       description="组掩码标识")
    channel_type: str = fields.CharField(index=True,
                                         max_length=255,
                                         description="频道标识")
    channel_subtype: str = fields.CharField(index=True,
                                            max_length=255,
                                            description="频道子标识")
    channel_id: str = fields.CharField(index=True,
                                         max_length=255,
                                         description="频道id")
    subscribe: str = fields.CharField(index=True,
                                      max_length=255,
                                      description="订阅ID")
    options: Dict[str,
                  Any] = fields.JSONField(description="此字段以JSON形式存储，选项及相关参数")
    drive_mark: str = fields.CharField(max_length=255, description="驱动标识")
    bot_type: str = fields.CharField(max_length=255, description="关联的Bot标识")
    bot_id: str = fields.CharField(max_length=255, description="关联的BotID")
    send_param: Dict[str, Any] = fields.JSONField(
        description="此字段以JSON形式存储，发送消息时的参数")

    change_time: datetime = fields.DatetimeField(auto_now=True,
                                                 description="修改时间")
    create_time: datetime = fields.DatetimeField(auto_now_add=True,
                                                 description="创建时间")


DatabaseManage.get_instance().add_model(SubscribeModel)
