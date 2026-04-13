from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import Enum

from schemas.parish_schema import ParishDetails


class MemberGroup(str, Enum):
    men_in_action = "men in action"
    youth = "youth"
    womens_guild = "womens guild"
    elderly = "elderly"


class NextOfKinDetails(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    residence: Optional[str] = None


class MemberData(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    residence: str
    next_of_kin_details: NextOfKinDetails


class MemberCreate(BaseModel):
    parish_id: UUID
    member_data: MemberData
    member_group: MemberGroup


class MemberDetails(BaseModel):
    id: UUID
    parish_id: UUID
    parish: ParishDetails
    member_no: str
    member_data: MemberData
    member_group: MemberGroup
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class MemberUpdate(BaseModel):
    member_data: Optional[MemberData] = None
    member_group: Optional[MemberGroup] = None


class PaginatedMemberResponse(BaseModel):
    items: List[MemberDetails]
    total: int
    page: int
    page_size: int
    pages: int
