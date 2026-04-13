from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import Column, DateTime, Numeric, String, func
from sqlalchemy.ext.associationproxy import association_proxy
from db.base_class import Base
from sqlalchemy.orm import relationship


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    # Pivots connecting this plan to features
    features_pivot = relationship(
        "SubscriptionPlanFeaturePivot",
        back_populates="subscription_plan",
        cascade="all, delete-orphan",
    )

    # Convenience relationship to access features through the pivot
    features = relationship(
        "SubscriptionPlanFeature",
        secondary="subscription_plan_feature_pivot",
        viewonly=True,
    )
