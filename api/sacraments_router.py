import csv
from io import StringIO
import re
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from api.serializers import serialize_sacraments
from db.models.parish import Parish
from db.models.sacrament import Sacrament
from db.models.user import User
from db.session import get_db
from schemas.notification_schema import NotificationType
from schemas.sacrament_schema import (
    SacramentCreate,
    SacramentDetails,
    SacramentUpdate,
    PaginatedSacramentResponse,
)
from sqlalchemy.exc import SQLAlchemyError
from log_config import logger
from services.auth_service import (
    get_current_user,
)
from services.notification_service import create_notification
from services.user_service import get_user_details

router = APIRouter()


# retrieve db/parish sacrament count with parish filter
@router.get(
    "/count",
    summary="Get count of all sacraments (optionally filtered by parish)",
)
async def count_parish_sacrament_records(
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Retrieving all sacraments count...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view sacrament count.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view sacrament count from another parish.",
                )

        query = db.query(Sacrament)
        logger.info("Retrieving sacraments...")

        if parish_id:
            logger.debug("Checking if parish exists...")
            parish_exists = db.query(Parish.id).filter(Parish.id == parish_id).first()
            if not parish_exists:
                logger.warning(f"Parish not found!")
                raise HTTPException(status_code=404, detail="Parish not found!")
            query = query.filter(Sacrament.parish_id == parish_id)

        total_count = query.count()
        logger.info("200 | Sacrament count fetched successfully!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during sacrament data count!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacrament data count!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retrieve db/parish sacraments with parish filter
@router.get(
    "/all",
    response_model=PaginatedSacramentResponse,
    summary="Get sacraments (all or filtered by parish)",
)
async def retrieve_sacraments(
    request: Request,
    parish_id: Optional[UUID] = Query(
        None, description="Optional parish ID to filter sacraments"
    ),
    is_archived: Optional[bool] = None,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Retrieving all sacrament data...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view sacrament data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view sacrament data from another parish.",
                )
        offset = (page - 1) * page_size
        query = db.query(Sacrament).options(joinedload(Sacrament.parish))
        logger.info("Attempting to create sacrament...")

        if is_archived is None:
            query = query.filter(Sacrament.is_archived == False)
        else:
            query = query.filter(Sacrament.is_archived == is_archived)

        if parish_id:
            logger.debug("Filtering sacraments by parish_id...")
            query = query.filter(Sacrament.parish_id == parish_id)

        if search:
            logger.debug("Searching sacraments with search term...")
            query = query.filter(Sacrament.name.ilike(f"%{search}%"))

        if sort_by and hasattr(Sacrament, sort_by):
            column = getattr(Sacrament, sort_by)
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            query = query.order_by(Sacrament.created_at.desc())

        total_count = query.count()
        sacraments = query.offset(offset).limit(page_size).all()

        logger.info("200 | Retrieved sacraments successfully!")

        return {
            "items": serialize_sacraments(sacraments),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "pages": (total_count + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except Exception as e:
        logger.exception("Failed to retrieve sacraments")
        raise HTTPException(status_code=500, detail="Failed to retrieve sacraments")


# create sacrament
@router.post(
    "/create",
    summary="Create a sacrament, linked to a parish",
)
async def create_sacrament(
    sacrament_create: SacramentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")
        parish_id = sacrament_create.parish_id

        # Check if parish exists
        db_parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not db_parish:
            logger.warning(f"Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

        # Check for duplicate sacrament
        db_sacrament = (
            db.query(Sacrament)
            .filter(
                and_(
                    Sacrament.name == sacrament_create.name,
                    Sacrament.parish_id == parish_id,
                )
            )
            .first()
        )
        if db_sacrament:
            logger.warning("Sacrament already exists!")
            raise HTTPException(
                status_code=409, detail="Sacrament already exists for this parish!"
            )

        # Create sacrament
        new_sacrament = Sacrament(**sacrament_create.model_dump())
        db.add(new_sacrament)
        db.commit()
        db.refresh(new_sacrament)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Sacrament created and notification sent successfully!",
        )

        logger.info("201 | Sacrament created and notification sent successfully!")
        return new_sacrament

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during sacrament creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacrament creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# get sacrament details
@router.get(
    "/details/{sacrament_id}",
    response_model=SacramentDetails,
    summary="Get details of an existing sacrament",
)
async def retrieve_sacrament_details(
    sacrament_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        logger.debug("Looking up sacrament!")
        db_sacrament = (
            db.query(Sacrament)
            .options(joinedload(Sacrament.parish))
            .filter(Sacrament.id == sacrament_id)
            .first()
        )

        if not db_sacrament:
            logger.warning("Sacrament not found!")
            raise HTTPException(status_code=404, detail="Sacrament not found!")

        logger.info("Sacrament retrieved successfully!")
        return db_sacrament

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during sacrament details query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacrament details query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# update sacrament details
@router.put(
    "/update/{sacrament_id}",
    response_model=SacramentDetails,
    summary="Update an existing sacrament",
)
async def update_sacrament_details(
    sacrament_id: UUID,
    sacrament_update: SacramentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")
        logger.debug("Attempting to update sacrament...")
        db_sacrament = db.query(Sacrament).filter(Sacrament.id == sacrament_id).first()
        if not db_sacrament:
            logger.warning("Sacrament not found!")
            raise HTTPException(status_code=404, detail="Sacrament not found!")

        update_data = sacrament_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_sacrament, key, value)

        db.commit()
        db.refresh(db_sacrament)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Sacrament updated and notification sent successfully!",
        )

        logger.info("201 | Sacrament updated and notification sent successfully!")
        return db_sacrament

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during sacrament data update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacrament data update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# archive sacrament
@router.post(
    "/archive/{sacrament_id}",
    summary="Archive sacrament",
)
async def archive_sacrament(
    sacrament_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive sacrament data...")
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    role_title = user.role.title if hasattr(user.role, "title") else None

    # parish existence check
    if parish_id is not None:
        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

    # role and parish based check
    if role_title == "Priest":
        if parish_id is None:
            raise HTTPException(
                status_code=403,
                detail="Priests must specify a parish_id to archive sacrament data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive sacrament data from another parish.",
            )

    sacrament = db.query(Sacrament).filter(Sacrament.id == sacrament_id).first()
    if not sacrament:
        raise HTTPException(status_code=404, detail="Sacrament not found!")
    sacrament.is_archived = True
    db.add(sacrament)
    db.commit()
    db.refresh(sacrament)
    return {"message": "Sacrament successfuly archived!"}


# unarchive sacrament
@router.post("/unarchive/{sacrament_id}", summary="Unarchive sacrament")
async def unarchive_sacrament(
    sacrament_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive sacrament data...")
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    role_title = user.role.title if hasattr(user.role, "title") else None

    # parish existence check
    if parish_id is not None:
        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

    # role and parish based check
    if role_title == "Priest":
        if parish_id is None:
            raise HTTPException(
                status_code=403,
                detail="Priests must specify a parish_id to unarchive sacrament data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to unarchive sacrament data from another parish.",
            )
    sacrament = db.query(Sacrament).filter(Sacrament.id == sacrament_id).first()
    if not sacrament:
        raise HTTPException(status_code=404, detail="Sacrament not found!")
    sacrament.is_archived = False
    db.add(sacrament)
    db.commit()
    db.refresh(sacrament)
    return {"message": "Sacrament successfuly unarchived!"}
