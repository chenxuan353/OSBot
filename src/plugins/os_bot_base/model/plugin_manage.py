from typing import Optional
from tortoise.models import Model
from tortoise import fields


class PluginModel(Model):
    """
        插件表

        此表仅供参考
    """

    class Meta:
        table = "bb_plugin"
        table_description = "插件表"

    id = fields.IntField(pk=True)
    name: str = fields.CharField(max_length=255,
                                 index=True,
                                 unique=True,
                                 description="插件索引标识")
    display_name: Optional[str] = fields.CharField(max_length=255,
                                                   null=True,
                                                   description="插件可阅读名称")
    module_name: Optional[str] = fields.CharField(max_length=255,
                                                  null=True,
                                                  description="模块路径")
    author: Optional[str] = fields.CharField(max_length=255,
                                             null=True,
                                             description="作者")
    des: Optional[str] = fields.CharField(max_length=255,
                                          null=True,
                                          description="描述")
    usage: Optional[str] = fields.TextField(null=True, description="帮助")
    admin_usage: Optional[str] = fields.TextField(null=True,
                                                  description="管理员帮助")
    switch: Optional[bool] = fields.BooleanField(description="开关状态",
                                                 null=True)  # type: ignore
    enable: bool = fields.BooleanField(max_length=255,
                                       default=True,
                                       description="启用状态")  # type: ignore
    change_time = fields.DatetimeField(auto_now=True)
    create_time = fields.DatetimeField(auto_now_add=True)


class PluginSwitchModel(Model):
    """
        插件开关数据表
    """

    class Meta:
        table = "bb_plugin_switch"
        table_description = "插件开关表"

    id = fields.IntField(pk=True)
    name: str = fields.CharField(max_length=255,
                                 index=True,
                                 unique=True,
                                 description="插件索引标识")
    group_mark: str = fields.CharField(max_length=255,
                                       index=True,
                                       unique=True,
                                       description="组掩码标识")
    switch: bool = fields.BooleanField(description="开关状态",
                                       null=True)  # type: ignore
    change_time = fields.DatetimeField(auto_now=True)
    create_time = fields.DatetimeField(auto_now_add=True)
