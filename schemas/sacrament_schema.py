from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator

from schemas.parish_schema import ParishDetails


class RuleCreate(BaseModel):
    title: str
    description: str


class SacramentCreate(BaseModel):
    parish_id: UUID
    name: str
    rules: List[RuleCreate]
    fee_amount: Decimal


class SacramentDetails(BaseModel):
    id: UUID
    parish_id: UUID
    parish: ParishDetails
    name: str
    rules: List[RuleCreate]
    fee_amount: Decimal
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    @field_validator("rules", mode="before")
    def normalize_rules(cls, v):
        if not v:
            return []
        if isinstance(v, str):
            return [r.strip() for r in v.split(",") if r.strip()]
        return v

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class SacramentUpdate(BaseModel):
    rules: Optional[List[RuleCreate]] = None
    fee_amount: Optional[Decimal] = None


class PaginatedSacramentResponse(BaseModel):
    items: List[SacramentDetails]
    total: int
    page: int
    page_size: int
    pages: int
