import csv
import io
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session
from api.serializers import serialize_roles
from db.models.role import Role
from db.models.user import User
from db.session import get_db
from log_config import logger
from schemas.notification_schema import NotificationType
from schemas.roles_schema import (
    PaginatedRoleResponse,
    RoleCreate,
    RoleDetails,
)
from sqlalchemy.exc import SQLAlchemyError
from schemas.user_schema import PaginatedUserResponse
from services.auth_service import get_current_user
from services.notification_service import create_notification
from services.user_service import get_user_details

router = APIRouter()


# retrieve db/parish role count
@router.get(
    "/count",
    summary="Fetch count of all roles",
)
async def count_roles(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None),
):
    try:
        logger.info("Retrieving role count...")
        query = db.query(Role)

        if search:
            query = query.filter(Role.title.ilike(f"%{search}%"))
            logger.debug("Applied search filter on role title!")

        total_count = query.count()
        logger.info("200 | Role count fetched successfully!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during role record data count!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during role record data count!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retrieve all roles
@router.get(
    "/all",
    response_model=PaginatedRoleResponse,
    summary="Fetch all roles",
)
async def retrieve_all_roles(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    is_archived: Optional[bool] = None,
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
):
    try:
        logger.info("Retrieving roles...")

        offset = (page - 1) * page_size
        query = db.query(Role)

        if is_archived is None:
            query = query.filter(Role.is_archived == False)
        else:
            query = query.filter(Role.is_archived == is_archived)

        # Search filter
        if search:
            query = query.filter(Role.title.ilike(f"%{search}%"))
            logger.debug("Applied search filter on role title")

        # Sorting
        if sort_by and hasattr(Role, sort_by):
            sort_column = getattr(Role, sort_by)
            query = query.order_by(
                sort_column.desc() if sort_order == "desc" else sort_column
            )
            logger.debug(f"Applied sorting by {sort_by} {sort_order}")

        total_count = query.count()
        roles = query.offset(offset).limit(page_size).all()

        logger.info("200 | Retrieved roles successfully!")

        return {
            "items": serialize_roles(roles),
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
        logger.error("500 | Database error during role data query!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error("500 | Unexpected error during role data query!", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# create role
@router.post(
    "/create",
    response_model=RoleDetails,
    summary="Create a role",
)
async def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")
        title_lower = role.title.strip().lower()
        logger.info("Attempting to create role...")

        # Check if role already exists
        existing_role = (
            db.query(Role).filter(func.lower(role.title) == title_lower).first()
        )
        if existing_role:
            logger.warning(f"Role already exists!")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role already exists.",
            )

        # Create new role
        new_role = Role(title=title_lower, description=role.description)
        db.add(new_role)
        db.commit()
        db.refresh(new_role)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Role record updated successfully!",
        )

        logger.info("201 | Role created and notification sent successfully!")
        return new_role

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | Database error during role creation!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error("500 | Unexpected error during role creation!", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# get role details
@router.get(
    "/details/{role_id}",
    response_model=RoleDetails,
    summary="Get details of an existing role",
)
async def retrieve_role_details(
    role_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        logger.info("Fetching role details...")
        role = db.query(Role).filter(Role.id == role_id).first()

        if not role:
            logger.warning("Role not found!")
            raise HTTPException(status_code=404, detail="Role not found!")

        logger.info("200 | Retrieved role details successfully!")
        return role

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during role details retrieval!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during role details retrieval!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# get role users
@router.get(
    "/users/{role_id}",
    response_model=PaginatedUserResponse,
    summary="Get users with a common role",
)
async def retrieve_role_users(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    role_id: UUID = Path(...),
    # current_user: str = Depends(get_current_user)
):
    try:
        logger.info("Fetching users belonging to same role...")

        offset = (page - 1) * page_size
        query = db.query(User).filter(User.role_id == role_id)

        # Apply search
        if search:
            logger.debug("Searching users with search parameter...")
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    User.phone.ilike(f"%{search}%"),
                )
            )

        # Apply sorting
        if sort_by and hasattr(User, sort_by):
            logger.debug(f"Sorting by: {sort_by} {sort_order}")
            sort_column = getattr(User, sort_by)
            query = query.order_by(
                desc(sort_column) if sort_order == "desc" else asc(sort_column)
            )

        total_count = query.count()
        users = query.offset(offset).limit(page_size).all()

        from api.users_router import serialize_users

        logger.info("Retrieved role users successfully!")

        return {
            "items": serialize_users(users),
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
        logger.error("500 | Database error during role users retrieval!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during role users retrieval!", exc_info=True
        )


# archive role
@router.post(
    "/archive/{role_id}",
    summary="Archive role ",
)
async def archive_role(
    role_id: UUID,
    db=Depends(get_db),
):
    logger.info("Attempting to archive role...")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found!")
    role.is_archived = True
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"message": "Role successfuly archived!"}


# unarchive role
@router.post(
    "/unarchive/{role_id}",
    summary="Unarchive role",
)
async def unarchive_role(
    role_id: UUID,
    db=Depends(get_db),
):
    logger.info("Attempting to unarchive role data...")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found!")
    role.is_archived = False
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"message": "Role successfuly unarchived!"}
