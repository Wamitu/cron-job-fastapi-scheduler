from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from db.base_class import Base


class ScheduledEmail(Base):
    __tablename__ = "scheduled_emails"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), nullable=False, default="UTC")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
