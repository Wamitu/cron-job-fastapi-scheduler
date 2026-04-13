from fastapi import HTTPException
from sqlalchemy.orm import Session
from db.models.subscription_plan import SubscriptionPlan
from db.models.parish_subscription import (
    ParishSubscription,
    ParishSubscriptionChange,
)
from sqlalchemy.orm import joinedload
from uuid import UUID
from datetime import datetime, timedelta, timezone
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from db.models.user import User
from log_config import logger
from dateutil.relativedelta import relativedelta

from schemas.parish_subscription_schema import ParishSubscriptionChangeRequest


def handle_subscription_change(
    subscription_id: UUID,
    data: ParishSubscriptionChangeRequest,
    db: Session,
    current_user: User,
    change_type: str,  # "upgrade" or "downgrade"
):
    logger.info(f"Scheduling {change_type} subscription plan change...")

    now = datetime.now(timezone.utc)

    # Support either a User object or a user ID (UUID/str) being passed in
    user_id = getattr(current_user, "id", None) or current_user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    subscription = (
        db.query(ParishSubscription)
        .options(
            joinedload(ParishSubscription.subscription)
            .joinedload(SubscriptionPlan.features_pivot)
            .joinedload(SubscriptionPlanFeaturePivot.feature),
            joinedload(ParishSubscription.payments),
        )
        .filter(ParishSubscription.id == subscription_id)
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found!")

    current_plan = db.get(SubscriptionPlan, subscription.subscription_plan_id)
    new_plan = db.get(SubscriptionPlan, data.new_plan_id)

    if not new_plan:
        raise HTTPException(status_code=404, detail="New plan not found!")

    if current_plan.id == new_plan.id:
        raise HTTPException(status_code=400, detail="You are already on this plan!")

    if subscription.last_plan_change_at:
        days_since_change = (now - subscription.last_plan_change_at).days
        if days_since_change < 30:
            raise HTTPException(
                status_code=400,
                detail="You can only change plans once every 30 days!",
            )

    if change_type == "upgrade" and new_plan.price <= current_plan.price:
        raise HTTPException(
            status_code=400, detail="Upgrade requires selecting a higher-priced plan!"
        )

    if change_type == "downgrade" and new_plan.price >= current_plan.price:
        raise HTTPException(
            status_code=400, detail="Downgrade requires selecting a lower-priced plan!"
        )

    # 🔁 Schedule change at end of current billing period (fallback to now if missing)
    scheduled_start = (
        subscription.end_date + timedelta(days=1)
        if subscription.end_date
        else now
    )
    scheduled_end = scheduled_start + relativedelta(months=1)

    # 📌 Store change in ParishSubscriptionChange table
    plan_change = ParishSubscriptionChange(
        parish_id=subscription.parish_id,
        parish_subscription_id=subscription.id,
        current_plan_id=current_plan.id,
        next_plan_id=new_plan.id,
        change_date=now,
        scheduled_start_date=scheduled_start,
        scheduled_end_date=scheduled_end,
        is_applied=False,
    )
    db.add(plan_change)

    # Prepare subscription to apply change later
    subscription.next_subscription_plan_id = new_plan.id
    subscription.last_plan_change_at = now
    db.commit()
    db.refresh(subscription)

    logger.info(
        f"{change_type.title()} to {new_plan.name} scheduled for {scheduled_start}"
    )
    return subscription
