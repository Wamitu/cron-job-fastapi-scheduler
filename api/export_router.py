import csv
from datetime import datetime
from io import StringIO
import io
import re
from typing import Optional
from uuid import UUID
from fastapi.responses import StreamingResponse
from api.serializers import (
    export_attendance_records,
    export_certificates,
    export_collections,
    export_fund_projects,
    export_invited_users,
    export_members,
    export_parishes,
    export_parish_subscriptions,
    export_roles,
    export_sacrament_records,
    export_sacraments,
    export_subscription_payments,
    export_users,
)
from db.models.certificate import Certificate
from db.models.collection import Collection
from db.models.fund_project import FundProject
from db.models.member import Member
from db.models.parish_subscription import ParishSubscription, SubscriptionPayment
from db.models.role import Role
from db.models.sacrament import Sacrament, SacramentRecord
from db.models.user import User
from db.models.user_invite import InvitedUser
from log_config import logger
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload
from db.models.attendance import Attendance
from db.models.parish import Parish
from db.session import get_db
from schemas.parish_subscription_schema import SubscriptionStatus
from services.auth_service import (
    get_current_user,
)
from services.user_service import get_user_details

router = APIRouter()


# export attendance records data as csv
@router.get(
    "/attendance-records/csv",
    summary="Export attendance records as CSV",
)
async def export_attendance_records_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(
        None,
        description="Parish ID filter (required for Priest, optional for System Admin)",
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # user role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export attendance datafor their parish only!.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export attendance data from another parish!",
                )

        # model relationship connector
        query = db.query(Attendance).options(
            joinedload(Attendance.parish), joinedload(Attendance.marked_by_user)
        )

        parish_name = None
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                raise HTTPException(status_code=404, detail="Parish not found!")
            parish_name = parish.parish_data.get("parish_name")
            query = query.filter(Attendance.parish_id == parish_id)

        # attendance records query
        attendance_records = query.all()

        records = export_attendance_records(attendance_records)

        # csv generator
        output = StringIO()

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic filename
        if role_title == "Priest" and parish_name:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"attendance_records_{safe_name}.csv"
        else:
            filename = "attendance_records_iparish.csv"

        logger.info("200 | Attendance records exported successfully to CSV!")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during attendance record data export!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during attendance record data export!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export certificate data as csv
@router.get(
    "/certificates/csv",
    summary="Export certificates as CSV",
)
async def export_certificates_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(
        None,
        description="Parish ID filter (required for Priest, optional for System Admin)",
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export certificate data as CSV...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export certificates.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export certificates from another parish.",
                )

        # model relationship connector
        query = db.query(Certificate).options(
            joinedload(Certificate.parish),
            joinedload(Certificate.sacrament_record),
            joinedload(Certificate.generated_by_user),
        )

        parish_name = None
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                raise HTTPException(status_code=404, detail="Parish not found!")
            parish_name = parish.parish_data.get("parish_name")
            query = query.filter(Certificate.parish_id == parish_id)

        # certificate query
        certificates = query.all()

        records = export_certificates(certificates)

        # csv generator
        output = StringIO()

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic filename
        if role_title == "Priest" and parish_name:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"certificates_{safe_name}.csv"
        else:
            filename = "certificates_iparish.csv"

        logger.info("200 | Certificate records exported successfully to CSV!")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during certificate data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during certificate data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export collection data as csv
@router.get(
    "/collections/csv",
    summary="Export collections as CSV",
)
async def export_collections_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(
        None,
        description="Parish ID filter (required for Priest, optional for System Admin)",
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export collection data as CSV...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export collections.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export collections from another parish.",
                )

        # model relationship connector
        query = db.query(Collection).options(joinedload(Collection.recorded_by_user))

        parish_name = None
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                raise HTTPException(status_code=404, detail="Parish not found!")
            parish_name = parish.parish_data.get("parish_name")
            query = query.filter(Collection.parish_id == parish_id)

        # collection query
        collections = query.all()

        records = export_collections(collections)

        # csv generator
        output = StringIO()

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic Filename
        if role_title == "Priest" and parish_name:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"collections_{safe_name}.csv"
        else:
            filename = "collections.csv"

        logger.info("200 | Collection records exported successfully to CSV!")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during collection data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during collection data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export fund projects data as csv
@router.get(
    "/fund-projects/csv",
    summary="Export fund projects as CSV",
)
async def export_fund_projects_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(
        None,
        description="Parish ID filter (required for Priest, optional for System Admin)",
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export fund project data as CSV...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export fund projects.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export fund projects from another parish.",
                )

        # model relationship connector
        query = db.query(FundProject).options(joinedload(FundProject.parish))

        parish_name = None
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                raise HTTPException(status_code=404, detail="Parish not found")
            parish_name = parish.parish_data.get("parish_name")
            query = query.filter(FundProject.parish_id == parish_id)

        # fund project query
        fund_projects = query.all()

        records = export_fund_projects(fund_projects)

        # csv generator
        output = StringIO()

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic Filename
        if role_title == "Priest" and parish_name:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"fund_projects_{safe_name}.csv"
        else:
            filename = "fund_projects_iparish.csv"

        logger.info("200 | Fund project records exported successfully to CSV!")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during fund project data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during fund project data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export member data as csv
