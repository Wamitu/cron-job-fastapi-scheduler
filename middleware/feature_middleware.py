from fastapi import Request, HTTPException
from fastapi.routing import APIRoute
from sqlalchemy.orm import joinedload, Session
from typing import Optional, Dict, Any, List
from log_config import logger

from db.models.parish import Parish
from db.models.parish_subscription import ParishSubscription
from db.models.subscription_plan import SubscriptionPlan
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from db.models.user import User
from services.auth_service import get_current_user


def require_feature(feature_name: str):
    """
    Decorator to mark routes that require a specific subscription feature.

    Args:
        feature_name: Name of the required feature

    Example:
        @require_feature("advanced_analytics")
        async def analytics_endpoint():
            pass
    """

    def decorator(route):
        setattr(route, "required_feature", feature_name.strip())
        return route

    return decorator


def feature_middleware(app):
    """
    Middleware to enforce subscription feature-based access control.
    Checks if the user's parish has an active subscription with the required feature.
    """

    @app.middleware("http")
    async def check_feature(request: Request, call_next):
        route: APIRoute = request.scope.get("route")
        # Guard for non-routed requests (e.g., OpenAPI, docs, static)
        if route is None or not hasattr(route, "endpoint"):
            return await call_next(request)

        feature_name: Optional[str] = getattr(route.endpoint, "required_feature", None)
        if feature_name:
            feature_name = feature_name.strip().lower()

        # Skip feature checking if no feature is required
        if not feature_name:
            return await call_next(request)

        try:
            db: Session = request.state.db
            current_user = await get_current_user(request=request, db=db)

            if not current_user:
                logger.warning(
                    f"Feature check failed: No user found for {request.method} {request.url.path}"
                )
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required. Please provide a valid token.",
                )

            # Get user with comprehensive subscription data
            user_data = await _get_user_subscription_data(db, current_user)
            if not user_data:
                logger.error(
                    f"Failed to load user data for feature check: {current_user.id}"
                )
                raise HTTPException(
                    status_code=500,
                    detail="Unable to verify subscription status. Please try again.",
                )

            user = user_data["user"]
            role_title = (user_data["role_title"] or "").lower()

            # SysAdmin bypass - full access to all features
            if role_title == "sysadmin":
                logger.debug(f"SysAdmin feature access granted to {feature_name}")
                request.state.user = current_user
                request.state.subscription_data = user_data
                return await call_next(request)

            # Validate parish and subscription
            subscription_validation = await _validate_subscription_access(
                user, feature_name
            )
            if not subscription_validation["valid"]:
                raise HTTPException(
                    status_code=subscription_validation["status_code"],
                    detail=subscription_validation["detail"],
                )

            # Check if feature is enabled
            feature_enabled = await _check_feature_enabled(
                user_data["active_subscription"], feature_name
            )

            if not feature_enabled:
                logger.warning(
                    f"Feature access denied: User {current_user.id} attempted to access "
                    f"feature '{feature_name}' without subscription"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Feature '{feature_name}' is not available in your current subscription plan. "
                    f"Please upgrade your subscription to access this feature.",
                )

            # Set user and subscription data in request state
            request.state.user = current_user
            request.state.subscription_data = user_data

            logger.debug(
                f"Feature access granted: User {current_user.id} accessing feature '{feature_name}'"
            )

        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error in feature middleware: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error during feature validation",
            )

        return await call_next(request)


async def _get_user_subscription_data(
    db: Session, user: User
) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive user data including role and subscription information.

    Args:
        db: Database session
        user: User object

    Returns:
        Dictionary containing user data or None if not found
    """
    try:
        # Load user with all related data in a single optimized query
        user_with_data = (
            db.query(User)
            .options(
                joinedload(User.role),
                joinedload(User.parish)
                .joinedload(Parish.subscription)
                .joinedload(ParishSubscription.subscription)
                .joinedload(SubscriptionPlan.features_pivot)
                .joinedload(SubscriptionPlanFeaturePivot.feature),
            )
            .filter(User.id == user.id)
            .first()
        )

        if not user_with_data:
            return None

        role_title = user_with_data.role.title.lower() if user_with_data.role else None

        # Find active subscription
        active_subscription = None
        if user_with_data.parish and user_with_data.parish.subscription:
            active_subscription = next(
                (
                    sub
                    for sub in user_with_data.parish.subscription
                    if sub.status == "active"
                ),
                None,
            )

        return {
            "user": user_with_data,
            "role_title": role_title,
            "active_subscription": active_subscription,
            "parish": user_with_data.parish,
        }

    except Exception as e:
        logger.error(f"Error loading user subscription data: {e}")
        return None


async def _validate_subscription_access(
    user: User, feature_name: str
) -> Dict[str, Any]:
    """
    Validate that the user has a valid parish and active subscription.

    Args:
        user: User object with loaded relationships
        feature_name: Name of the required feature

    Returns:
        Dictionary with validation result
    """
    try:
        if not user.parish:
            return {
                "valid": False,
                "status_code": 403,
                "detail": "No parish associated with your account. Please contact administrator.",
            }

        if not user.parish.subscription:
            return {
                "valid": False,
                "status_code": 403,
                "detail": "No subscription found for your parish. Please contact administrator.",
            }

        # Check for active subscription
        active_subscription = next(
            (sub for sub in user.parish.subscription if sub.status == "active"), None
        )

        if not active_subscription:
            return {
                "valid": False,
                "status_code": 403,
                "detail": "No active subscription found. Please activate your subscription to access features.",
            }

        if not active_subscription.subscription:
            return {
                "valid": False,
                "status_code": 403,
                "detail": "Invalid subscription plan. Please contact support.",
            }

        return {"valid": True}

    except Exception as e:
        logger.error(f"Error validating subscription access: {e}")
        return {
            "valid": False,
            "status_code": 500,
            "detail": "Error validating subscription. Please try again.",
        }


async def _check_feature_enabled(
    active_subscription: ParishSubscription, feature_name: str
) -> bool:
    """
    Check if a specific feature is enabled in the active subscription.

    Args:
        active_subscription: Active parish subscription
        feature_name: Name of the feature to check

    Returns:
        True if feature is enabled, False otherwise
    """
    try:
        if not active_subscription or not active_subscription.subscription:
            return False

        plan = active_subscription.subscription
        if not plan.features_pivot:
            return False

        # Check if feature exists and is enabled
        for pivot in plan.features_pivot:
            if (
                pivot.feature
                and isinstance(pivot.feature.name, str)
                and pivot.feature.name.strip().lower() == feature_name
                and pivot.enabled
            ):
                return True

        return False

    except Exception as e:
        logger.error(f"Error checking feature '{feature_name}': {e}")
        return False
