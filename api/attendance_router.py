from typing import Optional
from uuid import UUID
from api.serializers import serialize_attendance_records
from db.models.user import User
from log_config import logger
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload
from db.models.attendance import Attendance
from db.models.parish import Parish
from db.session import get_db
from middleware.feature_middleware import require_feature
from middleware.role_middleware import require_roles_by_titles
from schemas.attendance_schema import (
    AttendanceCreate,
    AttendanceDetails,
    AttendanceUpdate,
    PaginatedAttendanceResponse,
)
from schemas.notification_schema import NotificationType
from services.auth_service import (
    get_current_user,
)
from services.notification_service import create_notification
from services.user_service import get_user_details

router = APIRouter()


# fetch all attendance records count (optionally filtered by parish)
@router.get("/count")
@require_roles_by_titles("Bishop")
@require_feature("attendance_tracking")
async def count_attendance_records(
    parish_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),
):
    # logged_in_user = get_user_details(db, current_user)
    # if not logged_in_user:
    #     raise HTTPException(status_code=404, detail="User not found!")

    # user_role = logged_in_user.role.title
    # if user_role == "Priest":
    #     if not parish_id:
    #         raise HTTPException(
    #             status_code=400, detail="Priests must pass in parish id filter!"
    #         )
    #     if parish_id != logged_in_user.parish_id:
    #         raise HTTPException(
    #             status_code=401,
    #             detail="You are not authorized to view details for another parish other than own parish!",
    #         )
    query = db.query(Attendance)
    if parish_id:
        query = query.filter(Attendance.parish_id == parish_id)

    total_count = query.count()
    return {"total": total_count}


