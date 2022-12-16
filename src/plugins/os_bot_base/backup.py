"""
    定时备份一些需要备份的东西
"""
import os
from typing import Optional
from typing_extensions import Self
import zipfile
from time import strftime, time
from concurrent.futures import ProcessPoolExecutor
from nonebot_plugin_apscheduler import scheduler
from .config import config
from .logger import logger

from ..os_bot_base.util.async_pool import AsyncPool

pool = AsyncPool(ProcessPoolExecutor(max_workers=1))


class ZipBackup:
    instance: Optional[Self] = None

    def __init__(self) -> None:
        pass

    @classmethod
    def get_instance(cls) -> Self:
        if not cls.instance:
            cls.instance = cls()
        return cls.instance

    def _pool_backup_database(self):
        dbpath = os.path.join(config.os_data_path, "database")
        bk_file_path = os.path.join(
            config.os_data_path, "backup",
            f"database-{strftime('%Y-%m-%d_%H%M%S')}.bak.zip")
        zf = zipfile.ZipFile(bk_file_path, 'w', zipfile.ZIP_DEFLATED)
        for root, dirs, files in os.walk(dbpath):
            for item in files:
                file_path = os.path.join(root, item)
                zf.write(file_path, item)
        zf.close()

    def _pool_backup(self):
        self._pool_backup_database()

    async def backup(self):
        return await pool.submit(self._pool_backup)

    async def clear_backup_file(self):
        """清理指定天数前的备份文件"""
        expire_days = config.os_backup_day
        expire_times = expire_days * 24 * 3600
        current_time = time()
        path = os.path.join(config.os_data_path, "backup")

        for root, dirs, files in os.walk(path):
            for item in files:
                file_path = os.path.join(root, item)
                create_time = os.stat(file_path).st_mtime
                time_difference = current_time - create_time
                if time_difference > expire_times:
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.error("移除超过{}天的备份文件时异常 {} {} | {}",
                                     str(expire_days), e.__class__.__name__,
                                     str(e), file_path)
                        continue
                    logger.info("移除超过{}天的备份文件 {}", str(expire_days), file_path)


@scheduler.scheduled_job('cron', hour='4', minute='30', name="自动备份")
async def _():
    zip_backup = ZipBackup.get_instance()
    logger.info("开始自动备份")
    await zip_backup.backup()
    logger.info("自动备份完成")
    await zip_backup.clear_backup_file()
    logger.info("超期备份清理完成")
