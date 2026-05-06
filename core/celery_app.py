import os
from celery import Celery
from celery.schedules import crontab

broker = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

celery_app = Celery("CronJobScheduler", broker=broker, backend=backend)
celery_app.conf.update(
    imports=["core.tasks"],
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "dispatch_scheduled_emails": {
        "task": "core.tasks.dispatch_scheduled_emails",
        "schedule": crontab(minute="*"),  # every minute
    },
}