# fetch all attendance records (optionally filtered by parish)
@router.get(
    "/all",
    response_model=PaginatedAttendanceResponse,
    summary="Fetch all attendance records (optionally filtered by parish)",
)
async def fetch_all_attendance_records(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    is_archived: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to fetch all attendance records...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                raise HTTPException(status_code=404, detail="Parish not found!")

            query = db.query(Attendance).filter(Attendance.parish_id == parish_id)
        else:
            query = db.query(Attendance)

        # model relationship connector
        query = db.query(Attendance).options(
            joinedload(Attendance.parish), joinedload(Attendance.marked_by_user)
        )

        # archive filter
        if is_archived is None:
            query = query.filter(Attendance.is_archived == False)
        else:
            query = query.filter(Attendance.is_archived == is_archived)

        # search parameter
        if search:
            query = query.filter(
                or_(
                    Attendance.event_title.ilike(f"%{search}%"),
                    Attendance.event_type.ilike(f"%{search}%"),
                )
            )

        # sort parameter
        if sort_by and hasattr(Attendance, sort_by):
            column = getattr(Attendance, sort_by)
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            query = query.order_by(Attendance.created_at.desc())

        # attendance record query
        total_count = query.count()

        # pagination
        offset = (page - 1) * page_size
        attendance_records = query.offset(offset).limit(page_size).all()

        logger.info("200 | Attendance records fetched successfully!")

        return {
            "items": serialize_attendance_records(attendance_records),
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
            "500 | Database error during all attendance record data query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception as e:
        db.rollback()
        logger.error(
            f"500 | Unexpected error during all attendance record data query! {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# create attendance record
@router.post(
    "/create",
    response_model=AttendanceDetails,
    summary="Create an attendance record for a parish",
)
async def create_attendance_record(
    attendance_record_create: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        # dullicates check
        title_lower = attendance_record_create.event_title.lower()
        existing_attendance_record = (
            db.query(Attendance)
            .filter(func.lower(Attendance.event_title) == title_lower)
            .first()
        )

        # data comparison
        if existing_attendance_record:
            logger.warning("409 | Attendance record already exists!")
            raise HTTPException(
                status_code=409,
                detail="Attendance record already exists!",
            )

        new_attendance_record = Attendance(
            **attendance_record_create.model_dump(),
            marked_by=user.id,
        )
        db.add(new_attendance_record)
        db.commit()
        db.refresh(new_attendance_record)

        # create notification
        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Attendance record created successfully!",
        )

        logger.info("201 | New attendance record created successfully!")
        return new_attendance_record

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during attendance record data creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during attendance record data creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# fetch attendance record details
@router.get(
    "/details/{record_id}",
    response_model=PaginatedAttendanceResponse,
    summary="Fetch details of an existing attendance record",
)
async def retrieve_atendance_record_details(
    record_id: UUID,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    try:
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        offset = (page - 1) * page_size

        query = db.query(Attendance).filter(Attendance.id == record_id)
        total_count = query.count()

        if total_count == 0:
            logger.warning("404 | No attendance record found!")
            raise HTTPException(status_code=404, detail="No attendance record found!")

        records = query.offset(offset).limit(page_size).all()

        logger.info("200 | Attendance record retrieved!")
        return {
            "items": serialize_attendance_records(records),
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
            "500 | Database error during attendance record details query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during attendance record details query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# update attendance record
@router.put(
    "/update/{attendance_record_id}",
    response_model=AttendanceDetails,
    summary="Update an existing attendance record",
)
async def update_attendance_record(
    attendance_record_id: UUID,
    attendace_record_update: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        parish_name = user.parish.parish_data.get("parish_name")
        db_attendance_record = (
            db.query(Attendance).filter(Attendance.id == attendance_record_id).first()
        )

        if not db_attendance_record:
            logger.warning("404 | Attendance record not found!")
            raise HTTPException(status_code=404, detail="Attendance record not found!")

        update_data = attendace_record_update.dict(exclude_unset=True)

        # Determine what the updated event title will be
        new_event_title = update_data.get(
            "event_title", db_attendance_record.event_title
        )
        new_event_type = update_data.get("event_type", db_attendance_record.event_type)

        # restrict duplicate event title
        duplicate_check = (
            db.query(Attendance)
            .filter(
                Attendance.id != attendance_record_id,
                Attendance.event_title == new_event_title,
                Attendance.event_type == new_event_type,
            )
            .first()
        )

        if duplicate_check:
            logger.warning(
                "409 | Duplicate attendance record with this event title exists!"
            )
            raise HTTPException(
                status_code=409,
                detail="An attendance record with this event title already exists!",
            )

        # proceed to update record
        for key, value in update_data.items():
            setattr(db_attendance_record, key, value)

        db.commit()
        db.refresh(db_attendance_record)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Attendance record updated successfully for parish: {parish_name}",
        )

        logger.info(
            "201 | Attendance record updated and notification sent! successfully!"
        )
        return db_attendance_record

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during attendance record data update!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during attendance record data update!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# archive attendance record
@router.post(
    "/archive/{attendance_record_id}",
    summary="Archive attendance record",
)
async def archive_attendance_record(
    attendance_record_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    try:
        # current user check
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

        # user role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to archive attendance data.",
                )

            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to archive attendance data from another parish.",
                )

        attendance_record = (
            db.query(Attendance).filter(Attendance.id == attendance_record_id).first()
        )
        if not attendance_record:
            raise HTTPException(status_code=404, detail="Attendance record not found!")
        attendance_record.is_archived = True
        db.add(attendance_record)
        db.commit()
        db.refresh(attendance_record)
        return {"message": "Attendance record successfuly archived!"}

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during attendance record data update!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during attendance record data update!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# unarchive attendance record
@router.post("/unarchive/{attendance_record_id}", summary="Unarchive attendance record")
async def unarchive_attendance_record(
    attendance_record_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    try:
        # current user check
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

        # user role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to unarchive attendance data.",
                )

            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to unarchive attendance data from another parish.",
                )
        attendance_record = (
            db.query(Attendance).filter(Attendance.id == attendance_record_id).first()
        )
        if not attendance_record:
            raise HTTPException(status_code=404, detail="Attendance record not found!")
        attendance_record.is_archived = False
        db.add(attendance_record)
        db.commit()
        db.refresh(attendance_record)
        return {"message": "Attendance record successfuly unarchived!"}

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during attendance record data update!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during attendance record data update!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )
