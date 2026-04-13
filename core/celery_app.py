import os
from celery.schedules import crontab
from celery import Celery
from datetime import datetime, timedelta

broker = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
backend = os.getenv("CELERY_RESULT_BACKEND", broker)

celery_app = Celery("iparish", broker=broker, backend=backend)
celery_app.conf.update(
    imports=["core.tasks"],
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# celery_app.conf.beat_schedule = {
#     "update-subscription-statuses-every-minute": {
#         "task": "core.tasks.update_subscription_statuses",
#         "schedule": timedelta(minutes=5),  # every 2 minutes
#         "options": {
#             "eta": datetime.utcnow() + timedelta(minutes=5)  # start 5 mins later
#         },
#     },
# }

celery_app.conf.beat_schedule = {
    "update-subscription-statuses-every-day-10am": {
        "task": "core.tasks.update_subscription_statuses",
        "schedule": crontab(minute=0, hour=10),  # Runs daily at 10:00 AM
        "options": {
            "eta": datetime.utcnow() + timedelta(minutes=5)  # start 5 mins later
        },
    },
}
