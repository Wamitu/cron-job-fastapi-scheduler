from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from api.serializers import (
    serialize_certificate,
    serialize_certificates,
)
from db.models.certificate import Certificate
from db.models.parish import Parish
from db.models.sacrament import SacramentRecord
from db.models.user import User
from db.session import get_db
from schemas.certificate_schema import (
    CertificateCreate,
    CertificateDetails,
    CertificateUpdate,
    PaginatedCertificateResponse,
)
from sqlalchemy.exc import SQLAlchemyError
from log_config import logger
from schemas.notification_schema import NotificationType
from services.auth_service import (
    get_current_user,
)
from services.certificate_service import generate_unique_certificate_number
from sqlalchemy import or_

from services.notification_service import create_notification
from services.user_service import get_user_details

router = APIRouter()


# get data count
@router.get(
    "/count",
    summary="Fetch all count of certificate records (optionally filtered by parish)",
)
async def count_parish_certificate_records(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve all certificate record count...")
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

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view certificate count.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view certificate count from another parish.",
                )

        # certificate query
        query = db.query(Certificate)

        # parish filter
        if parish_id:
            query = query.filter(Certificate.parish_id == parish_id)

        total_count = query.count()
        logger.info("200 | Certificate count fetched!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | DB error during certificate count!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while counting certificate records!",
        )

    except Exception:
        db.rollback()
        logger.error("500 | Unexpected error during certificate count!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while counting certificate records!",
        )


