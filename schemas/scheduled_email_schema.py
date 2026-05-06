from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
from croniter import croniter

_CRON_HINT = (
    'Must have 5 space-separated fields: "minute hour day month weekday". '
    'Example: "0 8 * * *" means every day at 08:00 UTC.'
)


def _check_cron(value: str) -> str:
    parts = value.strip().split()
    if len(parts) not in (5, 6, 7):
        raise ValueError(
            f'Expected 5 fields (or 6/7 with seconds/year), got {len(parts)}. {_CRON_HINT}'
        )
    if not croniter.is_valid(value):
        raise ValueError(f'Invalid cron expression "{value}". {_CRON_HINT}')
    return value


class ScheduledEmailCreate(BaseModel):
    name: str
    recipient_email: EmailStr
    subject: str
    message: str
    cron_expression: str
    timezone: str = "UTC"
    is_active: bool = True

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        return _check_cron(v)


class ScheduledEmailUpdate(BaseModel):
    name: Optional[str] = None
    recipient_email: Optional[EmailStr] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            _check_cron(v)
        return v


class ScheduledEmailResponse(BaseModel):
    id: int
    name: str
    recipient_email: str
    subject: str
    message: str
    cron_expression: str
    timezone: str
    is_active: bool
    created_at: datetime
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]

    model_config = {"from_attributes": True}
