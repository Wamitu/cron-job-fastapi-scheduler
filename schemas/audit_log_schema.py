from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from schemas.diocese_schema import DioceseDetails
from schemas.parish_schema import ParishDetails


class AuditLogUserInfo(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class AuditLogDetails(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    user: Optional[AuditLogUserInfo] = None
    diocese_id: Optional[UUID] = None
    diocese: Optional[DioceseDetails] = None
    parish_id: Optional[UUID] = None
    parish: Optional[ParishDetails] = None
    method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[str] = None
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    ip_address: Optional[str] = None
    before_data: Optional[str] = None
    after_data: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class PaginatedAuditLogResponse(BaseModel):
    items: List[AuditLogDetails]
    total: int
    page: int
    page_size: int
    pages: int
