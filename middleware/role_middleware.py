from fastapi import Request, HTTPException
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID

from api.serializers import serialize_role
from db.models.parish import Parish
from db.models.role import Role
from db.models.user import User
from services.auth_service import get_current_user
from log_config import logger


def require_roles_by_titles(*roles: str):
    """
    Decorator to mark routes that require specific roles.

    Example:
        @require_roles_by_titles("Priest", "Admin")
        async def endpoint():
            ...
    """

    def decorator(route):
        setattr(route, "required_roles", [r.lower().strip() for r in roles if r])
        return route

    return decorator


def role_middleware(app):
    """
    Middleware to enforce authentication and role-based access control.
    """

    @app.middleware("http")
    async def check_roles(request: Request, call_next):
        route: APIRoute = request.scope.get("route")

        # Skip docs/static
        if route is None or not hasattr(route, "endpoint"):
            return await call_next(request)

        db: Session = request.state.db
        current_user = await get_current_user(request, db)

        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please provide a valid token.",
            )

        # Get user role info
        role_info = await _get_user_role_info(db, current_user)
        if not role_info:
            raise HTTPException(
                status_code=403,
                detail="User role not found. Please contact administrator.",
            )

        role_title = (role_info.get("title") or "").lower()
        required_roles: Optional[List[str]] = getattr(
            route.endpoint, "required_roles", None
        )

        # SysAdmin bypass - full access
        if role_title == "sysadmin":
            request.state.user = current_user
            request.state.role_info = role_info
            return await call_next(request)

        # If no roles were set for the endpoint → deny by default
        if not required_roles:
            raise HTTPException(
                status_code=403,
                detail="Access denied. This endpoint requires explicit role permission.",
            )

        # Check if user role is allowed
        if role_title not in [r.lower() for r in required_roles]:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {', '.join(required_roles)}",
            )

        # Priest restriction: must only access their parish
        if role_title == "priest":
            parish_access = await _validate_priest_parish_access(
                request, db, current_user
            )
            if not parish_access["valid"]:
                raise HTTPException(
                    status_code=parish_access["status_code"],
                    detail=parish_access["detail"],
                )

        # Bishop restriction: must only access parishes in their diocese
        if role_title == "bishop":
            diocese_access = await _validate_bishop_diocese_access(
                request, db, current_user
            )
            if not diocese_access["valid"]:
                raise HTTPException(
                    status_code=diocese_access["status_code"],
                    detail=diocese_access["detail"],
                )

        # Attach user + role info for downstream
        request.state.user = current_user
        request.state.role_info = role_info

        return await call_next(request)


async def _get_user_role_info(db: Session, user: User) -> Optional[Dict[str, Any]]:
    try:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if not role:
            return None
        return serialize_role(role)
    except Exception as e:
        logger.error(f"Error fetching role info for user {user.id}: {e}")
        return None


async def _validate_priest_parish_access(
    request: Request, db: Session, user: User
) -> Dict[str, Any]:
    """Priest can only access their assigned parish."""
    try:
        parish_id_param = request.query_params.get("parish_id")
        if not parish_id_param:
            return {
                "valid": False,
                "status_code": 400,
                "detail": "Parish ID is required in query parameters.",
            }

        try:
            parish_uuid = UUID(parish_id_param)
        except ValueError:
            return {
                "valid": False,
                "status_code": 400,
                "detail": "Invalid parish ID format.",
            }

        parish = db.query(Parish).filter(Parish.id == parish_uuid).first()
        if not parish:
            return {
                "valid": False,
                "status_code": 404,
                "detail": "Parish not found.",
            }

        if str(user.parish_id) != parish_id_param:
            return {
                "valid": False,
                "status_code": 403,
                "detail": "Access denied. You can only access your assigned parish.",
            }

        return {"valid": True}
    except Exception as e:
        logger.error(f"Error validating priest parish access: {e}")
        return {
            "valid": False,
            "status_code": 500,
            "detail": "Error validating parish access.",
        }


async def _validate_bishop_diocese_access(
    request: Request, db: Session, user: User
) -> Dict[str, Any]:
    """Bishop can only access parishes in their own diocese."""
    try:
        parish_id_param = request.query_params.get("parish_id")
        if not parish_id_param:
            return {
                "valid": False,
                "status_code": 400,
                "detail": "Parish ID is required in query parameters.",
            }

        try:
            parish_uuid = UUID(parish_id_param)
        except ValueError:
            return {
                "valid": False,
                "status_code": 400,
                "detail": "Invalid parish ID format.",
            }

        parish = db.query(Parish).filter(Parish.id == parish_uuid).first()
        if not parish:
            return {
                "valid": False,
                "status_code": 404,
                "detail": "Parish not found.",
            }

        if not user.diocese_id or str(parish.diocese_id) != str(user.diocese_id):
            return {
                "valid": False,
                "status_code": 403,
                "detail": "Access denied. You can only access parishes in your diocese.",
            }

        return {"valid": True}
    except Exception as e:
        logger.error(f"Error validating bishop diocese access: {e}")
        return {
            "valid": False,
            "status_code": 500,
            "detail": "Error validating diocese access.",
        }