@router.get(
    "/members/csv",
    summary="Export members as CSV",
)
async def export_members_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(
        None,
        description="Parish ID filter (required for Priest, optional for System Admin)",
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export member data as CSV...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # 🔒 Restriction for Priest
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export members.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export members from another parish.",
                )

        # no model relationship connector
        query = db.query(Member).options(joinedload(Member.parish))

        parish_name = None
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                raise HTTPException(status_code=404, detail="Parish not found!")
            parish_name = parish.parish_data.get("parish_name")
            query = query.filter(Member.parish_id == parish_id)

        # member query
        members = query.all()

        records = export_members(members)

        # csv generator
        output = io.StringIO()

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic filename
        if role_title == "Priest" and parish_name:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"members_{safe_name}.csv"
        else:
            filename = "members_iparish.csv"

        logger.info("200 | Member records exported successfully to CSV!")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during member data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during member data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export parish subscriptions data as csv
@router.get(
    "/parish-subscriptions/csv",
    summary="Export parish subscriptions as CSV",
)
async def export_parish_subscriptions_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[str] = Query(
        None, description="Parish ID filter (required for Priest)"
    ),
    status: Optional[SubscriptionStatus] = Query(None),
    is_paid: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export parish subscription data as CSV...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                parish_id = str(user.parish_id)
            elif parish_id != str(user.parish_id):
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export subscriptions from another parish.",
                )

        # model relationship connector
        query = db.query(ParishSubscription).options(
            joinedload(ParishSubscription.parish),
            joinedload(ParishSubscription.subscription),
            joinedload(ParishSubscription.next_plan),
        )

        # parish filter
        if parish_id:
            query = query.filter(ParishSubscription.parish_id == parish_id)
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            parish_name = parish.parish_data.get("parish_name") if parish else None
        else:
            parish_name = None

        # parish subscription status filter
        if status:
            query = query.filter(ParishSubscription.status == status)
        # parish subscription payment status filter
        if is_paid is not None:
            query = query.filter(ParishSubscription.is_paid == is_paid)

        # parish subscription query
        subscriptions = query.all()

        records = export_parish_subscriptions(subscriptions)

        # csv generator
        output = StringIO()

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic Filename
        if role_title == "Priest" and parish_name:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"parish_subscriptions_{safe_name}.csv"
        else:
            filename = "parish_subscriptions_iparish.csv"

        logger.info("200 | Parish subscription records exported successfully to CSV!")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during parish subscription data export!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during parish subscription data export!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export subscription payment data as csv
@router.get(
    "/subscription-payments/csv",
    summary="Export parish subscription payments as CSV",
)
async def export_subscription_payments_csv(
    parish_id: Optional[UUID] = Query(None, description="Filter by parish ID"),
    paid_from: Optional[datetime] = Query(
        None, description="Filter by start of paid_at date"
    ),
    paid_to: Optional[datetime] = Query(
        None, description="Filter by end of paid_at date"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export parish subscription payments data as csv...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                parish_id = user.parish_id
            elif parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export payments from another parish.",
                )

        # model relationship connector
        query = (
            db.query(SubscriptionPayment)
            .join(SubscriptionPayment.parish_subscription)
            .options(
                joinedload(SubscriptionPayment.parish_subscription).joinedload(
                    ParishSubscription.parish
                )
            )
        )

        # parish filter
        if parish_id:
            query = query.filter(ParishSubscription.parish_id == parish_id)
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            parish_name = parish.parish_data.get("parish_name") if parish else None
        else:
            parish_name = None

        # payment duration filter
        if paid_from:
            query = query.filter(SubscriptionPayment.paid_at >= paid_from)
        if paid_to:
            query = query.filter(SubscriptionPayment.paid_at <= paid_to)

        payments = query.order_by(SubscriptionPayment.created_at.desc()).all()

        if not payments:
            raise HTTPException(
                status_code=404, detail="No subscription payments found!"
            )

        records = export_subscription_payments(payments)

        # csv generator
        output = io.StringIO()

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic Filename
        if role_title == "Priest" and parish_name:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"subscription_payments_{safe_name}.csv"
        else:
            filename = "subscription_payments_iparish.csv"

        logger.info("200 | Subscription payment records exported successfully to CSV!")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during subscription payment data export!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during subscription payment data export!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export parish data as csv
@router.get(
    "/parishes/csv",
    summary="Export parishes as CSV",
)
async def export_parishes_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export parish data as csv...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title != "SysAdmin":
            logger.info("401 | You are not authorized to export parish data!")
            raise HTTPException(
                status_code=401,
                detail="You are not authorized to export parish data!",
            )

        # no model relationship connector
        query = db.query(Parish)

        # parish query
        parishes = query.all()

        records = export_parishes(parishes)

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())

        # csv generator
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        filename = "parishes_iparish.csv"

        logger.info("200 | Parish records exported successfully to CSV!")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during parish data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during parish data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export role data as csv
