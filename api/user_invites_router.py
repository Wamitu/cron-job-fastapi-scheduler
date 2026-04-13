import csv
from io import StringIO
import json
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from uuid import UUID, uuid4
from passlib.context import CryptContext
from datetime import datetime, timedelta
from api.serializers import serialize_parish
from api.serializers import serialize_role
from api.serializers import serialize_user
from db.models.user import User
from sqlalchemy.exc import SQLAlchemyError
from db.models.parish import Parish
from schemas.notification_schema import NotificationType
from services.auth_service import get_current_user
from services.notification_service import create_notification
from services.user_service import get_user_details
from utils.email_invite import send_email_invite, send_success_email
from db.models.user_invite import InvitedUser
from schemas.user_invite_schema import (
    InviteUserRequest,
    InvitedUserDetails,
    PaginatedInvitedUserResponse,
    UserRegisterFromInviteRequest,
)
from db.session import get_db
from datetime import timezone
from log_config import logger
from utils.phone_number_eligibility_check import is_valid_phone_number

router = APIRouter()


# invite user
@router.post(
    "/invite",
)
async def invite_user(
    invite_data: InviteUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to invite a user...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        if user.role.title == "Priest":
            if invite_data.parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are only allowed to invite users to your assigned parish.",
                )

        if not is_valid_phone_number(invite_data.phone):
            logger.warning(f" Invalid phone number format!")
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number format. Must be in 2547XXXXXXXX format!",
            )

        existing_invite = (
            db.query(InvitedUser)
            .filter(
                (InvitedUser.email == invite_data.email)
                | (InvitedUser.phone == invite_data.phone)
            )
            .first()
        )
        if existing_invite:
            raise HTTPException(
                status_code=400,
                detail="User with this email or phone has already been invited!",
            )

        token = str(uuid4())

        invited_user = InvitedUser(
            first_name=invite_data.first_name,
            last_name=invite_data.last_name,
            email=invite_data.email,
            phone=invite_data.phone,
            role_id=invite_data.role_id,
            parish_id=invite_data.parish_id,
            is_active=True,
            is_used=False,
            is_archived=False,
            invited_by=user.id,
            token=token,
        )

        db.add(invited_user)
        db.commit()
        db.refresh(invited_user)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Invited user created successfully!",
        )

        logger.info("201 | Invited user created successfully!")

        parish_name = "Your Parish Name"
        if invited_user.parish_id:
            try:
                parish = db.query(Parish).filter_by(id=invited_user.parish_id).first()
                if parish:
                    parish_data = parish.parish_data
                    if isinstance(parish_data, str):
                        parish_data = json.loads(parish_data)
                    parish_name = parish_data.get("parish_name", parish_name)
            except Exception as e:
                logger.warning(f"Error reading parish_data: {e}")

        try:
            send_email_invite(
                invitee_first_name=invited_user.first_name,
                invitee_last_name=invited_user.last_name,
                invitee_id=invited_user.id,
                to_email=invited_user.email,
                invitee_token=invited_user.token,
                parish_name=parish_name,
            )
        except Exception as e:
            logger.error(f"Failed to send invite email!: {e}")
            raise HTTPException(
                status_code=500, detail="User invited but email sending failed!"
            )

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"User invite sent successfully!",
        )

        logger.info("201 | User invite sent successfully!")
        return {"message": "Invitation sent successfully!"}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError:
        logger.exception("Database error!")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error!")

    except Exception:
        logger.exception("Unexpected error!")
        raise HTTPException(status_code=500, detail="Unexpected error occurred!")


# password validity
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def validate_password(password: str):
    if len(password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters long!"
        )
    if not any(c.islower() for c in password):
        raise HTTPException(
            status_code=400, detail="Password must contain a lowercase letter!"
        )
    if not any(c.isupper() for c in password):
        raise HTTPException(
            status_code=400, detail="Password must contain an uppercase letter!"
        )
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="Password must contain a number!")


