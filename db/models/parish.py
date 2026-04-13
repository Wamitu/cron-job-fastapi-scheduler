import uuid
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship
from db.base_class import Base


class Parish(Base):
    __tablename__ = "parishes"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    diocese_id = Column(UUID(as_uuid=True), ForeignKey("dioceses.id"), nullable=False)
    parish_data = Column(MutableDict.as_mutable(JSON), nullable=True)
    member_number_prefix = Column(String, nullable=False)
    member_number_suffix = Column(String, nullable=False)
    parish_settings = Column(MutableDict.as_mutable(JSON), nullable=True)
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

    diocese = relationship("Diocese", back_populates="parishes")
    users = relationship("User", back_populates="parish")
    subscription_changes = relationship(
        "ParishSubscriptionChange",
        back_populates="parish",
        cascade="all, delete-orphan",
    )
    subscription = relationship("ParishSubscription", back_populates="parish")
