import uuid
from sqlalchemy.sql import func
from sqlalchemy import (
    Boolean,
    Column,
)
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from db.base_class import Base


class SubscriptionPlanFeaturePivot(Base):
    __tablename__ = "subscription_plan_feature_pivot"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    subscription_plan_id = Column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id")
    )
    feature_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plan_features.id"))
    enabled = Column(Boolean, default=True)
    is_inherited = Column(Boolean, default=False)

    # Relationships
    subscription_plan = relationship(
        "SubscriptionPlan",
        back_populates="features_pivot",
    )
    feature = relationship(
        "SubscriptionPlanFeature",
        back_populates="plans_pivot",
    )
