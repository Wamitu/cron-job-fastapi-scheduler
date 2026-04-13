from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, StringConstraints, validator


class ParishDataCreate(BaseModel):
    parish_name: str
    contact_email: str
    contact_phone: str


class ParishData(BaseModel):
    parish_name: str
    contact_email: str
    contact_phone: str
    parish_slug: str


class ParishCreate(BaseModel):
    diocese_id: UUID
    parish_data: ParishDataCreate
    member_number_prefix: Optional[
        Annotated[str, StringConstraints(pattern="^[A-Za-z]{3}$")]
    ] = None
    member_number_suffix: Optional[
        Annotated[str, StringConstraints(pattern="^[0-9]{3}$")]
    ] = None
    parish_settings: Optional[dict] = None

    @validator("member_number_prefix")
    def upper_prefix(cls, v):
        return v.upper() if v else v


class ParishDetails(BaseModel):
    id: UUID
    diocese_id: UUID
    parish_data: ParishData
    member_number_prefix: str
    member_number_suffix: str
    parish_settings: Optional[dict] = None
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class ParishUpdate(BaseModel):
    parish_data: Optional[Dict[str, Any]] = None
    member_number_prefix: Optional[
        Annotated[str, StringConstraints(pattern="^[A-Za-z]{3}$")]
    ] = None
    member_number_suffix: Optional[
        Annotated[str, StringConstraints(pattern="^[0-9]{3}$")]
    ] = None

    @validator("member_number_prefix")
    def upper_prefix(cls, v):
        return v.upper() if v else v


class PaginatedParishResponse(BaseModel):
    items: List[ParishDetails]
    total: int
    page: int
    page_size: int
    pages: int
