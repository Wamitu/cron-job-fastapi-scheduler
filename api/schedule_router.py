from datetime import datetime, timezone
from typing import List

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.models.scheduled_email import ScheduledEmail
from db.session import get_db
from schemas.scheduled_email_schema import (
    ScheduledEmailCreate,
    ScheduledEmailResponse,
    ScheduledEmailUpdate,
)

router = APIRouter()


def _next_run(cron_expr: str) -> datetime:
    now = datetime.now(timezone.utc)
    return croniter(cron_expr, now).get_next(datetime).replace(tzinfo=timezone.utc)


def _get_or_404(db: Session, schedule_id: int) -> ScheduledEmail:
    job = db.query(ScheduledEmail).filter(ScheduledEmail.id == schedule_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return job


@router.post("/", response_model=ScheduledEmailResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduledEmailCreate, db: Session = Depends(get_db)):
    job = ScheduledEmail(**payload.model_dump(), next_run_at=_next_run(payload.cron_expression))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/", response_model=List[ScheduledEmailResponse])
def list_schedules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(ScheduledEmail).offset(skip).limit(limit).all()


@router.get("/{schedule_id}", response_model=ScheduledEmailResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, schedule_id)


@router.put("/{schedule_id}", response_model=ScheduledEmailResponse)
def update_schedule(
    schedule_id: int, payload: ScheduledEmailUpdate, db: Session = Depends(get_db)
):
    job = _get_or_404(db, schedule_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "cron_expression" in update_data:
        update_data["next_run_at"] = _next_run(update_data["cron_expression"])

    for field, value in update_data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return job


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    job = _get_or_404(db, schedule_id)
    db.delete(job)
    db.commit()


@router.post("/{schedule_id}/trigger", response_model=dict)
def trigger_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Manually dispatch the email for a schedule regardless of its next_run_at."""
    job = _get_or_404(db, schedule_id)
    from core.tasks import send_scheduled_email

    task = send_scheduled_email.delay(job.id)
    return {"message": "Email dispatch triggered", "task_id": str(task.id), "schedule_id": job.id}
