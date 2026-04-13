from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from schemas.parish_schema import ParishDetails
from schemas.user_schema import UserDetails


class AttendanceCreate(BaseModel):
    parish_id: UUID
    event_title: str
    event_type: str
    event_description: str
    event_date: datetime
    data: Dict[str, Any]


class AttendanceDetails(BaseModel):
    id: UUID
    parish_id: UUID
    parish: ParishDetails
    event_title: str
    event_type: str
    event_description: str
    event_date: datetime
    marked_by: UUID
    marked_by_user: UserDetails
    data: Dict[str, Any]
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class AttendanceUpdate(BaseModel):
    event_title: Optional[str] = None
    event_type: Optional[str] = None
    event_description: Optional[str] = None
    event_date: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None


class PaginatedAttendanceResponse(BaseModel):
    items: List[AttendanceDetails]
    total: int
    page: int
    page_size: int
    pages: int
