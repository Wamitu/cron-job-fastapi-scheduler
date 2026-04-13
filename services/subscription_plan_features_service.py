import logging
from uuid import uuid4
from log_config import logger
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db.models.subscription_plan import SubscriptionPlan
from db.models.subscription_plan_feature import SubscriptionPlanFeature


def check_subscription_plan_features_exist(db: Session) -> bool:
    return db.query(SubscriptionPlanFeature.id).first() is not None


def populate_plan_features_json(db: Session):
    try:
        plan_order = ["starter", "standard", "professional", "premium", "enterprise"]

        feature_map = {
            "starter": {"church_profile", "member_management", "basic_reporting"},
            "standard": {
                "collections_tracking",
                "sacrament_management",
                "user_role_management",
            },
            "professional": {
                "attendance_tracking",
                "certificate_generation",
                "project_management",
                "advanced_analytics",
            },
            "premium": {
                "bulk_sms_email",
                "automated_mpesa_reconciliation",
                "priority_support",
            },
            "enterprise": {
                "dedicated_onboarding",
                "custom_integrations",
                "premium_sla",
                "training_workshops",
                "multi_parish_management",
            },
        }

        accumulated_features = []

        for plan_name in plan_order:
            plan = db.query(SubscriptionPlan).filter_by(name=plan_name).first()
            if not plan:
                logger.warning(f"Subscription plan not found! Skipping update.")
                continue

            current_features = feature_map.get(plan_name, set())
            accumulated_features += list(current_features)

            feature_records = (
                db.query(SubscriptionPlanFeature)
                .filter(
                    SubscriptionPlanFeature.name.in_(accumulated_features),
                    SubscriptionPlanFeature.subscription_plan_id == plan.id,
                )
                .all()
            )

            feature_list = []
            for f in feature_records:
                feature_list.append(
                    {
                        "name": f.name,
                        "description": f.description,
                        "enabled": f.name in current_features,
                    }
                )

            plan.features = feature_list
            logger.info("Updated features for subscription plan!")

        db.commit()
        logger.info("All subscription plan features updated successfully!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("Failed to update features for subscription plans!")
        raise


def create_subscription_plan_features(db: Session):
    try:
        features = [
            {"name": "church_profile", "description": "Church profile management"},
            {"name": "member_management", "description": "Manage church members"},
            {"name": "basic_reporting", "description": "Generate basic reports"},
            {
                "name": "collections_tracking",
                "description": "Track collections and offerings",
            },
            {"name": "sacrament_management", "description": "Manage sacraments"},
            {
                "name": "user_role_management",
                "description": "Assign and manage user roles",
            },
            {
                "name": "attendance_tracking",
                "description": "Track service and event attendance",
            },
            {
                "name": "certificate_generation",
                "description": "Generate sacramental certificates",
            },
            {"name": "project_management", "description": "Manage church projects"},
            {
                "name": "advanced_analytics",
                "description": "Get deep insights into church operations",
            },
            {"name": "bulk_sms_email", "description": "Send SMS and email in bulk"},
            {
                "name": "automated_mpesa_reconciliation",
                "description": "Automatic M-Pesa matching",
            },
            {"name": "priority_support", "description": "Priority technical support"},
            {
                "name": "dedicated_onboarding",
                "description": "Dedicated onboarding specialist",
            },
            {
                "name": "custom_integrations",
                "description": "Custom system integrations",
            },
            {"name": "premium_sla", "description": "Premium Service Level Agreement"},
            {"name": "training_workshops", "description": "Live training workshops"},
            {
                "name": "multi_parish_management",
                "description": "Manage multiple parishes",
            },
        ]

        created, skipped = 0, 0

        for f in features:
            exists = db.query(SubscriptionPlanFeature).filter_by(name=f["name"]).first()
            if not exists:
                db.add(
                    SubscriptionPlanFeature(
                        name=f["name"], description=f["description"]
                    )
                )
                created += 1
            else:
                skipped += 1

        db.commit()
        logger.info(f"Seeded features successfully!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("Failed to seed features due to a database error!")
        raise
