from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class SubscriptionPlanFeatureCreate(BaseModel):
    name: str
    description: str
    plan_id: Optional[UUID]
    enabled: Optional[bool]


class SubscriptionPlanFeatureDetails(BaseModel):
    id: UUID
    name: str
    description: str
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class SubscriptionPlanFeatureOut(BaseModel):
    id: UUID
    name: str
    description: str
    enabled: bool

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class FeatureAssignRequest(BaseModel):
    feature_id: UUID
    enabled: bool


class SubscriptionPlanFeatureUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    plan_id: Optional[UUID] = None
    enabled: Optional[bool] = None


class PaginatedSubscriptionPlanFeatureResponse(BaseModel):
    items: List[SubscriptionPlanFeatureDetails]
    total: int
    page: int
    page_size: int
    pages: int
