from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import case, func, inspect, or_
from sqlalchemy.orm import Session
from api.serializers import serialize_subscription_plan_features
from db.models.subscription_plan import SubscriptionPlan
from db.models.subscription_plan_feature import SubscriptionPlanFeature
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from db.session import get_db
from schemas.subscription_plan_feature_schema import (
    FeatureAssignRequest,
    PaginatedSubscriptionPlanFeatureResponse,
)
from sqlalchemy.orm import joinedload

from schemas.subscription_plan_schema import (
    SubscriptionPlanCreate,
    SubscriptionPlanDetails,
    PaginatedSubscriptionPlanResponse,
    SubscriptionPlanUpdate,
    Feature,
)
from fastapi import HTTPException, status, Depends
from sqlalchemy.exc import SQLAlchemyError
from log_config import logger
from collections import defaultdict


router = APIRouter()


# retrieve all db subscription plans
@router.get(
    "/all",
    response_model=PaginatedSubscriptionPlanResponse,
    summary="Get all subscription plans in the system",
)
async def retrieve_all_subscription_plans(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
):
    try:
        logger.info("Retrieving subscription plans...")
        offset = (page - 1) * page_size
        query = db.query(SubscriptionPlan)

        # Optional search by plan name
        if search:
            query = query.filter(SubscriptionPlan.name.ilike(f"%{search}%"))

        # Optional sorting
        valid_columns = {c.key for c in inspect(SubscriptionPlan).mapper.column_attrs}
        if sort_by:
            if sort_by not in valid_columns:
                logger.warning("Invalid sort_by field attempted!")
                raise HTTPException(status_code=400, detail="Invalid sort_by field!")
            sort_column = getattr(SubscriptionPlan, sort_by)
            query = query.order_by(
                sort_column.desc() if sort_order == "desc" else sort_column.asc()
            )
        else:
            query = query.order_by(SubscriptionPlan.created_at.desc())

        total_count = query.count()
        subscription_plans = query.offset(offset).limit(page_size).all()

        # Fetch only enabled features
        pivot_rows = (
            db.query(SubscriptionPlanFeaturePivot)
            .options(joinedload(SubscriptionPlanFeaturePivot.feature))
            .filter(SubscriptionPlanFeaturePivot.enabled.is_(True))
            .all()
        )

        # Group features by subscription_plan_id
        features_by_plan_id = defaultdict(list)
        for pivot in pivot_rows:
            features_by_plan_id[pivot.subscription_plan_id].append(
                {
                    "id": pivot.feature.id,
                    "name": pivot.feature.name,
                    "description": pivot.feature.description,
                    "enabled": pivot.enabled,
                }
            )

        # Build enriched plan data
        enriched_plans = []
        for plan in subscription_plans:
            enriched_plans.append(
                {
                    "id": plan.id,
                    "name": plan.name,
                    "price": plan.price,
                    "features": features_by_plan_id.get(plan.id, []),
                    "created_at": plan.created_at,
                    "updated_at": plan.updated_at,
                }
            )

        return {
            "items": enriched_plans,
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
            "500 | Database error during subscription plans retrieval!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during subscription plans retrieval!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retreive features of a specific plan
@router.get(
    "/features/{plan_name}",
    response_model=PaginatedSubscriptionPlanFeatureResponse,
    summary="Get features for a specific subscription plan (filter by enabled)",
)
async def retrieve_subscription_plan_features(
    plan_name: str = Path(..., description="Name of the subscription plan"),
    enabled: Optional[bool] = Query(
        None, description="Filter features by enabled status"
    ),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: Optional[str] = Query("name"),
    sort_order: Optional[str] = Query("asc"),
):
    try:
        logger.info("Retrieving features for a specific subscription plan...")
        offset = (page - 1) * page_size

        # Fetch the subscription plan by name (case-insensitive)
        plan = (
            db.query(SubscriptionPlan)
            .filter(func.lower(SubscriptionPlan.name) == plan_name.lower())
            .first()
        )

        if not plan:
            logger.info("404 | Plan not found!")
            raise HTTPException(status_code=404, detail="Plan not found")

        pivot = SubscriptionPlanFeaturePivot
        feature_model = SubscriptionPlanFeature

        # Build query
        query = (
            db.query(feature_model, pivot.enabled)
            .join(pivot, pivot.feature_id == feature_model.id)
            .filter(pivot.subscription_plan_id == plan.id)
        )

        # Apply enabled filter if provided
        if enabled is not None:
            query = query.filter(pivot.enabled == enabled)

        # Validate and apply sorting
        valid_sort_fields = {c.key for c in inspect(feature_model).mapper.column_attrs}
        if sort_by not in valid_sort_fields:
            raise HTTPException(status_code=400, detail="Invalid sort_by field!")

        sort_column = getattr(feature_model, sort_by)
        query = query.order_by(
            sort_column.desc() if sort_order == "desc" else sort_column.asc()
        )

        results = query.all()

        # Deduplicate by feature name
        seen = set()
        unique_features = []
        for feature, is_enabled in results:
            if feature.name not in seen:
                feature.enabled = is_enabled  # attach enabled field from pivot
                unique_features.append(feature)
                seen.add(feature.name)

        total = len(unique_features)
        paginated = unique_features[offset : offset + page_size]

        logger.info("200 | Plan features retrieved successfully!")

        return {
            "items": serialize_subscription_plan_features(paginated),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise
    except Exception:
        logger.exception("Failed to retrieve subscription plan features!")
        raise HTTPException(status_code=500, detail="Unable to retrieve features!")


# create subscription_plan
@router.post(
    "/create",
    summary="Create a new subscription plan",
)
async def create_subscription_plan(
    subscription_plan_create: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
):
    try:
        plan_name = subscription_plan_create.name.strip()

        # Check if plan exists (case insensitive)
        existing_plan = (
            db.query(SubscriptionPlan)
            .filter(func.lower(SubscriptionPlan.name) == plan_name.lower())
            .first()
        )
        if existing_plan:
            logger.warning("409 | Subscription plan already exists!")
            raise HTTPException(
                status_code=409,
                detail="A subscription plan with this name already exists!",
            )

        new_plan = SubscriptionPlan(**subscription_plan_create.model_dump())
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)

        logger.info("201 | Subscription plan created!")
        return new_plan

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


# get subscription_plan details
@router.get(
    "/details/{subscription_plan_id}",
    response_model=SubscriptionPlanDetails,
    summary="Get details of an existing subscription plan",
)
async def get_subscription_plan_details(
    subscription_plan_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        # Get the base subscription plan
        db_plan = db.query(SubscriptionPlan).filter_by(id=subscription_plan_id).first()

        if not db_plan:
            logger.info("404 | Subscription plan not found!")
            raise HTTPException(status_code=404, detail="Subscription plan not found.")

        # Plan hierarchy for inheritance
        plan_order = ["starter", "standard", "professional", "premium", "enterprise"]
        all_plans = db.query(SubscriptionPlan).all()
        plans_by_name = {p.name: p.id for p in all_plans}

        if db_plan.name in plan_order:
            index = plan_order.index(db_plan.name)
            inherited_ids = [
                plans_by_name[name]
                for name in plan_order[: index + 1]
                if name in plans_by_name
            ]
        else:
            inherited_ids = [db_plan.id]

        # Query pivot table directly for inherited plans
        pivot_rows = (
            db.query(SubscriptionPlanFeaturePivot)
            .filter(
                SubscriptionPlanFeaturePivot.subscription_plan_id.in_(inherited_ids)
            )
            .join(SubscriptionPlanFeaturePivot.feature)
            .all()
        )

        # Deduplicate features by name
        seen = set()
        features = []
        for pivot in pivot_rows:
            feature = pivot.feature
            if feature.name not in seen:
                features.append(
                    Feature(
                        id=feature.id,
                        name=feature.name,
                        description=feature.description,
                        enabled=pivot.enabled,
                    )
                )
                seen.add(feature.name)

        return SubscriptionPlanDetails(
            id=db_plan.id,
            name=db_plan.name,
            price=db_plan.price,
            created_at=db_plan.created_at,
            updated_at=db_plan.updated_at,
            features=features,
        )

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


# update a subscription plan
@router.put(
    "/update/{plan_id}",
    summary="Update subscription plan details",
)
def update_subscription_plan_details(
    plan_id: UUID,
    payload: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        logger.info("Plan not found!")
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    if payload.name:
        plan.name = payload.name
    if payload.price:
        plan.price = payload.price

    db.commit()
    db.refresh(plan)
    logger.info("Plan feature updated successfully!")
    return {"detail": "Plan details updated successfully"}


# Add feature to subscription plan
@router.post(
    "/feature/add/{plan_id}",
    summary="Add a feature to a subscription plan",
)
def add_feature_to_plan(
    plan_id: UUID,
    add_feature: FeatureAssignRequest,
    db: Session = Depends(get_db),
):
    logger.info("Attemping to add feature to plan...")
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    exists = (
        db.query(SubscriptionPlanFeaturePivot)
        .filter_by(subscription_plan_id=plan_id, feature_id=add_feature.feature_id)
        .first()
    )

    if exists:
        logger.info("409 | Feature already exists in plan!")
        raise HTTPException(
            status_code=400, detail="Feature already assigned to this pla!"
        )

    pivot = SubscriptionPlanFeaturePivot(
        subscription_plan_id=plan_id,
        feature_id=add_feature.feature_id,
        enabled=add_feature.enabled,
    )

    db.add(pivot)
    db.commit()
    logger.info("Feature added to plan successfully!")
    return {"detail": "Feature added to subscription plan"}


# Remove feature from subscription plan
@router.delete(
    "/feature/remove/{plan_id}/{feature_id}",
    summary="Remove a feature from a subscription plan",
)
def remove_feature_from_plan(
    plan_id: UUID,
    feature_id: UUID,
    db: Session = Depends(get_db),
):
    logger.info("Attempting to remove feature from plan...")

    pivot = (
        db.query(SubscriptionPlanFeaturePivot)
        .filter_by(subscription_plan_id=plan_id, feature_id=feature_id)
        .first()
    )

    if not pivot:
        logger.warning("Feature not found in plan!")
        raise HTTPException(
            status_code=404, detail="Feature not assigned to this subscription plan"
        )

    db.delete(pivot)
    db.commit()
    logger.info("Feature removed from plan successfully!")
    return {"detail": "Feature removed from subscription plan"}


# Enable feature from subscription plan
@router.put(
    "/{plan_id}/feature/enable/{feature_id}",
    summary="Enable a previously disabled feature in a subscription plan",
)
def enable_feature_in_plan(
    plan_id: UUID,
    feature_id: UUID,
    db: Session = Depends(get_db),
):
    logger.info("Attempting to enable feature in subscription plan...")
    pivot = (
        db.query(SubscriptionPlanFeaturePivot)
        .filter_by(subscription_plan_id=plan_id, feature_id=feature_id)
        .first()
    )

    if not pivot:
        logger.info("Feature not found in this plan!")
        raise HTTPException(status_code=404, detail="Feature not found in this plan")

    pivot.enabled = True  # Enable the feature
    db.commit()
    logger.info("Feature enabled successfully!")
    return {"detail": "Feature enabled in subscription plan"}


# Disable feature from subscription plan
@router.put(
    "/{plan_id}/feature/disable/{feature_id}",
    summary="Disable a feature in a subscription plan",
)
def disable_feature_in_plan(
    plan_id: UUID,
    feature_id: UUID,
    db: Session = Depends(get_db),
):
    logger.info("Attempting to disble feature in subscription plan...")
    pivot = (
        db.query(SubscriptionPlanFeaturePivot)
        .filter_by(subscription_plan_id=plan_id, feature_id=feature_id)
        .first()
    )

    if not pivot:
        logger.info("Feature not found in this plan!")
        raise HTTPException(status_code=404, detail="Feature not found in this plan")

    pivot.enabled = False  # Disable the feature
    db.commit()
    logger.info("Feature disabled successfully!")
    return {"detail": "Feature disabled in subscription plan"}