# register from invite
@router.post(
    "/register-from-invite",
)
async def register_from_invite(
    data: UserRegisterFromInviteRequest, db: Session = Depends(get_db)
):
    try:
        logger.info("Attempting to register from invite...")
        invited_user = db.query(InvitedUser).filter_by(token=data.token).first()

        if not invited_user:
            logger.warning(f"Invalid invite token!")
            raise HTTPException(status_code=404, detail="Invalid token!")

        if invited_user.is_used:
            logger.warning(f"Token already used!")
            raise HTTPException(status_code=400, detail="Token has already been used!")

        if invited_user.created_at + timedelta(hours=48) < datetime.now(timezone.utc):
            logger.warning(f"Expired token!")
            raise HTTPException(status_code=400, detail="Token has expired!")

        if invited_user.is_active == False:
            logger.warning(f"Expired token!")
            raise HTTPException(status_code=400, detail="Token has expired!")

        validate_password(data.password)
        hashed_password = pwd_context.hash(data.password)

        new_user = User(
            first_name=invited_user.first_name,
            last_name=invited_user.last_name,
            email=invited_user.email,
            phone=invited_user.phone,
            parish_id=invited_user.parish_id,
            role_id=invited_user.role_id,
            hashed_password=hashed_password,
            is_active=True,
        )

        invited_user.is_used = True
        invited_user.is_active = False
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Load parish name for email
        parish_name = "Your Parish"
        if invited_user.parish_id:
            try:
                parish = db.query(Parish).filter_by(id=invited_user.parish_id).first()
                if parish and parish.parish_data:
                    parish_data = parish.parish_data
                    if isinstance(parish_data, str):
                        parish_data = json.loads(parish_data)
                    parish_name = parish_data.get("parish_name", parish_name)
            except Exception as e:
                logger.warning(f"Error reading parish_data during registration!: {e}")

        try:
            send_success_email(
                to_email=new_user.email,
                first_name=new_user.first_name,
                last_name=new_user.last_name,
                parish_name=parish_name,
            )
        except Exception as email_err:
            logger.error(f"Failed to send success email: {email_err}")

        logger.info(f"User registered from invite!")
        return {"message": "Registration complete. You can now log in!"}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error during user registration from invite!")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while processing your registration!",
        )

    except Exception:
        logger.exception("Unexpected error during registration from invite!")
        raise HTTPException(
            status_code=500, detail="Unexpected error occurred during registration!"
        )


# serialize invited_user
def serialize_invited_user(invited_user):
    """Convert SQLAlchemy model instance to a dictionary, excluding internal attributes."""
    if isinstance(invited_user, dict):
        return invited_user
    return {
        "id": invited_user.id,
        "parish_id": invited_user.parish_id,
        "parish": (
            serialize_parish(invited_user.parish) if invited_user.parish else None
        ),
        "first_name": invited_user.first_name,
        "last_name": invited_user.last_name,
        "email": invited_user.email,
        "phone": invited_user.phone,
        "role_id": invited_user.role_id,
        "role": serialize_role(invited_user.role) if invited_user.role else None,
        "invited_by": invited_user.invited_by,
        "invited_by_user": (
            serialize_user(invited_user.invited_by_user)
            if invited_user.invited_by_user
            else None
        ),
        "is_archived": invited_user.is_archived,
        "created_at": (
            invited_user.created_at.isoformat() if invited_user.created_at else None
        ),
    }


# serialize invited_users
def serialize_invited_users(invited_users):

    return [serialize_invited_user(invited_user) for invited_user in invited_users]


# get data count
@router.get(
    "/count",
    summary="Get count of all invited users in the system",
)
async def count_invited_user_records(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve invited users count...")

        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view invited user count for their own parish.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view invited user count from another parish.",
                )

        query = db.query(InvitedUser)

        if parish_id:
            logger.info(f"Filtering invited users by parish_id: {parish_id}")
            query = query.filter(InvitedUser.parish_id == parish_id)

        total_count = query.count()

        logger.info(f"Total invited users count!")
        return {"total": total_count}
    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise
    except SQLAlchemyError:
        logger.exception("Failed to count invited users due to database error!")
        raise HTTPException(
            status_code=500, detail="Database error while counting invited users!"
        )
    except Exception:
        logger.exception("Unexpected error occurred while counting invited users!")
        raise HTTPException(status_code=500, detail="Unexpected error occurred!")


