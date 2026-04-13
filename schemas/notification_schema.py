from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import Enum


class NotificationType(str, Enum):
    reminder = "reminder"
    info = "info"
    warning = "warning"


# Create schema
class NotificationCreate(BaseModel):
    user_id: UUID
    parish_id: UUID
    notification_type: NotificationType
    message: str


class NotificationDetails(BaseModel):
    id: UUID
    user_id: UUID
    parish_id: Optional[UUID] = None
    notification_type: NotificationType
    message: str
    sent_at: datetime
    read_at: Optional[datetime]
    is_archived: bool

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class NotificationUpdate(BaseModel):
    read_at: Optional[datetime] = None
    is_archived: Optional[bool] = None
    message: Optional[str] = None


# Paginated response schema
class PaginatedNotificationResponse(BaseModel):
    items: List[NotificationDetails]
    total: int
    page: int
    page_size: int
    pages: int
