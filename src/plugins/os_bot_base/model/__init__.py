"""
    # 数据库模型
"""
from ..database import DatabaseManage
from .session import SessionModel
from .plugin_manage import PluginModel, PluginSwitchModel
# 载入数据模型
DatabaseManage.get_instance().add_model(SessionModel)
DatabaseManage.get_instance().add_model(PluginModel)
DatabaseManage.get_instance().add_model(PluginSwitchModel)
