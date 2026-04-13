from decimal import Decimal
import traceback
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from api.serializers import serialize_sacrament_records
from db.models.certificate import Certificate
from db.models.parish import Parish
from db.models.sacrament import Sacrament, SacramentRecord
from db.models.user import User
from db.session import get_db
from schemas.notification_schema import NotificationType
from schemas.sacrament_record_schema import (
    SacramentRecordCreate,
    SacramentRecordDetails,
    SacramentRecordUpdate,
    PaginatedSacramentRecordResponse,
)
from log_config import logger
from services.auth_service import (
    get_current_user,
)
from services.certificate_service import generate_unique_certificate_number
from services.notification_service import create_notification
from utils.reference_number_generator import generate_sacrament_record_reference_number
from services.user_service import get_user_details

router = APIRouter()


# retrieve db/parish sacrament records count with parish filter
@router.get(
    "/count",
    summary="Fetch all count of sacrament record records (optionally filtered by parish)",
)
async def count_sacrament_records(
    parish_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Retrieving all sacrament record count...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view sacrament record count.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view sacrament record count from another parish.",
                )

        if parish_id:
            logger.info(f" Filtering count by parish...")
            query = db.query(SacramentRecord).filter(
                SacramentRecord.parish_id == parish_id
            )
        else:
            logger.info(" Counting sacrament records across all parishes")
            query = db.query(SacramentRecord)

        total_count = query.count()
        logger.info("200 | Scrament records count fetched successfully!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during sacrament record count!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacrament record count!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retrieve db/parish sacrament record count with parish filter
@router.get(
    "/all",
    response_model=PaginatedSacramentRecordResponse,
    summary="Fetch all sacrament record records (optionally filtered by parish)",
)
async def retrieve_all_sacrament_records(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID"),
    is_archived: Optional[bool] = None,
    is_settled: Optional[bool] = None,
    sacrament_id: Optional[UUID] = Query(None),
    sacrament_name: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Retrieving all sacrament records...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        # fetch user role title
        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view sacrament record data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view collection data from another parish.",
                )

        offset = (page - 1) * page_size

        query = db.query(SacramentRecord).options(
            joinedload(SacramentRecord.sacrament), joinedload(SacramentRecord.parish)
        )

        # archive filter
        if is_archived is None:
            query = query.filter(SacramentRecord.is_archived == False)
        else:
            query = query.filter(SacramentRecord.is_archived == is_archived)

        # settled filter
        if is_settled is None:
            query = query.filter(SacramentRecord.is_settled == False)
        else:
            query = query.filter(SacramentRecord.is_settled == is_settled)

        # parish filter
        if parish_id:
            logger.debug(f"Filter by parish_id: {parish_id}")
            query = query.filter(SacramentRecord.parish_id == parish_id)

        # search parameter
        if search:
            logger.debug(f"Searching by name: {search}")
            query = query.filter(
                func.lower(SacramentRecord.name).ilike(f"%{search.lower()}%")
            )

        # sacrament id parameter
        if sacrament_id:
            logger.debug(f"Filter by sacrament_id: {sacrament_id}")
            query = query.filter(SacramentRecord.sacrament_id == sacrament_id)

        # sacrament name parameter
        if sacrament_name:
            logger.debug(f"Filter by sacrament name: {sacrament_name}")
            query = query.join(Sacrament).filter(
                func.lower(Sacrament.name).ilike(f"%{sacrament_name.lower()}%")
            )

        # sort parameter
        if sort_by and hasattr(SacramentRecord, sort_by):
            logger.debug(f"Sorting by {sort_by} ({sort_order})")
            sort_column = getattr(SacramentRecord, sort_by)
            query = query.order_by(
                sort_column.desc() if sort_order == "desc" else sort_column.asc()
            )
        else:
            query = query.order_by(SacramentRecord.created_at.desc())

        total_count = query.count()
        sacrament_records = query.offset(offset).limit(page_size).all()

        logger.info("Fetched sacrament records successfully!")

        return {
            "items": serialize_sacrament_records(sacrament_records),
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
            "500 | Database error during sacrament record data query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception as e:
        db.rollback()
        logger.error(
            f"500 | Unexpected error during all sacrament record data query! {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# create sacrament record
@router.post(
    "/create",
    summary="Create a sacrament record, linked to a parish",
)
async def create_sacrament_record(
    sacrament_record_create: SacramentRecordCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    try:
        logger.info("Attempting to create a sacramemt record...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        db_parish = (
            db.query(Parish)
            .filter(Parish.id == sacrament_record_create.parish_id)
            .first()
        )
        if not db_parish:
            raise HTTPException(status_code=404, detail="Parish not found")

        db_sacrament = (
            db.query(Sacrament)
            .filter(Sacrament.id == sacrament_record_create.sacrament_id)
            .first()
        )
        if not db_sacrament:
            raise HTTPException(status_code=404, detail="Sacrament not found")

        data = sacrament_record_create.data or {}

        if db_sacrament.name.lower() == "baptism":
            idno = str(data.get("idno")).strip() if data.get("idno") else None
            parent_idno = (
                str(data.get("parent_idno")).strip()
                if data.get("parent_idno")
                else None
            )
            name = str(data.get("name")).strip() if data.get("name") else None

            if not idno and not parent_idno:
                raise HTTPException(
                    status_code=400,
                    detail="Either idno or parent_idno is required for Baptism.",
                )

            if name and (idno or parent_idno):
                base_filters = [
                    SacramentRecord.parish_id == sacrament_record_create.parish_id,
                    SacramentRecord.sacrament_id
                    == sacrament_record_create.sacrament_id,
                    func.lower(cast(SacramentRecord.data["name"], String))
                    == name.lower(),
                ]

                id_filters = []
                if idno:
                    id_filters.append(
                        cast(SacramentRecord.data["idno"], String) == str(idno)
                    )
                if parent_idno:
                    id_filters.append(
                        cast(SacramentRecord.data["parent_idno"], String)
                        == str(parent_idno)
                    )

                existing = (
                    db.query(SacramentRecord)
                    .filter(*base_filters)
                    .filter(or_(*id_filters))
                    .first()
                )

                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail="A similar sacrament record already exists.",
                    )

        elif db_sacrament.name.lower() == "marriage":
            groomName = (
                str(data.get("groomName")).strip() if data.get("groomName") else None
            )
            brideName = (
                str(data.get("brideName")).strip() if data.get("brideName") else None
            )

            if groomName and brideName:
                base_filters = [
                    SacramentRecord.parish_id == sacrament_record_create.parish_id,
                    SacramentRecord.sacrament_id
                    == sacrament_record_create.sacrament_id,
                    func.lower(cast(SacramentRecord.data["groomName"], String))
                    == groomName.lower(),
                    func.lower(cast(SacramentRecord.data["brideName"], String))
                    == brideName.lower(),
                ]

                existing = db.query(SacramentRecord).filter(*base_filters).first()
                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail="A similar sacrament record already exists.",
                    )

        elif db_sacrament.name.lower() == "confirmation":
            candidateName = (
                str(data.get("candidateName")).strip()
                if data.get("candidateName")
                else None
            )
            if candidateName:
                base_filters = [
                    SacramentRecord.parish_id == sacrament_record_create.parish_id,
                    SacramentRecord.sacrament_id
                    == sacrament_record_create.sacrament_id,
                    func.lower(cast(SacramentRecord.data["candidateName"], String))
                    == candidateName.lower(),
                ]

                existing = db.query(SacramentRecord).filter(*base_filters).first()
                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail="A similar sacrament record already exists.",
                    )

        elif db_sacrament.name.lower() == "firstcommunion":
            childName = (
                str(data.get("childName")).strip() if data.get("childName") else None
            )
            if childName:
                base_filters = [
                    SacramentRecord.parish_id == sacrament_record_create.parish_id,
                    SacramentRecord.sacrament_id
                    == sacrament_record_create.sacrament_id,
                    func.lower(cast(SacramentRecord.data["childName"], String))
                    == childName.lower(),
                ]

                existing = db.query(SacramentRecord).filter(*base_filters).first()
                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail="A similar sacrament record already exists.",
                    )

        fee_amount = Decimal(db_sacrament.fee_amount)
        reference = generate_sacrament_record_reference_number(
            sacrament_name=db_sacrament.name, db=db
        )

        new_sacrament_record = SacramentRecord(
            reference_no=reference,
            parish_id=sacrament_record_create.parish_id,
            sacrament_id=sacrament_record_create.sacrament_id,
            data=data,
            generate_certificate=sacrament_record_create.generate_certificate,
            fee_amount=fee_amount,
            outstanding_balance=fee_amount,
            created_by=user.id,
        )

        db.add(new_sacrament_record)
        db.commit()
        db.refresh(new_sacrament_record)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message="Sarament record created successfully!",
        )

        logger.info("201 | Sacrament record created successfully!")

        certificate_for = None
        certificate = None

        if new_sacrament_record.generate_certificate:
            record = (
                db.query(SacramentRecord)
                .options(joinedload(SacramentRecord.sacrament))
                .filter(SacramentRecord.id == new_sacrament_record.id)
                .first()
            )

            if record and record.sacrament:
                name_lower = record.sacrament.name.lower()

                if name_lower == "baptism":
                    certificate_for = record.data.get("childName")
                elif name_lower == "confirmation":
                    certificate_for = record.data.get("candidateName")
                elif name_lower == "marriage":
                    groom = record.data.get("groomName")
                    bride = record.data.get("brideName")
                    certificate_for = (
                        f"{groom} & {bride}" if groom and bride else (groom or bride)
                    )
                elif name_lower == "first communion":
                    certificate_for = record.data.get("childName")
                else:
                    certificate_for = "Unknown"

                certificate_for = certificate_for

                if certificate_for:
                    certificate = Certificate(
                        parish_id=record.parish_id,
                        sacrament_record_id=record.id,
                        certificate_for=certificate_for,
                        certificate_no=generate_unique_certificate_number(db),
                        generated_by=user.id,
                        is_archived=False,
                    )
                    db.add(certificate)
                    db.commit()
                    db.refresh(certificate)

                    create_notification(
                        db=db,
                        user_id=user.id,
                        parish_id=user.parish_id,
                        notification_type=NotificationType.info,
                        message=f"Certificate created for {certificate_for} successfully!",
                    )
                    logger.info("201 | Certificate created successfully!")
            else:
                logger.warning("Skipping certificate: sacrament relationship not found")

        return {
            "message": "Sacrament record created successfully!",
            "sacrament_record": new_sacrament_record,
            "certificate": certificate,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        error_msg = str(e.__cause__ or e)
        logger.error(
            f"500 | Database error during sacrament record creation! {error_msg}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Database error: {error_msg}")

    except Exception as e:
        db.rollback()
        tb = traceback.format_exc()
        logger.error(
            f"500 | Unexpected error during sacrament record creation! {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}\n{tb}")


# get sacrament details
@router.get(
    "/details/{sacrament_record_id}",
    response_model=SacramentRecordDetails,
    summary="Get details of an existing sacrament record in the system",
)
async def get_sacrament_record_details(
    sacrament_record_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        logger.debug("Fetching sacrament record details...")

        db_sacrament_record = (
            db.query(SacramentRecord)
            .options(
                joinedload(SacramentRecord.parish),
                joinedload(SacramentRecord.sacrament),
                joinedload(SacramentRecord.created_by_user),
            )
            .filter(SacramentRecord.id == sacrament_record_id)
            .first()
        )

        if not db_sacrament_record:
            logger.warning(f"Sacrament record not found!")
            raise HTTPException(status_code=404, detail="Sacrament record not found!")

        logger.info("Sacrament record retrieved successfully!")
        return db_sacrament_record

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during sacrament record data query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacrament record data query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# update sacrament details
@router.put(
    "/update/{sacrament_record_id}",
    response_model=SacramentRecordDetails,
    summary="Update an existing sacrament record",
)
async def update_sacrament_record_details(
    sacrament_record_id: UUID,
    sacrament_record_update: SacramentRecordUpdate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    try:
        logger.info("Attempting to update a sacramemt record...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")
        db_sacrament_record = (
            db.query(SacramentRecord)
            .filter(SacramentRecord.id == sacrament_record_id)
            .first()
        )

        if not db_sacrament_record:
            logger.warning(f"Sacrament record not found!")
            raise HTTPException(status_code=404, detail="Sacrament record not found!")

        update_data = sacrament_record_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_sacrament_record, key, value)

        db.commit()
        db.refresh(db_sacrament_record)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Sacrament record updated and notification sent successfully!",
        )

        logger.info(
            "200 | Sacrament record updated and notification sent successfully!"
        )
        return db_sacrament_record

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during sacrament record data update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacrament record data update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# archive sacrament record
@router.post(
    "/archive/{sacrament_record_id}",
    summary="Archive sacrament record",
)
async def archive_sacrament_record(
    sacrament_record_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive sacrament record data...")
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
                detail="Priests must specify a parish_id to archive sacrament record data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive sacrament record data from another parish.",
            )

    sacrament_record = (
        db.query(SacramentRecord)
        .filter(SacramentRecord.id == sacrament_record_id)
        .first()
    )
    if not sacrament_record:
        raise HTTPException(status_code=404, detail="sacrament record not found!")
    sacrament_record.is_archived = True
    db.add(sacrament_record)
    db.commit()
    db.refresh(sacrament_record)
    return {"message": "Sacrament record successfuly archived!"}


# unarchive sacrament record
@router.post("/unarchive/{sacrament_record_id}", summary="Unarchive sacrament record")
async def unarchive_sacrament_record(
    sacrament_record_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive sacrament record data...")
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
                detail="Priests must specify a parish_id to unarchive sacrament record data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to unarchive sacrament record data from another parish.",
            )
    sacrament_record = (
        db.query(SacramentRecord)
        .filter(SacramentRecord.id == sacrament_record_id)
        .first()
    )
    if not sacrament_record:
        raise HTTPException(status_code=404, detail="Sacrament record not found!")
    sacrament_record.is_archived = False
    db.add(sacrament_record)
    db.commit()
    db.refresh(sacrament_record)
    return {"message": "Sacrament record successfuly unarchived!"}
