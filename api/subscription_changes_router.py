from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.serializers import serialize_subscription_plan
from db.models.user import User
from db.session import get_db
from db.models.parish_subscription import (
    ParishSubscriptionChange,
)
from sqlalchemy.exc import SQLAlchemyError
from schemas.parish_subscription_schema import (
    ParishSubscriptionChangeDetails,
)
from log_config import logger
from services.auth_service import get_current_user
from services.user_service import get_user_details

router = APIRouter()


# view past subscriptions history
@router.get(
    "/subscription-changes", response_model=List[ParishSubscriptionChangeDetails]
)
def get_subscription_changes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to fetch parish subscription changes...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        changes = db.query(ParishSubscriptionChange).all()

        return [
            ParishSubscriptionChangeDetails(
                id=change.id,
                parish_subscription_id=change.parish_subscription_id,
                current_plan_id=change.current_plan_id,
                next_plan_id=change.next_plan_id,
                change_date=change.change_date,
                scheduled_start_date=(
                    change.scheduled_start_date.date()
                    if change.scheduled_start_date
                    else None
                ),
                scheduled_end_date=(
                    change.scheduled_end_date.date()
                    if change.scheduled_end_date
                    else None
                ),
                current_plan=(
                    serialize_subscription_plan(change.current_plan)
                    if change.current_plan
                    else None
                ),
                next_plan=(
                    serialize_subscription_plan(change.next_plan)
                    if change.next_plan
                    else None
                ),
                is_applied=change.is_applied,
            )
            for change in changes
        ]

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during parish subscription parish subscription changes retrieval!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Database error during parish subscription parish subscription changes retrieval!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during parish subscription parish subscription changes retrieval!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Unexpected error during parish subscription parish subscription changes retrieval!",
        )
