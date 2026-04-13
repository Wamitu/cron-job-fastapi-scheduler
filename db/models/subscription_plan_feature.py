import uuid
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.ext.associationproxy import association_proxy
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from db.base_class import Base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class SubscriptionPlanFeature(Base):
    __tablename__ = "subscription_plan_features"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationship to pivot table linking features to plans
    plans_pivot = relationship(
        "SubscriptionPlanFeaturePivot",
        back_populates="feature",
        cascade="all, delete-orphan",
    )
