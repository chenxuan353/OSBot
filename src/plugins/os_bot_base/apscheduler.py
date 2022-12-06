from nonebot_plugin_apscheduler import scheduler
from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent, EVENT_JOB_MAX_INSTANCES, JobSubmissionEvent
from .logger import logger


def listener_error(event: JobExecutionEvent):
    logger.opt(exception=True).exception("Apscheduler job {} raised {} | {}",
                                         event.job_id, event.exception,
                                         event.traceback)


scheduler.add_listener(listener_error, EVENT_JOB_ERROR)
