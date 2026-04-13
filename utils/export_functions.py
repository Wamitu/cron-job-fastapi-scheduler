import csv
import re
from io import StringIO
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import joinedload
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from api.sacraments_router import serialize_sacraments
from api.user_invites_router import serialize_invited_users
from db.models.sacrament import Sacrament
from db.models.user_invite import InvitedUser
from log_config import logger
from api.users_router import serialize_users
from db.models.parish import Parish
from db.models.user import User
from services.user_service import get_user_details


# helper to sanitize dictionary records
def sanitize_record(row: dict) -> dict:
    sanitized = {}
    for key, value in row.items():
        if isinstance(value, str):
            sanitized[key] = value.replace("\x00", "")
        else:
            sanitized[key] = value
    return sanitized


# export users function
def get_users_export_csv(
    db: Session, current_user: User, parish_id: Optional[UUID] = None
) -> dict:
    """
    Prepare CSV content for users export. Returns a dict with:
    { "filename": str, "content": str }
    """
    try:
        logger.info("Preparing users CSV export...")

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

        users = query.all()
        records = serialize_users(users)

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        # dynamically pick all fields from the first record
        fieldnames = list(records[0].keys())

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(sanitize_record(row))

        output.seek(0)

        # dynamic filename
        if role_title == "Priest" and parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            parish_name = parish.parish_data.get("parish_name") if parish else "parish"
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"users_{safe_name}.csv"
        else:
            filename = "users_iparish.csv"

        logger.info("Users CSV prepared successfully")
        return {"filename": filename, "content": output.getvalue()}

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during user data export!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")
    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during user data export!", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# export invited users function
def get_invited_users_export_csv(
    db: Session, current_user: User, parish_id: Optional[UUID] = None
) -> dict:
    """
    Prepare CSV content for invited users export. Returns a dict with:
    { "filename": str, "content": str }
    """
    try:
        logger.info("Preparing invited users CSV export...")

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
                    detail="Priests must specify a parish_id to export invited users.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export invited users from another parish.",
                )

        # query setup
        query = db.query(InvitedUser).options(
            joinedload(InvitedUser.parish),
            joinedload(InvitedUser.role),
            joinedload(InvitedUser.invited_by_user),
        )

        if parish_id:
            query = query.filter(InvitedUser.parish_id == parish_id)

        invited_users = query.all()
        records = serialize_invited_users(invited_users)

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        # dynamically pick all fields from the first record
        fieldnames = list(records[0].keys())

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(sanitize_record(row))

        output.seek(0)

        # dynamic filename
        if role_title == "Priest" and parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            parish_name = parish.parish_data.get("parish_name") if parish else "parish"
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"invited_users_{safe_name}.csv"
        else:
            filename = "invited_users_iparish.csv"

        logger.info("Invited users CSV prepared successfully")
        return {"filename": filename, "content": output.getvalue()}

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during invited user data export!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")
    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during invited user data export!", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# export sacraments function
def get_sacraments_export_csv(
    db: Session, current_user: User, parish_id: Optional[UUID] = None
) -> dict:
    """
    Prepare CSV content for sacraments export. Returns a dict with:
    { "filename": str, "content": str }
    """
    try:
        logger.info("Preparing sacraments CSV export...")

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
                    detail="Priests must specify a parish_id to export sacrament data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to export sacrament data from another parish.",
                )

        # query setup
        query = db.query(Sacrament).options(joinedload(Sacrament.parish))
        if parish_id:
            query = query.filter(Sacrament.parish_id == parish_id)

        sacraments = query.all()
        records = serialize_sacraments(sacraments)

        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")

        # dynamically pick all fields from the first record
        fieldnames = list(records[0].keys())

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(sanitize_record(row))

        output.seek(0)

        # dynamic filename
        if role_title == "Priest" and parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            parish_name = parish.parish_data.get("parish_name") if parish else "parish"
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", parish_name)
            filename = f"sacraments_{safe_name}.csv"
        else:
            filename = "sacraments_iparish.csv"

        logger.info("Sacraments CSV prepared successfully")
        return {"filename": filename, "content": output.getvalue()}

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during sacrament data export!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")
    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during sacrament data export!", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")
