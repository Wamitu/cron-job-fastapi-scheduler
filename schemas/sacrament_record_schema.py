from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from schemas.parish_schema import ParishDetails
from schemas.sacrament_schema import SacramentDetails
from schemas.user_schema import UserDetails


class SacramentRecordCreate(BaseModel):
    parish_id: UUID
    sacrament_id: UUID
    data: Optional[Dict[str, Any]] = None
    generate_certificate: bool = False


class SacramentRecordDetails(BaseModel):
    id: UUID
    reference_no: str
    parish_id: UUID
    parish: ParishDetails
    sacrament_id: UUID
    sacrament: SacramentDetails
    data: Optional[Dict[str, Any]] = None
    generate_certificate: bool
    fee_amount: Decimal
    outstanding_balance: Decimal
    is_settled: bool
    created_by: UUID
    created_by_user: UserDetails
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class SacramentRecordUpdate(BaseModel):
    sacrament_id: Optional[UUID] = None
    data: Optional[Dict[str, Any]] = None


class PaginatedSacramentRecordResponse(BaseModel):
    items: List[SacramentRecordDetails]
    total: int
    page: int
    page_size: int
    pages: int
