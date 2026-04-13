import logging
from log_config import logger
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db.models.subscription_plan import SubscriptionPlan


# Check for existing subscription plans
def check_subscription_plans_exist(db: Session) -> bool:
    return db.query(SubscriptionPlan.id).first() is not None


# Seed subscription plans
def create_subscription_plans(db: Session):
    try:
        plans = [
            {"name": "starter", "price": Decimal("5000.00")},
            {"name": "standard", "price": Decimal("8000.00")},
            {"name": "professional", "price": Decimal("12000.00")},
            {"name": "premium", "price": Decimal("18000.00")},
            {"name": "enterprise", "price": Decimal("25000.00")},
        ]

        created, skipped = 0, 0

        for plan in plans:
            exists = db.query(SubscriptionPlan).filter_by(name=plan["name"]).first()
            if not exists:
                new_plan = SubscriptionPlan(
                    name=plan["name"],
                    price=plan["price"],
                )
                db.add(new_plan)
                created += 1
            else:
                skipped += 1

        db.commit()
        logger.info("Seeded subscription plans successfully!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("Failed to seed subscription plans due to a database error!")
        raise
