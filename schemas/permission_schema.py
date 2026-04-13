from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from schemas.user_schema import UserDetails


class PermissionAssign(BaseModel):
    permission_name: str


class PermissionDetails(BaseModel):
    id: UUID
    permission_name: str
    granted_at: datetime
    granted_by: UUID
    granted_by_user: Optional[UserDetails] = None


class UserPermissionDetails(BaseModel):
    id: UUID
    user_id: UUID
    user: Optional[UserDetails]
    permission_id: UUID
    permission: Optional[PermissionDetails]
