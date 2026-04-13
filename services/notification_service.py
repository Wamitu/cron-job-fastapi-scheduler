from sqlalchemy.orm import Session
from db.models.notification import Notification as NotificationModel, NotificationType
from uuid import UUID


def create_notification(
    db: Session,
    user_id: UUID,
    parish_id: UUID,
    notification_type: NotificationType,
    message: str,
):
    db_notification = NotificationModel(
        user_id=user_id,
        parish_id=parish_id,
        notification_type=notification_type,
        message=message,
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification
