import enum
import uuid
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base_class import Base


class NotificationType(enum.Enum):
    reminder = "reminder"
    info = "info"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    parish_id = Column(UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=True)
    notification_type = Column(Enum(NotificationType), nullable=False)
    message = Column(String, nullable=False)
    sent_at = Column(DateTime, server_default=func.now(), nullable=False)
    read_at = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
