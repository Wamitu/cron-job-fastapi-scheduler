from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from schemas.subscription_plan_feature_schema import SubscriptionPlanFeatureDetails


class Feature(BaseModel):
    id: UUID
    name: str
    description: str
    enabled: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanCreate(BaseModel):
    name: str
    price: Decimal


class SubscriptionPlanDetails(BaseModel):
    id: UUID
    name: str
    price: Decimal
    features: List[Feature] = []
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str]
    price: Optional[Decimal]


class PaginatedSubscriptionPlanResponse(BaseModel):
    items: List[SubscriptionPlanDetails]
    total: int
    page: int
    page_size: int
    pages: int
