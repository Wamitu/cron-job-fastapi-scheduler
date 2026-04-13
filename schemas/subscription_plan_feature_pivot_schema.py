from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from schemas.subscription_plan_schema import SubscriptionPlanDetails


class SubscriptionPlanFeaturePivotCreate(BaseModel):
    subscription_plan_id: int
    feature_id: int
    enabled: bool = True


class SubscriptionPlanFeaturePivotDetails(BaseModel):
    id: UUID
    subscription_plan_id: UUID
    feature_id: UUID
    enabled: bool = True
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