# retrieve all invited users
@router.get(
    "/all",
    response_model=PaginatedInvitedUserResponse,
    summary="Get all invited users in the system or per parish",
)
async def retrieve_all_invited_users(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    parish_id: Optional[UUID] = Query(None, description="Filter by parish ID"),
    is_archived: Optional[bool] = None,
    is_active: Optional[bool] = None,
    is_used: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve invited users...")

        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view invited user data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view invited user data from another parish.",
                )
        offset = (page - 1) * page_size
        query = db.query(InvitedUser).options(
            joinedload(InvitedUser.parish),
            joinedload(InvitedUser.role),
            joinedload(InvitedUser.invited_by_user),
        )

        # archive filter
        if is_archived is None:
            query = query.filter(InvitedUser.is_archived == False)
        else:
            query = query.filter(InvitedUser.is_archived == is_archived)

        # is active filter
        if is_active is not None:
            now = datetime.now(timezone.utc)

            if is_active:
                # Active = must be marked active and not expired
                query = query.filter(
                    and_(
                        InvitedUser.is_active == True,
                        InvitedUser.created_at + timedelta(hours=48) > now,
                    )
                )
            else:
                # Expired = either not active OR expired by time
                query = query.filter(
                    or_(
                        InvitedUser.is_active == False,
                        InvitedUser.created_at + timedelta(hours=48) < now,
                    )
                )

        # is used filter
        if is_used is not None:
            if is_used:
                # used token
                query = query.filter(
                    InvitedUser.is_used == True,
                )
            else:
                # unused token
                query = query.filter(
                    InvitedUser.is_used == False,
                )

        # parish filter
        if parish_id:
            query = query.filter(InvitedUser.parish_id == parish_id)

        # search parameter
        if search:
            query = query.filter(
                or_(
                    InvitedUser.first_name.ilike(f"%{search}%"),
                    InvitedUser.last_name.ilike(f"%{search}%"),
                    InvitedUser.phone.ilike(f"%{search}%"),
                )
            )

        # sort parameter
        if sort_by and hasattr(InvitedUser, sort_by):
            column = getattr(InvitedUser, sort_by)
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            query = query.order_by(InvitedUser.created_at.desc())

        total_count = query.count()
        invited_users = query.offset(offset).limit(page_size).all()

        logger.info("Retrieved invited users!")

        return {
            "items": serialize_invited_users(invited_users),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "pages": (total_count + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as db_err:
        logger.error(f"Database error retrieving invited users!: {str(db_err)}")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while retrieving invited users!",
        )

    except Exception as e:
        logger.error(f"Unexpected error!: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your request!",
        )


# retrieve details of an invited user
@router.get(
    "/details/{invitee_id}",
    response_model=InvitedUserDetails,
)
async def retrieve_invited_users_details(
    invitee_id: UUID,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve invited user details...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        db_invited_user = (
            db.query(InvitedUser)
            .options(
                joinedload(InvitedUser.parish),
                joinedload(InvitedUser.role),
                joinedload(InvitedUser.invited_by_user),
            )
            .filter(InvitedUser.id == invitee_id)
            .first()
        )
        if not db_invited_user:
            logger.warning(f"Invited user not found!")
            raise HTTPException(status_code=404, detail="User not found!")

        logger.info(f"Retrieved invited user details for invitee!")
        return db_invited_user

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as db_err:
        logger.error(f"Database error retrieving invited user!: {str(db_err)}")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while retrieving the invited user!",
        )

    except Exception as e:
        logger.error(f"Unexpected error retrieving invited user!: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error occurred!")


# archive invited user
@router.post(
    "/archive/{invited_user_id}",
    summary="Archive invited user",
)
async def archive_invited_user(
    invited_user_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive invited user data...")
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
                detail="Priests must specify a parish_id to archive invited user data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive invited user data from another parish.",
            )

    invited_user = (
        db.query(InvitedUser).filter(InvitedUser.id == invited_user_id).first()
    )
    if not invited_user:
        raise HTTPException(status_code=404, detail="invited_user not found!")
    invited_user.is_archived = True
    db.add(invited_user)
    db.commit()
    db.refresh(invited_user)
    return {"message": "Invited_user successfuly archived!"}


# unarchive invited user
@router.post("/unarchive/{invited_user_id}", summary="Unarchive invited user")
async def unarchive_invited_user(
    invited_user_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive invited user data...")
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
                detail="Priests must specify a parish_id to unarchive invited user data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to unarchive invited user data from another parish.",
            )
    invited_user = (
        db.query(invited_user).filter(invited_user.id == invited_user_id).first()
    )
    if not invited_user:
        raise HTTPException(status_code=404, detail="invited_user not found!")
    invited_user.is_archived = False
    db.add(invited_user)
    db.commit()
    db.refresh(invited_user)
    return {"message": "Invited user successfuly unarchived!"}
