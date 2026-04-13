from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from schemas.parish_schema import ParishDetails
from schemas.sacrament_record_schema import SacramentRecordDetails
from schemas.user_schema import UserDetails


class CertificateCreate(BaseModel):
    parish_id: UUID
    sacrament_record_id: UUID
    certificate_for: str


class CertificateDetails(BaseModel):
    id: UUID
    parish_id: UUID
    parish: Optional[ParishDetails] = None
    sacrament_record_id: UUID
    sacrament_record: Optional[SacramentRecordDetails] = None
    certificate_no: str
    certificate_for: str
    generated_by: UUID
    generated_by_user: Optional[UserDetails] = None
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class CertificateUpdate(BaseModel):
    certificate_for: Optional[str]


class PaginatedCertificateResponse(BaseModel):
    items: List[CertificateDetails]
    total: int
    page: int
    page_size: int
    pages: int
