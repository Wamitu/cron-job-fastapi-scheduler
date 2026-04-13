from enum import Enum
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date, datetime

from schemas.parish_schema import ParishDetails
from schemas.subscription_plan_schema import SubscriptionPlanDetails
from schemas.user_schema import UserDetails


class SubscriptionStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    expired = "expired"
    grace_period = "grace_period"
    cancelled = "cancelled"


class ParishSubscriptionCreate(BaseModel):
    parish_id: UUID
    subscription_plan_id: UUID


class ParishOnBoardingSubscriptionCreate(BaseModel):
    subscription_plan_id: UUID


class ParishSubscriptionDetails(BaseModel):
    id: UUID
    parish_id: UUID
    parish: Optional[ParishDetails]
    subscription_plan_id: UUID
    subscription: Optional[SubscriptionPlanDetails]
    start_date: datetime
    end_date: datetime
    last_renewed_at: Optional[datetime]
    status: SubscriptionStatus
    next_subscription_plan_id: Optional[UUID]
    next_plan: Optional[SubscriptionPlanDetails]
    last_plan_change_at: Optional[datetime]
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ParishSubscriptionUpdate(BaseModel):
    parish_id: Optional[UUID] = None
    subscription_plan_id: Optional[UUID] = None
    status: Optional[SubscriptionStatus] = None


class ParishSubscriptionChangeDetails(BaseModel):
    id: UUID
    parish_subscription_id: UUID
    current_plan_id: UUID
    current_plan: Optional[SubscriptionPlanDetails]
    next_plan_id: UUID
    next_plan: Optional[SubscriptionPlanDetails]
    change_date: datetime
    scheduled_start_date: Optional[datetime]
    scheduled_end_date: Optional[datetime]
    is_applied: bool

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPaymentCreate(BaseModel):
    parish_subscription_id: Optional[UUID] = None
    amount: float
    channel: str
    reference: Optional[str] = None
    paid_at: datetime


class ParishSubscriptionChangeRequest(BaseModel):
    new_plan_id: UUID


class SubscriptionPaymentDetails(BaseModel):
    id: UUID
    parish_subscription_id: Optional[UUID]
    parish_subscription: Optional[ParishSubscriptionDetails]
    amount: float
    channel: str
    reference: Optional[str] = None
    paid_at: datetime
    recorded_by: Optional[UUID]
    recorded_by_user: Optional[UserDetails]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedParishSubscriptionResponse(BaseModel):
    items: List[ParishSubscriptionDetails]
    total: int
    page: int
    page_size: int
    pages: int


class PaginatedSubscriptionPaymentResponse(BaseModel):
    items: List[SubscriptionPaymentDetails]
    total: int
    page: int
    page_size: int
    pages: int
