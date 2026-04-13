import logging
import random
from uuid import uuid4
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from log_config import logger
from db.models.parish import Parish
from db.models.parish_subscription import ParishSubscription
from db.models.subscription_plan import SubscriptionPlan
from db.models.parish_subscription import ParishSubscriptionChange
from schemas.parish_subscription_schema import (
    ParishSubscriptionCreate,
    SubscriptionStatus,
)


def check_parish_subscriptions_exist(db: Session) -> bool:
    return db.query(ParishSubscription.id).first() is not None


def create_parish_subscriptions(db: Session):
    try:
        parishes = db.query(Parish).all()
        if not parishes:
            raise HTTPException(
                status_code=404, detail="No parishes found to seed subscriptions!"
            )

        all_plans = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.name.in_(
                    ["starter", "standard", "premium", "professional", "enterprise"]
                )
            )
            .all()
        )

        if not all_plans:
            raise HTTPException(
                status_code=404,
                detail="No valid subscription plans found!",
            )

        created_count = 0
        skipped_count = 0

        plan_lookup = {plan.name: plan for plan in all_plans}
        ordered_plan_names = [
            "starter",
            "standard",
            "premium",
            "professional",
            "enterprise",
        ]
        ordered_plans = [
            plan_lookup[name] for name in ordered_plan_names if name in plan_lookup
        ]

        for i, (parish, plan) in enumerate(zip(parishes[:5], ordered_plans)):
            exists = db.query(ParishSubscription).filter_by(parish_id=parish.id).first()
            if exists:
                skipped_count += 1
                continue

            start_date = datetime.utcnow()
            # end_date = start_date + timedelta(minutes=5)
            end_date = start_date + relativedelta(months=1)

            payload = ParishSubscriptionCreate(
                parish_id=parish.id,
                subscription_plan_id=plan.id,
            )

            status = SubscriptionStatus.active

            new_subscription = ParishSubscription(
                parish_id=payload.parish_id,
                subscription_plan_id=payload.subscription_plan_id,
                start_date=start_date,
                end_date=end_date,
                status=status,
                is_archived=False,
            )

            db.add(new_subscription)
            db.flush()  # Flush to get `new_subscription.id`

            logger.info(
                f"Parish '{parish.parish_data.get('parish_name')}' assigned plan '{plan.name}'"
            )
            created_count += 1

            # 🔁 Seed a pending plan change for the first 2 parishes
            if i < 2:
                new_tier_index = min(
                    i + 2, len(ordered_plans) - 1
                )  # upgrade 1 or 2 levels
                new_plan = ordered_plans[new_tier_index]

                parish_change = ParishSubscriptionChange(
                    parish_id=parish.id,
                    parish_subscription_id=new_subscription.id,
                    current_plan_id=plan.id,
                    next_plan_id=new_plan.id,
                    scheduled_start_date=end_date,
                    # scheduled_end_date=end_date + relativedelta(months=1),
                    scheduled_end_date=end_date + relativedelta(months=1),
                    is_applied=False,
                )
                db.add(parish_change)
                new_subscription.next_subscription_plan_id = new_plan.id

                logger.info(
                    f"Parish '{parish.parish_data.get('parish_name')}' scheduled plan change "
                    f"from '{plan.name}' to '{new_plan.name}'"
                )

        db.commit()
        logger.info("Parish subscriptions (and some changes) seeded successfully!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error while seeding parish subscriptions!: %s", str(e))
        raise
