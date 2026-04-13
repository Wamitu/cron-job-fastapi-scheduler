from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session
from api.serializers import (
    serialize_subscription_plan_feature,
    serialize_subscription_plan_features,
)
from db.models.subscription_plan import SubscriptionPlan
from db.models.subscription_plan_feature import SubscriptionPlanFeature
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from db.session import get_db
from schemas.subscription_plan_feature_schema import (
    PaginatedSubscriptionPlanFeatureResponse,
    SubscriptionPlanFeatureCreate,
    SubscriptionPlanFeatureUpdate,
)
from sqlalchemy.exc import SQLAlchemyError
from log_config import logger


router = APIRouter()


# retrieve all subscription plan features
@router.get(
    "/all",
    response_model=PaginatedSubscriptionPlanFeatureResponse,
    summary="Get all subscription plans with features",
)
async def retrieve_all_subscription_plans(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("name"),
    sort_order: Optional[str] = Query("asc"),
):
    try:
        logger.debug("Retrieving subscription plan features...")

        offset = (page - 1) * page_size
        query = db.query(SubscriptionPlanFeature)

        if search:
            query = query.filter(SubscriptionPlanFeature.name.ilike(f"%{search}%"))

        # Safe sort field check
        valid_columns = {
            c.key for c in inspect(SubscriptionPlanFeature).mapper.column_attrs
        }
        if sort_by not in valid_columns:
            logger.warning("Invalid sort_by field!")
            raise HTTPException(status_code=400, detail="Invalid sort_by field!")

        sort_column = getattr(SubscriptionPlanFeature, sort_by)
        query = query.order_by(
            sort_column.desc() if sort_order == "desc" else sort_column.asc()
        )

        total_count = query.count()
        subscription_plan_features = query.offset(offset).limit(page_size).all()

        logger.info("Retrieved features successfully!")
        return {
            "items": serialize_subscription_plan_features(subscription_plan_features),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "pages": (total_count + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during subscription plan features query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during subscription plan features query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# Create a new subscription plan feature and attach to subscription plan
@router.post(
    "/create",
    summary="Create a new feature (and optionally attach to a plan)",
)
def create_feature(
    feature: SubscriptionPlanFeatureCreate, db: Session = Depends(get_db)
):
    try:
        logger.info("Attempting to create subscription plan feature...")
        # Check if feature already exists
        existing_feature = (
            db.query(SubscriptionPlanFeature)
            .filter(func.lower(SubscriptionPlanFeature.name) == feature.name.lower())
            .first()
        )
        if existing_feature:
            raise HTTPException(status_code=409, detail="Feature already exists!")

        # Create the feature
        new_feature = SubscriptionPlanFeature(
            name=feature.name, description=feature.description
        )
        db.add(new_feature)
        db.commit()
        db.refresh(new_feature)

        # If plan_id is provided, attach feature to plan through pivot
        if feature.plan_id:
            # Ensure plan exists
            plan = db.query(SubscriptionPlan).filter_by(id=feature.plan_id).first()
            if not plan:
                raise HTTPException(
                    status_code=404, detail="Subscription plan not found!"
                )

            pivot = SubscriptionPlanFeaturePivot(
                subscription_plan_id=plan.id,
                feature_id=new_feature.id,
                enabled=feature.enabled,
            )
            db.add(pivot)
            db.commit()

        return {
            "message": "Feature created successfully",
            "feature_id": new_feature.id,
            "attached_to_plan": bool(feature.plan_id),
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during subscription plan feature creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during subscription plan feature creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# get details of an existing subscription plan feature
@router.get(
    "/details/{feature_id}",
    summary="Get details of a single feature (and optionally its plan association)",
)
def get_feature_details(
    feature_id: UUID,
    plan_id: Optional[UUID] = Query(
        None, description="Optional plan to show pivot info"
    ),
    db: Session = Depends(get_db),
):
    try:
        logger.info("Retrieving subscription plan feature details...")
        # Fetch feature
        feature = db.query(SubscriptionPlanFeature).filter_by(id=feature_id).first()
        if not feature:
            raise HTTPException(status_code=404, detail="Feature not found!")

        feature_data = serialize_subscription_plan_feature(feature)

        # If plan_id is passed, try to get pivot data
        if plan_id:
            pivot = (
                db.query(SubscriptionPlanFeaturePivot)
                .filter_by(feature_id=feature_id, subscription_plan_id=plan_id)
                .first()
            )
            if pivot:
                feature_data["enabled"] = pivot.enabled
            else:
                feature_data["enabled"] = None

        return feature_data

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during subscription plan feature details query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during subscription plan feature details query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# update subscription plan feature
@router.patch(
    "/update/{feature_id}",
    summary="Update a feature and/or its subscription plan relationship",
)
def update_feature(
    feature_id: UUID,
    feature_update: SubscriptionPlanFeatureUpdate,
    db: Session = Depends(get_db),
):
    try:
        logger.info("Retrieving subscription plan feature details...")
        # Get the feature
        feature = db.query(SubscriptionPlanFeature).filter_by(id=feature_id).first()
        if not feature:
            logger.info("Feature not found!")
            raise HTTPException(status_code=404, detail="Feature not found")

        # Update feature fields
        if feature_update.name is not None:
            feature.name = feature_update.name
        if feature_update.description is not None:
            feature.description = feature_update.description

        db.commit()
        db.refresh(feature)

        # If plan_id is provided, update the pivot table
        if feature_update.plan_id:
            pivot = (
                db.query(SubscriptionPlanFeaturePivot)
                .filter_by(
                    feature_id=feature_id,
                    subscription_plan_id=feature_update.plan_id,
                )
                .first()
            )
            if not pivot:
                raise HTTPException(
                    status_code=404, detail="Feature not attached to the specified plan"
                )

            if feature_update.enabled is not None:
                pivot.enabled = feature_update.enabled

            db.commit()
            logger.info("Feature updated successfully!")
        return {"message": "Feature updated successfully"}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during subscription plan feature update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during subscription plan feature update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")
