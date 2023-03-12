from tortoise.models import Model
from tortoise import fields


class SessionModel(Model):
    """
        Session模型

        支持session的数据库存储功能
    """

    class Meta:
        table = "os_session"
        table_description = "session表"

    id = fields.IntField(pk=True, generated=True)
    key: str = fields.CharField(max_length=255,
                                index=True,
                                null=False,
                                unique=True,
                                description="session key")
    json: str = fields.TextField(description="数据段")
    change_time = fields.DatetimeField(auto_now=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    def __str__(self):
        return self.key
