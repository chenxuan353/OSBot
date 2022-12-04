"""
    RSShub订阅支持

    按照rsshub订阅的定义，频道的子类型将被划定为模块名
"""
from . import config
from . import polling
from .subchannel import *