# retrieve all certificates
@router.get(
    "/all",
    response_model=PaginatedCertificateResponse,
    summary="Fetch all certificate records (optionally filtered by parish)!",
)
async def retrieve_all_certificates(
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
        logger.info("Retrieving all certificates...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view certificate data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view certificate data from another parish.",
                )

        offset = (page - 1) * page_size

        # model relationship connector
        query = db.query(Certificate).options(
            joinedload(Certificate.parish),
            joinedload(Certificate.sacrament_record),
            joinedload(Certificate.generated_by_user),
        )

        # archive filter
        if is_archived is None:
            query = query.filter(Certificate.is_archived == False)
        else:
            query = query.filter(Certificate.is_archived == is_archived)

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                logger.warning("404 | Parish not found!")
                raise HTTPException(status_code=404, detail="Parish not found!")
            query = query.filter(Certificate.parish_id == parish_id)

        # search parameter
        if search:
            query = query.filter(
                or_(
                    Certificate.certificate_no.ilike(f"%{search}%"),
                )
            )

        # sort parameter
        if sort_by:
            if hasattr(Certificate, sort_by):
                sort_column = getattr(Certificate, sort_by)
                query = query.order_by(
                    sort_column.desc() if sort_order == "desc" else sort_column.asc()
                )
            else:
                logger.warning("400 | Invalid sort_by field!")
                raise HTTPException(status_code=400, detail="Invalid sort_by field!")

        total_count = query.count()
        certificates = query.offset(offset).limit(page_size).all()

        logger.info("200 | Certificates retrieved successfully!")
        return {
            "items": serialize_certificates(certificates),
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
        logger.error("500 | DB error during certificate retrieval!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while retrieving certificates!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"500 | Unexpected error during all certificate data query! {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# create certificate
@router.post(
    "/create",
    response_model=CertificateDetails,
    summary="Create a new certificate for a member",
)
async def create_certificate(
    certificate_create: CertificateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to create a certificate...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title

        # role and parish based check
        if role_title == "Priest":
            if user.parish_id != certificate_create.parish_id:
                logger.info(
                    "403 | User not allowed to create certificate in this parish!"
                )
                raise HTTPException(
                    status_code=403,
                    detail="You cannot create a certificate for another parish.",
                )

        title_lower = certificate_create.certificate_for.lower()

        # duplicate data check
        existing_certificate = (
            db.query(Certificate)
            .filter(func.lower(Certificate.certificate_for) == title_lower)
            .first()
        )

        if existing_certificate:
            logger.warning("400 | Certificate already exists!")
            raise HTTPException(
                status_code=400,
                detail="Certificate already exists for this member!",
            )

        unique_cert_no = generate_unique_certificate_number(db)
        db_certificate = Certificate(
            **certificate_create.model_dump(),
            certificate_no=unique_cert_no,
            generated_by=user.id,
        )
        db.add(db_certificate)
        db.commit()
        db.refresh(db_certificate)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message="Certificate record created successfully!",
        )

        logger.info("201 | Certificate record created successfully!")
        return serialize_certificate(db_certificate)

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | DB error during certificate creation!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while creating the certificate!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during certificate creation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while creating the certificate!",
        )


# get certificate details
@router.get(
    "/details/{certificate_id}",
    response_model=CertificateDetails,
    summary="Retrieve certificate details by ID",
)
async def retrieve_certificate_details(
    certificate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve certificate details...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title

        db_certificate = (
            db.query(Certificate)
            .options(
                joinedload(Certificate.parish),
                joinedload(Certificate.sacrament_record),
                joinedload(Certificate.generated_by_user),
            )
            .filter(Certificate.id == certificate_id)
            .first()
        )

        if db_certificate is None:
            logger.warning("404 | Certificate not found!")
            raise HTTPException(status_code=404, detail="Certificate not found!")

        # role and parish based check
        if role_title == "Priest":
            if user.parish_id != db_certificate.parish_id:
                logger.info(
                    "403 | User not allowed to view certificate in this parish!"
                )
                raise HTTPException(
                    status_code=403,
                    detail="You cannot view a certificate for another parish.",
                )

        logger.info("200 | Certificate retrieved successfully!")
        return db_certificate

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | DB error during certificate retrieval!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while retrieving the certificate!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during certificate retrieval!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while retrieving the certificate!",
        )


# update certificate
@router.put(
    "/update/{certificate_id}",
    response_model=CertificateDetails,
    summary="Update an existing certificate by ID",
)
async def update_certificate(
    certificate_id: UUID,
    certificate_update: CertificateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to update an existing certificate...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        db_certificate = (
            db.query(Certificate).filter(Certificate.id == certificate_id).first()
        )

        if not db_certificate:
            logger.warning("404 | Certificate not found!")
            raise HTTPException(status_code=404, detail="Certificate not found!")

        role_title = user.role.title

        # role and parish based check
        if role_title == "Priest":
            if user.parish_id != db_certificate.parish_id:
                logger.info(
                    "403 | User not allowed to create certificate in this parish!"
                )
                raise HTTPException(
                    status_code=403,
                    detail="You cannot create a certificate for another parish.",
                )

        update_data = certificate_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_certificate, key, value)

        db.commit()
        db.refresh(db_certificate)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Certificate record updated successfully!",
        )

        logger.info("200 | Certificate record updated successfully!")
        return db_certificate

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | DB error during certificate update", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while updating the certificate.",
        )

    except Exception:
        db.rollback()
        logger.error("500 | Unexpected error during certificate update", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while updating the certificate.",
        )


# archive certificate
@router.post(
    "/archive/{certificate_id}",
    summary="Archive certificate",
)
async def archive_certificate(
    certificate_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive certificate...")
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
                detail="Priests must specify a parish_id to archive certificate data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive certificate data from another parish.",
            )

    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found!")
    certificate.is_archived = True
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return {"message": "Certificate successfuly archived!"}


# unarchive certificate
@router.post("/unarchive/{certificate_id}", summary="Unarchive certificate")
async def unarchive_certificate(
    certificate_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive certificate data...")
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
                detail="Priests must specify a parish_id to archive certificate data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive certificate data from another parish.",
            )
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found!")
    certificate.is_archived = False
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return {"message": "Certificate successfuly unarchived!"}


# generate sacrament record certificate
@router.post(
    "/generate-certificate",
    summary="Generate a certificate for a sacrament record whose certificate has not been generated",
)
async def generate_certificate_for_person(
    sacrament_record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info(f"Attempting to generate certificate...")

        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        # Find sacrament record with matching name and certificate not generated
        record = (
            db.query(SacramentRecord)
            .filter(SacramentRecord.id == sacrament_record_id)
            .first()
        )

        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"No sacrament record found without a certificate.",
            )

        if record.generate_certificate == True:
            raise HTTPException(
                status_code=409, detail="Record already has an existing certificate!"
            )

        sacrament_record_sacrament_name = record.sacrament.name

        name_lower = sacrament_record_sacrament_name.lower()

        if name_lower == "baptism":
            certificate_for = record.data.get("name")
        elif name_lower == "confirmation":
            certificate_for = record.data.get("candidateName")
        elif name_lower == "marriage":
            groom = record.data.get("groomName")
            bride = record.data.get("brideName")
            if groom and bride:
                certificate_for = f"{groom} & {bride}"
            else:
                certificate_for = groom or bride
        elif name_lower == "first communion":
            certificate_for = record.data.get("childName")

        else:
            certificate_for = "Unnamed"

        # Create the certificate
        certificate = Certificate(
            parish_id=record.parish_id,
            sacrament_record_id=record.id,
            certificate_for=certificate_for,
            certificate_no=generate_unique_certificate_number(db),
            generated_by=user.id,
            is_archived=False,
        )
        db.add(certificate)

        # Mark the record as having generated a certificate
        record.generate_certificate = True
        db.commit()
        db.refresh(certificate)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Certificate created successfully!",
        )

        logger.info(f"201 | Certificate successfully generated!")

        return {
            "message": "Certificate generated successfully",
            "certificate": certificate,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during certificate generation!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")
    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during certificate generation!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")
