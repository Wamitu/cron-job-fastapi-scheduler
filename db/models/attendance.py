import uuid
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base_class import Base


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    parish_id = Column(
        UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=False, index=True
    )
    event_title = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    event_description = Column(String, nullable=False)
    event_date = Column(Date, nullable=False)
    marked_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    data = Column(JSON, nullable=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    parish = relationship("Parish")
    marked_by_user = relationship("User")