@router.get(
    "/roles/csv",
    summary="Export roles to CSV",
)
async def export_roles_to_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export role data as csv...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title != "SysAdmin":
            logger.info("401 | You are not authorized to export role data!")
            raise HTTPException(
                status_code=401,
                detail="You are not authorized to export role data!",
            )

        # no model relationship connector
        query = db.query(Role)

        # role query
        roles = query.all()

        records = export_roles(roles)

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())

        # csv generator
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        logger.info("200 | Roles exported successfully to CSV")

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=roles.csv"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during role data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during role data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export sacrament record data as csv
@router.get(
    "/sacrament-records/csv",
    summary="Export sacrament records as CSV",
)
async def export_sacrament_records_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(
        None,
        description="Parish ID filter (required for Priest, optional for System Admin)",
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export sacrament record data as CSV...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export sacrament records.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export sacrament records from another parish.",
                )

        # model relationship connector
        query = db.query(SacramentRecord).options(
            joinedload(SacramentRecord.parish),
            joinedload(SacramentRecord.sacrament),
            joinedload(SacramentRecord.created_by_user).joinedload(User.role),
        )

        parish_name = None

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                raise HTTPException(status_code=404, detail="Parish not found!")
            parish_name = parish.parish_data.get("parish_name")
            query = query.filter(SacramentRecord.parish_id == parish_id)

        sacrament_records = query.all()

        records = export_sacrament_records(sacrament_records)

        if not records:
            raise HTTPException(status_code=404, detail="No sacrament records found!")

        fieldnames = list(records[0].keys())

        # csv generator
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic Filename
        if role_title == "Priest" and parish_name:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"sacrament_records_{safe_name}.csv"
        else:
            filename = "sacrament_records_iparish.csv"

        logger.info("200 | Sacrament records exported successfully to CSV")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during sacrament record data export!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during sacrament record data export!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export sacrament data as csv
@router.get(
    "/sacraments/csv",
    summary="Export sacraments as CSV",
)
async def export_sacraments_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(
        None, description="Optional parish ID to filter sacraments"
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to export sacraments to CSV...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export sacrament data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export sacrament data from another parish.",
                )

        # model relationship connector
        query = db.query(Sacrament).options(joinedload(Sacrament.parish))

        # parish filter
        if parish_id:
            query = query.filter(Sacrament.parish_id == parish_id)

        # sacrament query
        sacraments = query.all()

        records = export_sacraments(sacraments)

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())

        # csv generator
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic Filename ---
        if role_title == "Priest":
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            parish_name = parish.parish_data.get("parish_name") if parish else "parish"
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"sacraments_{safe_name}.csv"
        else:
            filename = "sacraments_iparish.csv"

        logger.info("200 | Sacrament exported successfully to CSV")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during sacrament data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during sacrament data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export invited users data as csv
@router.get(
    "/user-invites/csv",
    summary="Export invited users as CSV",
)
async def export_invited_users_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Filter by parish ID"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Exporting invited users to CSV...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export invited users.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export invited users from another parish.",
                )

        # model relationship connector
        query = db.query(InvitedUser).options(
            joinedload(InvitedUser.parish),
            joinedload(InvitedUser.role),
            joinedload(InvitedUser.invited_by_user),
        )

        # parish filter
        if parish_id:
            query = query.filter(InvitedUser.parish_id == parish_id)

        # invited user query
        invited_users = query.all()

        records = export_invited_users(invited_users)

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())

        # csv generator
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic Filename ---
        if role_title == "Priest":
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            parish_name = parish.parish_data.get("parish_name") if parish else "parish"
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"invited_users_{safe_name}.csv"
        else:
            filename = "invited_users_iparish.csv"

        logger.info("200 | User invites exported successfully to CSV")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during invited user data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during invited user data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# export user data as csv
@router.get(
    "/users/csv",
    summary="Export users as CSV",
)
async def export_users_csv(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Filter by parish ID"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Exporting users to CSV...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = getattr(user.role, "title", None)

        # role and parish based checks
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to export users.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export users from another parish.",
                )

        # query setup
        query = db.query(User).options(joinedload(User.role))

        # parish_id filter
        if parish_id:
            query = query.filter(User.parish_id == parish_id)

        # model query
        users = query.all()

        records = export_users(users)

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        fieldnames = list(records[0].keys())

        # csv generator
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in records:
            writer.writerow(row)

        output.seek(0)

        # dynamic Filename
        if role_title == "Priest":
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            parish_name = parish.parish_data.get("parish_name") if parish else "parish"
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"users_{safe_name}.csv"
        else:
            filename = "users_iparish.csv"

        logger.info("200 | User exported successfully to CSV")

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during user data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during user data export!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )
