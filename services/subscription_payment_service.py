from db.models.parish_subscription import SubscriptionPayment
from db.models.parish_subscription import ParishSubscription, SubscriptionStatus
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from decimal import Decimal
from datetime import datetime
from uuid import uuid4
from db.models.role import Role
from db.models.user import User
from log_config import logger


def check_parish_subscription_payments_exist(db: Session) -> bool:
    return db.query(SubscriptionPayment.id).first() is not None


def create_subscription_payments_for_active_subscriptions(db: Session):
    """
    Seed subscription payments for ACTIVE parish subscriptions.
    Payments are recorded by the first available SysAdmin user.
    """
    try:
        # Find a SysAdmin user
        sysadmin_role = db.query(Role).filter(Role.title == "SysAdmin").first()

        if not sysadmin_role:
            logger.warning("SysAdmin role not found!")
            return None

        # Step 2: Get a user with that role_id
        sysadmin_user = db.query(User).filter(User.role_id == sysadmin_role.id).first()

        if not sysadmin_user:
            logger.warning("No user with SysAdmin role found!")

        active_subscriptions = (
            db.query(ParishSubscription)
            .filter(ParishSubscription.status == SubscriptionStatus.active)
            .all()
        )

        if not active_subscriptions:
            logger.info("No ACTIVE parish subscriptions found for seeding payments!")
            return

        created_count = 0

        for sub in active_subscriptions:
            existing_payment = (
                db.query(SubscriptionPayment)
                .filter_by(parish_subscription_id=sub.id)
                .first()
            )
            if existing_payment:
                continue

            if not sub.subscription:
                logger.warning(f"Subscription has no linked plan! Skipping...")
                continue

            payment = SubscriptionPayment(
                parish_subscription_id=sub.id,
                amount=(
                    sub.subscription.price
                    if sub.subscription.price
                    else Decimal("0.00")
                ),
                channel="mpesa",
                reference=f"TX-{uuid4().hex[:10]}",
                paid_at=datetime.utcnow(),
                recorded_by=sysadmin_user.id,
                is_archived=False,
            )

            db.add(payment)
            created_count += 1

        db.commit()
        logger.info(f"Subscription payments seeded successfully!")

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Error while seeding subscription payments!: %s", str(e))
        raise
