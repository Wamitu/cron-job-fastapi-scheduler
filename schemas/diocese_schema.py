from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, StringConstraints, validator

from schemas.parish_schema import ParishDetails


class DioceseCreate(BaseModel):
    name: str
    description: str


class DioceseDetails(BaseModel):
    id: UUID
    parishes: List[ParishDetails] = []
    name: str
    description: str
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class DioceseUpdate(BaseModel):
    name: str
    description: str


class PaginatedDioceseResponse(BaseModel):
    items: List[DioceseDetails]
    total: int
    page: int
    page_size: int
    pages: int
