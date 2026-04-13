from uuid import UUID
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from schemas.diocese_schema import DioceseDetails
from schemas.parish_schema import ParishDetails
from schemas.roles_schema import RoleDetails


class UserCreate(BaseModel):
    diocese_id: UUID
    parish_id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str
    password: str
    role_id: UUID
    is_active: bool


class UserCreateForParish(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    password: str


class UserDetails(BaseModel):
    id: UUID
    diocese_id: Optional[UUID]
    diocese: Optional[DioceseDetails]
    parish_id: Optional[UUID]
    parish: Optional[ParishDetails]
    first_name: str
    last_name: str
    email: str
    phone: str
    role_id: UUID
    role: Optional[RoleDetails]
    is_active: bool
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[str] = None


class PaginatedUserResponse(BaseModel):
    items: List[UserDetails]
    total: int
    page: int
    page_size: int
    pages: int


UserDetails.model_rebuild()
