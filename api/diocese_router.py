from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from api.serializers import serialize_dioceses
from db.models.diocese import Diocese
from db.models.parish import Parish
from db.models.user import User
from db.session import get_db
from log_config import logger
from schemas.diocese_schema import PaginatedDioceseResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from schemas.user_schema import PaginatedUserResponse


router = APIRouter()


# get data count
@router.get(
    "/count",
    summary="Fetch all count of dioceses",
)
async def count_diocese_records(
    db: Session = Depends(get_db),
):
    try:
        query = db.query(Diocese)
        total_count = query.count()
        logger.info("200 | Diocese count fetched successfully!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during diocese data count!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during diocese data count!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# retrieve all dioceses
@router.get(
    "/all",
    response_model=PaginatedDioceseResponse,
    summary="Fetch all dioceses",
)
async def retrieve_all_dioceses(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
):
    offset = (page - 1) * page_size

    try:
        query = db.query(Diocese).options(joinedload(Diocese.parishes))

        if search:
            query = query.filter(
                Diocese["name"].astext.ilike(f"%{search}%"),
            )

        # sort parameter
        allowed_sort_fields = {"name"}
        if sort_by in allowed_sort_fields:
            column = getattr(Diocese, sort_by)
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            query = query.order_by(Diocese.created_at.desc())

        total_count = query.count()
        dioceses = query.offset(offset).limit(page_size).all()

        logger.info(f"Retrieved dioceses successfully!")

        return {
            "items": serialize_dioceses(dioceses),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "pages": (total_count + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during diocese data query!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during diocese data query!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# retrieve all parishes under a diocese
@router.get(
    "/parishes",
    response_model=PaginatedDioceseResponse,
    summary="Fetch all parishes under a diocese",
)
async def retrieve_all_parishes_under_a_diocese(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    diocese_id: Optional[int] = Query(None, description="Filter by a specific diocese"),
):
    offset = (page - 1) * page_size

    try:
        query = db.query(Diocese).options(joinedload(Diocese.parishes))

        # diocese filter
        if diocese_id:
            query = query.filter(Diocese.id == diocese_id)

        # search parameter
        if search:
            query = query.filter(Diocese.name.ilike(f"%{search}%"))

        # sort parameter
        allowed_sort_fields = {"name"}
        if sort_by in allowed_sort_fields:
            column = getattr(Diocese, sort_by)
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            query = query.order_by(Diocese.created_at.desc())

        total_count = query.count()
        dioceses = query.offset(offset).limit(page_size).all()

        logger.info(f"Retrieved dioceses successfully!")

        return {
            "items": serialize_dioceses(dioceses),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "pages": (total_count + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during diocese data query!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during diocese data query!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# retrieve db/parish users with parish filter belonging to diocese parishes
@router.get(
    "/parish/users",
    response_model=PaginatedUserResponse,
    summary="Get all parish users for a diocese",
)
async def retrieve_all_users_belonging_to_diocese_parishes(
    db: Session = Depends(get_db),
    diocese_id: Optional[UUID] = Query(None),
    parish_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
):
    try:
        offset = (page - 1) * page_size

        # model relationship connector
        query = (
            db.query(User)
            .join(User.parish)
            .join(Parish.diocese)
            .options(joinedload(User.role))
            .filter(Diocese.id == diocese_id)
        )

        # parish filter
        if parish_id:
            query = query.filter(Parish.id == parish_id)

        # sort parameter
        if sort_by and hasattr(User, sort_by):
            column = getattr(User, sort_by)
            logger.info("Sorting by sort parameter...")
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            logger.info("Sorting by default: created_at desc...")
            query = query.order_by(User.created_at.desc())

        total_count = query.count()
        users = query.offset(offset).limit(page_size).all()

        from api.users_router import serialize_users

        return {
            "items": serialize_users(users),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "pages": (total_count + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as db_err:
        logger.error(
            f" Database error while retrieving diocese parishes users!: {str(db_err)}"
        )
        raise HTTPException(
            status_code=500, detail="Database error occurred while retrieving users!"
        )

    except Exception as e:
        logger.error(f" Unexpected error retrieving diocese parishes users!: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Unexpected error occurred while retrieving users!"
        )
