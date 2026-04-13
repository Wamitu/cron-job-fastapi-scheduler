from typing import Any, Dict, List, Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import Enum

from schemas.fund_project_schema import FundProjectDetails
from schemas.member_schema import MemberDetails
from schemas.parish_schema import ParishDetails
from schemas.sacrament_record_schema import SacramentRecordDetails
from schemas.user_schema import UserDetails


class CollectionType(str, Enum):
    donation = "donation"
    offering = "offering"
    tithe = "tithe"
    thanksgiving = "thanksgiving"
    sacrament = "sacrament"
    project = "project"


class CollectionMethod(str, Enum):
    mpesa = "mpesa"
    cash = "cash"
    card = "card"
    cheque = "cheque"
    bank_transfer = "bank transfer"


class CollectionCreate(BaseModel):
    collection_type: CollectionType
    member_id: Optional[UUID] = None
    parish_id: UUID
    project_id: Optional[UUID] = None
    sacrament_record_id: Optional[UUID] = None
    collection_method: CollectionMethod
    collection_data: Optional[Dict[str, Any]]
    contributor_data: Optional[Dict[str, Any]] = None
    amount: Decimal


class CollectionDetails(BaseModel):
    id: UUID
    collection_type: CollectionType
    member_id: Optional[UUID] = None
    member: Optional[MemberDetails] = None
    parish_id: UUID
    parish: Optional[ParishDetails] = None
    project_id: Optional[UUID] = None
    project: Optional[FundProjectDetails] = None
    sacrament_record_id: Optional[UUID] = None
    sacrament_record: Optional[SacramentRecordDetails] = None
    collection_method: CollectionMethod
    collection_data: Optional[Dict[str, Any]]
    contributor_data: Optional[Dict[str, Any]] = None
    recorded_by: UUID
    recorded_by_user: Optional[UserDetails] = None
    amount: Decimal
    is_archived: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class PaginatedCollectionResponse(BaseModel):
    items: List[CollectionDetails]
    total: int
    page: int
    page_size: int
    pages: int
