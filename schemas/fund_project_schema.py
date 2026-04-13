from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import List
from enum import Enum
from schemas.parish_schema import ParishDetails


class FundProjectStatus(str, Enum):
    active = "active"
    completed = "completed"
    inactive = "inactive"


class FundProjectCreate(BaseModel):
    parish_id: UUID
    name: str
    description: Optional[str] = None
    target_amount: Decimal
    status: FundProjectStatus


class FundProjectDetails(BaseModel):
    id: UUID
    parish_id: UUID
    parish: Optional[ParishDetails]
    name: str
    description: Optional[str] = None
    target_amount: Decimal
    current_amount: Decimal
    account_suffix: str
    status: FundProjectStatus
    is_archived: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class FundProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_amount: Optional[Decimal] = None
    status: Optional[FundProjectStatus] = None


class PaginatedFundProjectResponse(BaseModel):
    items: List[FundProjectDetails]
    total: int
    page: int
    page_size: int
    pages: int
