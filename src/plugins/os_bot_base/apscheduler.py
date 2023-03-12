"""
    # `apscheduler`日志优化

    使`apscheduler`任务异常时可以调用`logoru`的异常堆栈打印
"""
from nonebot_plugin_apscheduler import scheduler
from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent, EVENT_JOB_MAX_INSTANCES, JobSubmissionEvent
from .logger import logger


def listener_error(event: JobExecutionEvent):
    logger.opt(exception=True).exception("Apscheduler job {} raised {} | {}",
                                         event.job_id, event.exception,
                                         event.traceback)


scheduler.add_listener(listener_error, EVENT_JOB_ERROR)
