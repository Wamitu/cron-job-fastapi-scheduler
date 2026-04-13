import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base_class import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    parish_id = Column(
        UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=False, index=True
    )
    collection_id = Column(
        UUID(as_uuid=True), ForeignKey("collections.id"), nullable=True, index=True
    )
    subscription_payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscription_payments.id"),
        nullable=True,
        index=True,
    )
    receipt_no = Column(String, nullable=False)
    generated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
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
