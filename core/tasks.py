from datetime import datetime, timezone
from croniter import croniter
from sqlalchemy import or_
from sqlalchemy.orm import Session
from db.session import SessionLocal
from utils.email_client import send_email
from core.celery_app import celery_app


@celery_app.task(name="core.tasks.dispatch_scheduled_emails")
def dispatch_scheduled_emails():
    """
    Runs every minute via Celery Beat. Finds jobs that are due, dispatches
    the email task for each, then advances next_run_at to the following occurrence.
    Jobs with no next_run_at (newly created) only get their schedule initialised.
    """
    from db.models.scheduled_email import ScheduledEmail

    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        active_jobs = (
            db.query(ScheduledEmail)
            .filter(
                ScheduledEmail.is_active == True,
                or_(
                    ScheduledEmail.next_run_at <= now,
                    ScheduledEmail.next_run_at == None,
                ),
            )
            .all()
        )

        for job in active_jobs:
            cron = croniter(job.cron_expression, now)
            next_run = cron.get_next(datetime).replace(tzinfo=timezone.utc)

            if job.next_run_at is not None and job.next_run_at <= now:
                send_scheduled_email.delay(job.id)

            job.next_run_at = next_run

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="core.tasks.send_scheduled_email")
def send_scheduled_email(job_id: int):
    """Sends the email for a single scheduled job and records the run time."""
    from db.models.scheduled_email import ScheduledEmail

    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        job = (
            db.query(ScheduledEmail)
            .filter(ScheduledEmail.id == job_id, ScheduledEmail.is_active == True)
            .first()
        )
        if not job:
            return

        send_email(job.recipient_email, job.subject, job.message)

        job.last_run_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
