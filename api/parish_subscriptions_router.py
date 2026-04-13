from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from uuid import UUID
from api.serializers import (
    serialize_parish_subscription,
    serialize_parish_subscriptions,
)
from api.serializers import serialize_subscription_plan
from db.models.parish import Parish
from db.models.user import User
from db.session import get_db
from db.models.parish_subscription import (
    ParishSubscription,
    ParishSubscriptionChange,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from dateutil.relativedelta import relativedelta
from db.models.subscription_plan import SubscriptionPlan
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from db.models.parish_subscription import SubscriptionPayment
from schemas.notification_schema import NotificationType
from schemas.parish_subscription_schema import (
    PaginatedSubscriptionPaymentResponse,
    ParishSubscriptionChangeDetails,
    ParishSubscriptionCreate,
    ParishSubscriptionDetails,
    ParishSubscriptionChangeRequest,
    SubscriptionPaymentCreate,
    SubscriptionPaymentDetails,
)
from schemas.parish_subscription_schema import SubscriptionStatus
from log_config import logger
from services.auth_service import get_current_user
from services.notification_service import create_notification
from services.user_service import get_user_details
from utils.receipt_no_generator import generate_receipt_number
from utils.subscription import handle_subscription_change


router = APIRouter()


# get data count
@router.get(
    "/count",
    summary="Fetch all count of parish subscriptions records (optionally filtered by parish)",
)
async def count_parish_subscription_records(
    db: Session = Depends(get_db),
):
    try:
        query = db.query(ParishSubscription)
        total_count = query.count()
        logger.info("200 | Parish subscription count fetched successfully!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise


# retrieve all parish subscriptions
@router.get(
    "/all",
    summary="Fetch all parish subscription records (optionally filtered by parish)",
)
async def retrieve_all_parish_subscriptions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    parish_id: Optional[str] = Query(None),
    is_archived: Optional[bool] = None,
    status: Optional[SubscriptionStatus] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
):
    offset = (page - 1) * page_size

    try:
        query = db.query(ParishSubscription).options(
            joinedload(ParishSubscription.parish),
            joinedload(ParishSubscription.subscription),
            joinedload(ParishSubscription.next_plan),
        )

        if parish_id:
            query = query.filter(ParishSubscription.parish_id == parish_id)
        if is_archived is None:
            query = query.filter(ParishSubscription.is_archived == False)
        else:
            query = query.filter(ParishSubscription.is_archived == is_archived)
        if status:
            query = query.filter(ParishSubscription.status == status)
        allowed_sort_fields = {
            "start_date",
            "end_date",
            "created_at",
            "status",
        }

        if sort_by in allowed_sort_fields:
            column = getattr(ParishSubscription, sort_by)
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            query = query.order_by(ParishSubscription.created_at.desc())

        total_count = query.count()
        subscriptions = query.offset(offset).limit(page_size).all()

        serialized_subscriptions = serialize_parish_subscriptions(subscriptions)

        logger.info(
            f"Retrieved {len(subscriptions)} parish subscriptions (Page {page})"
        )

        return {
            "items": serialized_subscriptions,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "pages": (total_count + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except Exception as e:
        logger.error(f"Error retrieving parish subscriptions: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch parish subscriptions."
        )


# create parish subscription
@router.post(
    "/create",
    response_model=ParishSubscriptionDetails,
    summary="Create parish subscription for parish",
)
def create_parish_subscription(
    data: ParishSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        # check for active/existing subscription
        existing_subscription = (
            db.query(ParishSubscription)
            .filter(
                ParishSubscription.status.in_(["grace_period", "active", "expired"]),
            )
            .first()
        )

        if existing_subscription:
            raise HTTPException(
                status_code=400,
                detail="Parish already has an active or pending subscription.",
            )

        # get subscription plan
        plan = db.get(SubscriptionPlan, data.subscription_plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        now = datetime.utcnow()
        end_date = now + relativedelta(months=1)

        # determine initial status without payment flags
        previous_subscriptions = (
            db.query(ParishSubscription)
            .filter(ParishSubscription.parish_id == data.parish_id)
            .count()
        )
        if previous_subscriptions == 0:
            status = SubscriptionStatus.grace_period
        else:
            status = SubscriptionStatus.inactive

        # Create new subscription
        subscription = ParishSubscription(
            parish_id=data.parish_id,
            subscription_plan_id=data.subscription_plan_id,
            start_date=now,
            end_date=end_date,
            status=status,
        )

        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Parish subscription record created successfully!",
        )

        logger.info(
            "201 | Parish subscription record created and notification sent successfully!"
        )

        # Load the subscription with relationships for proper serialization
        subscription_with_relations = (
            db.query(ParishSubscription)
            .options(
                joinedload(ParishSubscription.parish),
                joinedload(ParishSubscription.subscription)
                .joinedload(SubscriptionPlan.features_pivot)
                .joinedload(SubscriptionPlanFeaturePivot.feature),
                joinedload(ParishSubscription.next_plan)
                .joinedload(SubscriptionPlan.features_pivot)
                .joinedload(SubscriptionPlanFeaturePivot.feature),
            )
            .filter(ParishSubscription.id == subscription.id)
            .first()
        )

        return subscription_with_relations

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during parish subscription creation!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during parish subscription creation!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# get parish subscription details
@router.get(
    "/details/{parish_subscription_id}",
    summary="Get parish subscription details",
)
def get_parish_subscription(
    parish_subscription_id: UUID,
    db: Session = Depends(get_db),
):
    logger.info("Fetching parish subscription details")

    subscription = (
        db.query(ParishSubscription)
        .options(
            joinedload(ParishSubscription.parish),
            joinedload(ParishSubscription.subscription)
            .joinedload(SubscriptionPlan.features_pivot)
            .joinedload(SubscriptionPlanFeaturePivot.feature),
            joinedload(ParishSubscription.next_plan)
            .joinedload(SubscriptionPlan.features_pivot)
            .joinedload(SubscriptionPlanFeaturePivot.feature),
        )
        .filter(ParishSubscription.id == parish_subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return serialize_parish_subscription(subscription)


# upgrade subscriptopn plan
@router.post(
    "/{subscription_id}/upgrade-plan",
    response_model=ParishSubscriptionDetails,
)
def upgrade_subscription_plan(
    subscription_id: UUID,
    data: ParishSubscriptionChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        handle_subscription_change(
            subscription_id=subscription_id,
            data=data,
            db=db,
            current_user=current_user,
            change_type="upgrade",
        )

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Parish subscription record upgraded successfully!",
        )

        logger.info(
            "201 | Parish subscription record upgraded and notification sent successfully!"
        )

        updated_sub = (
            db.query(ParishSubscription)
            .filter(ParishSubscription.id == subscription_id)
            .first()
        )

        if not updated_sub:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return updated_sub

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during parish subscription plan upgrade!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during parish subscription plan upgrade!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# downgrade subscription plan
@router.post(
    "/{subscription_id}/downgrade-plan",
    response_model=ParishSubscriptionDetails,
)
def downgrade_subscription_plan(
    subscription_id: UUID,
    data: ParishSubscriptionChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        handle_subscription_change(
            subscription_id=subscription_id,
            data=data,
            db=db,
            current_user=current_user,
            change_type="downgrade",
        )

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Parish subscription record downgraded successfully!",
        )

        logger.info(
            "201 | Parish subscription record downgraded and notification sent successfully!"
        )

        updated_sub = (
            db.query(ParishSubscription)
            .filter(ParishSubscription.id == subscription_id)
            .first()
        )

        if not updated_sub:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return updated_sub

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during parish subscription plan downgrade!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during parish subscription plan downgrade!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# cancel parish subscription
@router.post(
    "/{subscription_id}/cancel",
    response_model=ParishSubscriptionDetails,
)
def cancel_subscription(
    subscription_id: UUID,
    cancel_completely: bool = Query(
        False,
        description="If true, cancels subscription immediately to inactive; if false, cancels to cancelled and can be reactivated",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        subscription = (
            db.query(ParishSubscription)
            .options(
                joinedload(ParishSubscription.parish),
                joinedload(ParishSubscription.subscription)
                .joinedload(SubscriptionPlan.features_pivot)
                .joinedload(SubscriptionPlanFeaturePivot.feature),
                joinedload(ParishSubscription.next_plan)
                .joinedload(SubscriptionPlan.features_pivot)
                .joinedload(SubscriptionPlanFeaturePivot.feature),
            )
            .filter(ParishSubscription.id == subscription_id)
            .first()
        )

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found!")

        if subscription.status in [
            SubscriptionStatus.cancelled,
            SubscriptionStatus.inactive,
        ]:
            raise HTTPException(
                status_code=400, detail="Subscription already cancelled or inactive."
            )

        # Only active subscriptions can be fully cancelled
        if cancel_completely and subscription.status != SubscriptionStatus.active:
            raise HTTPException(
                status_code=400,
                detail="Only active subscriptions can be cancelled completely (inactive).",
            )

        # Apply cancellation
        if cancel_completely:
            subscription.status = SubscriptionStatus.inactive
        else:
            # Can cancel normally even if in grace_period
            subscription.status = SubscriptionStatus.cancelled

        db.commit()
        db.refresh(subscription)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Parish subscription cancelled successfully!).",
        )

        return subscription

    except HTTPException as e:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="A database error occurred!")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# reactivate subscription
@router.post(
    "/{subscription_id}/reactivate",
    response_model=ParishSubscriptionDetails,
)
def reactivate_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        subscription = (
            db.query(ParishSubscription)
            .options(
                joinedload(ParishSubscription.parish),
                joinedload(ParishSubscription.subscription)
                .joinedload(SubscriptionPlan.features_pivot)
                .joinedload(SubscriptionPlanFeaturePivot.feature),
                joinedload(ParishSubscription.next_plan)
                .joinedload(SubscriptionPlan.features_pivot)
                .joinedload(SubscriptionPlanFeaturePivot.feature),
            )
            .filter(ParishSubscription.id == subscription_id)
            .first()
        )

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found!")

        if subscription.status != SubscriptionStatus.cancelled:
            raise HTTPException(
                status_code=400,
                detail="Only cancelled subscriptions can be reactivated.",
            )

        if subscription.end_date and subscription.end_date < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail="Cannot reactivate — subscription already expired.",
            )

        # Reactivate
        subscription.status = SubscriptionStatus.active
        db.commit()
        db.refresh(subscription)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message="Parish subscription reactivated successfully!",
        )

        logger.info("201 | Parish subscription reactivated successfully!")

        return subscription

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during parish subscription reactivation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")
    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during parish subscription reactivation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


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


# parish sub overview
@router.get(
    "/overview_info",
    summary="Get info on parish subscription, prospect and recent payments",
)
async def get_parish_subscription_overview(
    parish_subscription_id: UUID = Query(..., description="Parish subscription ID"),
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info("Retrieving parish subscription overview info...")
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    role_title = user.role.title if hasattr(user.role, "title") else None

    # model relationship connector
    subscription = (
        db.query(ParishSubscription)
        .options(
            joinedload(ParishSubscription.parish),
            joinedload(ParishSubscription.subscription),
            joinedload(ParishSubscription.next_plan),
        )
        .filter(ParishSubscription.id == parish_subscription_id)
        .first()
    )

    if not subscription:
        logger.warning("404 | Parish subscription not found!")
        raise HTTPException(status_code=404, detail="Parish subscription not found")

    # 🔒 Restrict access for Priests based on parish_id
    if role_title == "Priest":
        if not parish_subscription_id:
            raise HTTPException(
                status_code=403,
                detail="Priests must specify a parish_subscription_id to view overview data.",
            )
        if subscription.parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to view data from another parish.",
            )

    # serialize parish subscription
    serialized_subscription = serialize_parish_subscriptions([subscription])[0]

    # prospect logic
    if subscription.status.name.lower() != "active":
        expected_amount = 0
    else:
        if not subscription.subscription.price:
            raise HTTPException(
                status_code=400,
                detail="Subscription plan or amount not set for this parish subscription",
            )
        expected_amount = subscription.subscription.price

    # 5 most recent payments for this parish subscription
    payments_query = (
        db.query(SubscriptionPayment)
        .filter(SubscriptionPayment.parish_subscription_id == parish_subscription_id)
        .options(
            joinedload(SubscriptionPayment.parish_subscription).joinedload(
                ParishSubscription.parish
            )
        )
        .order_by(SubscriptionPayment.created_at.desc())
        .limit(5)
    )

    payments = payments_query.all()

    serialized_payments = []
    for payment in payments:
        result_data = payment.__dict__.copy()
        result_data["parish"] = payment.parish_subscription.parish
        serialized = SubscriptionPaymentDetails(**result_data)
        serialized_payments.append(serialized)

    return {
        "parish_subscription_overview": {
            "parish_subscription_info": serialized_subscription,
            "prospect": expected_amount,
            "most_recent_payments": serialized_payments,
        }
    }
