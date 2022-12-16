import os
from typing import List, Union
from nonebot import get_driver
from enum import Enum
from pydantic import BaseSettings, Field


class DriveEnum(str, Enum):
    file = "file"
    database = 'database'


class Config(BaseSettings):
    """
        # 基础配置

        - `os_data_path` 基础数据路径
        - `os_log_file_debug` 保存调试日志到文件
        - `os_database` 数据库地址，默认使用sqlite3，规范为sql数据库规范。
        - `os_session_save_model` session存储方式 支持：file(本地json)、database(使用db服务)
        - `os_session_timeout` session超时时间（分钟），超过此时间未被调用将自动回收，小于1时视为关闭，默认30。
        - `os_ob_black_eachother_private` 连接到此后端的bot私聊消息互相屏蔽
        - `os_ob_black_eachother_group` 连接到此后端的bot群消息互相屏蔽
        - `os_ob_black_user_list` onebot协议用户黑名单列表
        - `os_ob_black_group_list` onebot协议群组黑名单列表
        - `os_ob_notice_disconnect` onebot协议连接断开通知
        - `os_ob_notice_user_list` 默认紧急通知用户列表
        - `os_ob_notice_group_list` 默认紧急通知群列表
        - `os_notice_distusage` 是否启用磁盘用量提醒
        - `os_notice_distusage_percent` 磁盘用量提醒临界值（极限临界值为固定的95）
        - `os_notice_distusage_single` 磁盘用量以任一磁盘为标准（默认通过综合用量判断）
        - `os_notice_memoryusage` 内存用量提醒
        - `os_notice_memoryusage_percent` 内存用量提醒临界值
        - `os_backup_enable` 是否启用备份
        - `os_backup_day` 最大备份天数
        - `os_backup_session_enable` 启用session备份
        - `os_backup_database_enable` 启用database备份

    """
    superusers: List[Union[int, str]] = Field(default=[])

    os_data_path: str = Field(default=os.path.join(".", "data"))
    os_log_file_debug: bool = Field(default=False)
    os_database: str = Field(default="")
    os_session_save_model: DriveEnum = DriveEnum.file
    os_session_timeout: int = Field(default=30)
    os_ob_black_eachother_private: bool = Field(default=False)
    os_ob_black_eachother_group: bool = Field(default=True)
    os_ob_black_anonymous: bool = Field(default=True)
    os_ob_black_tmp: bool = Field(default=True)
    os_ob_black_user_list: List[int] = Field(default=[])
    os_ob_black_group_list: List[int] = Field(default=[])
    os_ob_notice_disconnect: bool = Field(default=True)
    os_ob_notice_user_list: List[int] = Field(default=[])
    os_ob_notice_group_list: List[int] = Field(default=[])

    os_notice_distusage: bool = Field(default=True)
    os_notice_distusage_percent: int = Field(default=90)
    os_notice_distusage_single: bool = Field(default=True)
    os_notice_memoryusage: bool = Field(default=True)
    os_notice_memoryusage_percent: int = Field(default=90)
    os_backup_enable: bool = Field(default=True)
    os_backup_day: int = Field(default=7)
    os_backup_session_enable: bool = Field(default=True)
    os_backup_database_enable: bool = Field(default=True)

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())
