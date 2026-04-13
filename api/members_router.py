from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, asc, cast, desc, text
from sqlalchemy.orm import Session
from api.serializers import serialize_members
from db.models.member import Member
from sqlalchemy.orm.attributes import InstrumentedAttribute
from db.models.parish import Parish
from db.models.user import User
from db.session import get_db
from schemas.member_schema import (
    PaginatedMemberResponse,
    MemberCreate,
    MemberUpdate,
    MemberDetails,
)
from sqlalchemy.orm import joinedload
from log_config import logger
from schemas.notification_schema import NotificationType
from services.auth_service import (
    get_current_user,
)
from sqlalchemy.exc import SQLAlchemyError
from services.notification_service import create_notification
from services.user_service import get_user_details
from utils.member_number_generator import generate_member_no
from utils.phone_number_eligibility_check import is_valid_phone_number

router = APIRouter()


# retrieve db/parish member count with parish filter
@router.get(
    "/count",
    summary="Fetch all count of member records (optionally filtered by parish)",
)
async def count_member_records(
    parish_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve member count...")
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
                    detail="Priests must specify a parish_id to view member count.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view member count from another parish.",
                )

        # member query
        query = db.query(Member)

        # parish filter
        if parish_id:
            query = query.filter(Member.parish_id == parish_id)

        total_count = query.count()
        logger.info("200 | Member count fetched successfully!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during member records count!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during member records count!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retrieve db/parish members with parish filter
@router.get(
    "/all",
    response_model=PaginatedMemberResponse,
    summary="Fetch all member records (optionally filtered by parish)",
)
async def retrieve_all_members(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("member_no"),
    sort_order: Optional[str] = Query("asc"),
    parish_id: Optional[UUID] = Query(None),
    is_archived: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve all member data...")
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
                    detail="Priests must specify a parish_id to view member data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view member data from another parish.",
                )

        offset = (page - 1) * page_size

        # member query
        query = db.query(Member)

        # archive filter
        if is_archived is None:
            query = query.filter(Member.is_archived == False)
        else:
            query = query.filter(Member.is_archived == is_archived)

        # parish filter
        if parish_id:
            query = query.filter(Member.parish_id == parish_id)

        # search parameter
        if search:
            query = query.filter(
                (cast(Member.member_data["email"], String).ilike(f"%{search}%"))
                | (cast(Member.member_data["first_name"], String).ilike(f"%{search}%"))
                | (cast(Member.member_data["last_name"], String).ilike(f"%{search}%"))
            )

        # sort parameter
        allowed_sort_fields = ["member_no", "created_at", "updated_at"]
        if sort_by in allowed_sort_fields:
            sort_column = getattr(Member, sort_by, None)
            if isinstance(sort_column, InstrumentedAttribute):
                if sort_order == "desc":
                    query = query.order_by(desc(sort_column))
                else:
                    query = query.order_by(asc(sort_column))
        else:
            # default sort parameter
            query = query.order_by(asc(Member.member_no))

        total = query.count()
        members = query.offset(offset).limit(page_size).all()

        logger.info("200 | Members retrieved successfully!")

        return PaginatedMemberResponse(
            items=serialize_members(members),
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during member records retrieval!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during member records retrieval!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# create member
@router.post(
    "/create",
    summary="Create a member, linked to a parish",
)
async def create_member(
    member_create: MemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to create a member...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        # duplicate data checks
        email = member_create.member_data.email.lower()
        phone = member_create.member_data.phone

        logger.info(f"Create member request!")

        if not is_valid_phone_number(phone):
            logger.warning(f"Invalid phone format!")
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number format. Use 2547XXXXXXXX!",
            )

        # check duplicate email
        existing_member = (
            db.query(Member)
            .filter(text("member_data->>'email' = :email"))
            .params(email=email)
            .first()
        )
        if existing_member:
            logger.warning(f"Duplicate member email attempted!")
            raise HTTPException(
                status_code=400, detail="Member with this email already exists!"
            )

        # check duplicate phone
        existing_phone = (
            db.query(Member)
            .filter(text("member_data->>'phone' = :phone"))
            .params(phone=phone)
            .first()
        )
        if existing_phone:
            logger.warning(f"Duplicate phone number attempted!")
            raise HTTPException(
                status_code=400, detail="Phone number is already in use!"
            )

        # generate member number
        try:
            member_no = generate_member_no(parish_id=member_create.parish_id, db=db)
        except ValueError as e:
            logger.error(f"Error generating member number!: {e}")
            raise HTTPException(status_code=404, detail=str(e))

        # create new member
        new_member = Member(
            parish_id=member_create.parish_id,
            member_no=member_no,
            member_data=member_create.member_data.model_dump(),
            member_group=member_create.member_group,
        )

        db.add(new_member)
        db.commit()
        db.refresh(new_member)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Member record created successfully!",
        )

        logger.info("201 | Member record created successfully!")
        return new_member

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during member creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during member creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# get member details
@router.get(
    "/details/{member_no}",
    response_model=MemberDetails,
    summary="Get details of an existing member in the system",
)
async def retrieve_member_details(
    member_no: str,
    db=Depends(get_db),
):
    try:
        logger.info(f"Retrieving member details...")
        existing_member = (
            db.query(Member)
            .options(joinedload(Member.parish))
            .filter(Member.member_no == member_no)
            .first()
        )
        if not existing_member:
            logger.warning(f"Member not found!")
            raise HTTPException(status_code=404, detail="Member not found!")
        logger.info(f"Member details retrieved!")
        return existing_member

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except Exception as e:
        logger.error(f"Error retrieving member details!: {e}")
        raise HTTPException(status_code=500, detail="Internal server error!")


# update member details
@router.put(
    "/update/{member_id}",
    response_model=MemberDetails,
    summary="Update details of an existing member",
)
async def update_member_details(
    member_id: UUID,
    member_update: MemberUpdate,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to update a member...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")
        existing_member = db.query(Member).filter(Member.id == member_id).first()
        if not existing_member:
            logger.warning(f"Member not found!")
            raise HTTPException(status_code=404, detail="Member not found!")

        update_data = member_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(existing_member, key, value)
        db.commit()
        db.refresh(existing_member)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Member record updated successfully!",
        )

        logger.info("201 | Member record updated and notification sent successfully!")
        return existing_member

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except Exception as e:
        logger.error(f"Failed to update member!: {e}")
        raise HTTPException(status_code=500, detail="Internal server error!")


# archive member
@router.post(
    "/archive/{member_id}",
    summary="Archive member",
)
async def archive_member(
    member_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive member data...")
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
                detail="Priests must specify a parish_id to archive member data.",
            )
        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive member data from another parish.",
            )

    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found!")
    member.is_archived = True
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"message": "Member successfuly archived!"}


# unarchive member
@router.post("/unarchive/{member_id}", summary="Unarchive member")
async def unarchive_member(
    member_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive member data...")
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
                detail="Priests must specify a parish_id to unarchive member data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to unarchive member data from another parish.",
            )
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found!")
    member.is_archived = False
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"message": "Member successfuly unarchived!"}
