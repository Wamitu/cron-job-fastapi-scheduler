from pydantic import EmailStr, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from schemas.parish_schema import ParishDetails
from schemas.roles_schema import RoleDetails
from schemas.user_schema import UserDetails


class InviteUserRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str = Field(
        ...,
        description="Phone number must be provided and follow the format 2547XXXXXXXX",
    )
    role_id: UUID
    parish_id: UUID


class OnBoardParishInviteUserRequest(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]
    phone: Optional[str] = Field(
        None,
        description="Phone number must be provided and follow the format 2547XXXXXXXX",
    )


class UserRegisterFromInviteRequest(BaseModel):
    token: str
    password: str

    class Config:
        arbitrary_types_allowed = True


class InvitedUserDetails(BaseModel):
    id: UUID
    parish_id: Optional[UUID] = None
    parish: Optional[ParishDetails] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role_id: Optional[UUID] = None
    role: Optional[RoleDetails] = None
    invited_by: Optional[UUID] = None
    invited_by_user: Optional[UserDetails] = None
    is_archived: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class PaginatedInvitedUserResponse(BaseModel):
    items: List[InvitedUserDetails]
    total: int
    page: int
    page_size: int
    pages: int
