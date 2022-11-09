from nonebot.adapters import Message
from nonebot.params import CommandArg


def only_command():
    """
        匹配无参数命令
    """

    async def checker(msg: Message = CommandArg()) -> bool:
        return not msg

    return checker
