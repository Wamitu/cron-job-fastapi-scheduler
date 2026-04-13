from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, logger
from services.user_service import get_user_details
from sqlalchemy.orm import Session
from uuid import UUID
from db.models.parish import Parish
from db.models.user import User
from db.session import get_db
from db.models.notification import Notification as NotificationModel
from schemas.notification_schema import (
    NotificationCreate,
    NotificationUpdate,
    NotificationDetails,
    PaginatedNotificationResponse,
)
from services.auth_service import get_current_user

router = APIRouter()


# all notifications
@router.get(
    "/all",
    response_model=PaginatedNotificationResponse,
    summary="Fetch all notification records (optionally filtered by parish)",
)
def get_all_notifications(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    is_archived: Optional[bool] = None,
    user_id: Optional[UUID] = None,
    parish_id: Optional[UUID] = Query(None),
):
    query = db.query(NotificationModel)

    # archive filter
    if is_archived is not None:
        query = query.filter(NotificationModel.is_archived == is_archived)

    # user filter
    if user_id:
        query = query.filter(NotificationModel.user_id == user_id)

    # parish filter
    if parish_id:
        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")
        query = query.filter(NotificationModel.parish_id == parish_id)

    total = query.count()
    pages = (total + page_size - 1) // page_size

    notifications = (
        query.order_by(NotificationModel.sent_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedNotificationResponse(
        items=notifications,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# create notification
@router.post(
    "/create",
    response_model=NotificationDetails,
    summary="Create a notification",
)
def create_notification(
    notification: NotificationCreate,
    db: Session = Depends(get_db),
):
    db_notification = NotificationModel(
        user_id=notification.user_id,
        parish_id=notification.parish_id,
        notification_type=notification.notification_type,
        data=notification.data,
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification


# notification details
@router.get(
    "/{notification_id}",
    response_model=NotificationDetails,
    summary="Get a notification by ID",
)
def get_notification(notification_id: UUID, db: Session = Depends(get_db)):
    db_notification = (
        db.query(NotificationModel)
        .filter(NotificationModel.id == notification_id)
        .first()
    )
    if not db_notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return db_notification


# update notification
@router.put(
    "/{notification_id}",
    response_model=NotificationDetails,
    summary="Update a notification (mark as read, archive, or update data)",
)
def update_notification(
    notification_id: UUID,
    update_data: NotificationUpdate,
    db: Session = Depends(get_db),
):
    db_notification = (
        db.query(NotificationModel)
        .filter(NotificationModel.id == notification_id)
        .first()
    )
    if not db_notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(db_notification, field, value)

    db.commit()
    db.refresh(db_notification)
    return db_notification


# mark notification as read
@router.post("/{notification_id}/mark-as-read")
def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")
    # get notification
    notification = (
        db.query(NotificationModel)
        .filter(
            NotificationModel.id == notification_id,
            NotificationModel.user_id == user.id,
        )
        .first()
    )

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Mark as read
    if not notification.read_at:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)

    return {
        "message": "Notification marked as read",
        "notification_id": str(notification.id),
        "read_at": notification.read_at,
    }
