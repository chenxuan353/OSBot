from tortoise.models import Model
from tortoise import fields
from ..os_bot_base import DatabaseManage


class Feedback(Model):

    class Meta:
        table = "os_feedback"
        table_description = "反馈表"

    id = fields.IntField(pk=True)
    source_mark: str = fields.CharField(max_length=255,
                                        index=True,
                                        description="反馈来源标识")
    source: str = fields.CharField(max_length=255,
                                   index=True,
                                   description="来源")
    msg: str = fields.TextField(description="反馈的内容")
    deal: bool = fields.BooleanField(max_length=255,
                                     default=False,
                                     description="反馈处理状态")  # type: ignore
    change_time = fields.DatetimeField(auto_now=True)
    create_time = fields.DatetimeField(auto_now_add=True)


DatabaseManage.get_instance().add_model(Feedback)
