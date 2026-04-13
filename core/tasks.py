import asyncio
import db.models
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db.session import SessionLocal
from schemas.parish_subscription_schema import SubscriptionStatus
from log_config import logger
from core.celery_app import celery_app
from db.models.parish import Parish
from db.models.subscription_plan import SubscriptionPlan
from db.models.parish_subscription import ParishSubscription
from db.models.user import User
from db.models.diocese import Diocese
from utils.bulk_sms_client import send_bulk_sms


@celery_app.task
def update_subscription_statuses():
    """
    Cron-driven Celery task to update subscription statuses:
    - Active → Grace Period (if end_date passed)
    - Grace Period → Expired (3 days after end_date)
    - Expired → Inactive (30 days after end_date)
    Note: Uses end_date-based thresholds; does not rely on non-existent timestamp columns.
    """

    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        subscriptions = db.query(ParishSubscription).all()
        logger.info(f"Running status update for {len(subscriptions)} subscriptions")
        for sub in subscriptions:
            try:
                # Coerce status strings to Enum to avoid DB errors on commit
                if isinstance(sub.status, str):
                    status_map = {
                        "active": SubscriptionStatus.active,
                        "grace_period": SubscriptionStatus.grace_period,
                        "expired": SubscriptionStatus.expired,
                        "inactive": SubscriptionStatus.inactive,
                        "cancelled": SubscriptionStatus.cancelled,
                    }
                    lowered = sub.status.lower()
                    if lowered in status_map:
                        sub.status = status_map[lowered]
                    else:
                        logger.warning(
                            f"Subscription {getattr(sub, 'id', None)} has unknown status '{sub.status}', skipping."
                        )
                        continue

                # Normalize end_date to timezone-aware for safe comparisons
                end_date = sub.end_date
                if not end_date:
                    continue
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)

                changed = False

                # ACTIVE → GRACE PERIOD (end_date passed)
                if sub.status == SubscriptionStatus.active and end_date < now:
                    sub.status = SubscriptionStatus.grace_period
                    changed = True
                    logger.info(
                        f"Subscription {sub.id} moved to GRACE PERIOD (end_date {end_date.isoformat()})."
                    )

                # GRACE PERIOD → EXPIRED (3 days after end_date)
                elif sub.status == SubscriptionStatus.grace_period:
                    days_since_end = (now - end_date).days
                    if days_since_end >= 3:
                        sub.status = SubscriptionStatus.expired
                        changed = True
                        logger.info(
                            f"Subscription {sub.id} moved to EXPIRED ({days_since_end} days after end)."
                        )

                # EXPIRED → INACTIVE (30 days after end_date)
                elif sub.status == SubscriptionStatus.expired:
                    days_since_end = (now - end_date).days
                    if days_since_end >= 30:
                        sub.status = SubscriptionStatus.inactive
                        changed = True
                        logger.info(
                            f"Subscription {sub.id} moved to INACTIVE ({days_since_end} days after end)."
                        )

                if changed:
                    logger.info(f"Updating sub {sub.id}: status -> {sub.status}")
                    db.flush()

            except Exception as sub_err:
                logger.error(
                    f"Error processing subscription {getattr(sub, 'id', None)}: {sub_err}",
                    exc_info=True,
                )
                logger.exception(
                    f"Row failed in status update: id={getattr(sub, 'id', None)}, "
                    f"status={sub.status}, end_date={sub.end_date}, plan_id={getattr(sub, 'subscription_plan_id', None)}, "
                    f"parish_id={getattr(sub, 'parish_id', None)}"
                )

        # after
        try:
            db.commit()
            logger.info("Subscription statuses updated successfully.")
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Commit failed during subscription status update!")

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error during subscription status update!")

    finally:
        db.close()


@celery_app.task
def send_bulk_sms_task(
    message: str, recipients: list[str], masked_number: str = None, telco: str = None
):
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        send_bulk_sms(message, recipients, masked_number, telco)
    )
    return result
