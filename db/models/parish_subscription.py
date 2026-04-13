import uuid
from sqlalchemy.sql import func
from sqlalchemy import (
    Column,
    ForeignKey,
    Numeric,
    String,
    DateTime,
    Boolean,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from db.base_class import Base
from schemas.parish_subscription_schema import SubscriptionStatus
from sqlalchemy.orm import relationship


class ParishSubscription(Base):
    __tablename__ = "parish_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    parish_id = Column(
        UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=False, index=True
    )
    subscription_plan_id = Column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    start_date = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    end_date = Column(DateTime(timezone=True), nullable=False)
    last_renewed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status = Column(
        SAEnum(SubscriptionStatus, name="subscription_status", native_enum=False),
        nullable=False,
        default=SubscriptionStatus.active,
    )
    next_subscription_plan_id = Column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=True
    )
    last_plan_change_at = Column(DateTime(timezone=True), nullable=True)
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

    parish = relationship("Parish", back_populates="subscription")
    # Relationships
    subscription = relationship(
        "SubscriptionPlan",
        foreign_keys=[subscription_plan_id],
    )
    next_plan = relationship(
        "SubscriptionPlan",
        foreign_keys=[next_subscription_plan_id],
    )
    subscription_changes = relationship(
        "ParishSubscriptionChange",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )
    payments = relationship(
        "SubscriptionPayment",
        back_populates="parish_subscription",
        cascade="all, delete-orphan",
    )


class ParishSubscriptionChange(Base):
    __tablename__ = "parish_subscription_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    parish_subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("parish_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    parish_id = Column(UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=False)
    current_plan_id = Column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    next_plan_id = Column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    change_date = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    scheduled_start_date = Column(DateTime(timezone=True), nullable=True)
    scheduled_end_date = Column(DateTime(timezone=True), nullable=True)
    is_applied = Column(Boolean, default=False)

    parish = relationship("Parish", back_populates="subscription_changes")
    subscription = relationship(
        "ParishSubscription",
        back_populates="subscription_changes",
    )
    current_plan = relationship(
        "SubscriptionPlan",
        foreign_keys=[current_plan_id],
    )
    next_plan = relationship(
        "SubscriptionPlan",
        foreign_keys=[next_plan_id],
    )


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    parish_subscription_id = Column(
        UUID(as_uuid=True), ForeignKey("parish_subscriptions.id"), nullable=False
    )
    amount = Column(Numeric(10, 2), nullable=False)
    channel = Column(String, nullable=False)
    reference = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=False)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    parish_subscription = relationship(
        "ParishSubscription",
        back_populates="payments",
    )
    recorded_by_user = relationship("User")
