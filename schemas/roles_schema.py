from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RoleCreate(BaseModel):
    title: str
    description: Optional[str]


class RoleDetails(BaseModel):
    id: UUID
    title: str
    description: str
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class RoleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class PaginatedRoleResponse(BaseModel):
    items: List[RoleDetails]
    total: int
    page: int
    page_size: int
    pages: int
