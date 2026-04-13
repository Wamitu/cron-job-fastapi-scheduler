from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db.models.subscription_plan import SubscriptionPlan
from db.models.subscription_plan_feature import SubscriptionPlanFeature
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from log_config import logger


def check_subscription_plan_feature_pivot_exist(db: Session) -> bool:
    return db.query(SubscriptionPlanFeaturePivot.id).first() is not None


def create_subscription_plan_feature_pivot(db: Session):
    try:
        plan_order = ["starter", "standard", "professional", "premium", "enterprise"]

        feature_map = {
            "starter": ["church_profile", "member_management", "basic_reporting"],
            "standard": [
                "collections_tracking",
                "sacrament_management",
                "user_role_management",
            ],
            "professional": [
                "attendance_tracking",
                "certificate_generation",
                "project_management",
                "advanced_analytics",
            ],
            "premium": [
                "bulk_sms_email",
                "automated_mpesa_reconciliation",
                "priority_support",
            ],
            "enterprise": [
                "dedicated_onboarding",
                "custom_integrations",
                "premium_sla",
                "training_workshops",
                "multi_parish_management",
            ],
        }

        plan_rank = {name: idx for idx, name in enumerate(plan_order)}
        accumulated_features: list[tuple[str, str]] = []

        for plan_name in plan_order:
            plan = db.query(SubscriptionPlan).filter_by(name=plan_name).first()
            if not plan:
                logger.warning("Plan not found! Skipping...")
                continue

            current_features = feature_map.get(plan_name, [])
            for feature_name in current_features:
                accumulated_features.append((feature_name, plan_name))

            for feature_name, _ in accumulated_features:
                feature = (
                    db.query(SubscriptionPlanFeature)
                    .filter_by(name=feature_name)
                    .first()
                )
                if not feature:
                    logger.warning("Feature not found! Skipping...")
                    continue

                exists = (
                    db.query(SubscriptionPlanFeaturePivot)
                    .filter_by(
                        subscription_plan_id=plan.id,
                        feature_id=feature.id,
                    )
                    .first()
                )

                if not exists:
                    db.add(
                        SubscriptionPlanFeaturePivot(
                            subscription_plan_id=plan.id,
                            feature_id=feature.id,
                            enabled=True,
                        )
                    )

            logger.info(f"Features added to plan successfully!")

        db.commit()
        logger.info("Pivot seeding complete!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to seed pivot!: {str(e)}")
        raise
