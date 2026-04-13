from datetime import datetime, timedelta, timezone
import json
from typing import Optional
from uuid import UUID, uuid4
from db.models.diocese import Diocese
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import extract, func, text
from sqlalchemy.orm import Session
from api.serializers import serialize_parish_parish_subscription, serialize_parishes
from db.models.collection import Collection
from db.models.login_activity import LoginActivity
from db.models.member import Member
from db.models.parish import Parish
from db.models.parish_subscription import ParishSubscription, ParishSubscriptionChange
from db.models.role import Role
from db.models.subscription_plan import SubscriptionPlan
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from db.models.user import User
from db.models.user_invite import InvitedUser
from db.session import get_db
from log_config import logger
from schemas.notification_schema import NotificationType
from schemas.parish_schema import (
    PaginatedParishResponse,
    ParishCreate,
    ParishDetails,
    ParishUpdate,
)
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from schemas.parish_subscription_schema import (
    ParishOnBoardingSubscriptionCreate,
    ParishSubscriptionChangeDetails,
    SubscriptionStatus,
)
from schemas.user_invite_schema import OnBoardParishInviteUserRequest
from services.auth_service import get_current_user
from services.notification_service import create_notification
from services.user_service import get_user_details
from utils.email_invite import send_email_invite
from utils.member_number_generator import (
    generate_member_number_prefix_suggestions,
    update_member_numbers,
)
from utils.parish_slug_generator import generate_unique_slug
from utils.phone_number_eligibility_check import is_valid_phone_number
from dateutil.relativedelta import relativedelta


router = APIRouter()


# get data count
@router.get(
    "/count",
    summary="Fetch all count of parishes",
)
async def count_parish_records(
    db: Session = Depends(get_db),
):
    try:
        logger.info(f"Retrieving parish data count...")
        query = db.query(Parish)
        total_count = query.count()
        logger.info("200 | Parish count fetched successfully!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during parish data count!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during parish data count!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# retrieve all parishes
@router.get(
    "/all",
    response_model=PaginatedParishResponse,
    summary="Fetch all parishes",
)
async def retrieve_all_parishes(
    is_archived: Optional[bool] = None,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
):
    offset = (page - 1) * page_size

    try:
        query = db.query(Parish)
        logger.info(f"Retrieving parishes...!")

        if search:
            query = query.filter(
                Parish.parish_data["parish_name"].astext.ilike(f"%{search}%"),
                Parish.parish_data["parish_slug"].astext.ilike(f"%{search}%"),
            )

        # archive filter
        if is_archived is None:
            query = query.filter(Parish.is_archived == False)
        else:
            query = query.filter(Parish.is_archived == is_archived)

        # sort parameter
        allowed_sort_fields = {"name", "slug", "created_at"}
        if sort_by in allowed_sort_fields:
            column = getattr(Parish, sort_by)
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            query = query.order_by(Parish.created_at.desc())

        total_count = query.count()
        parishes = query.offset(offset).limit(page_size).all()

        logger.info(f"Retrieved parishes successfully!")

        return {
            "items": serialize_parishes(parishes),
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
        logger.error("Database error during parish data query!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during parish data query!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# check existing db member_number prefixes
@router.get(
    "/existing-member-number-prefixes",
    summary="Retrieve all used member_number_prefix values",
)
def retrieve_existing_prefixes(db: Session = Depends(get_db)):
    try:
        logger.info(f"Retrieving member number prefixes...")
        prefixes = (
            db.query(Parish.member_number_prefix)
            .filter(Parish.member_number_prefix.isnot(None))
            .distinct()
            .all()
        )
        result = [prefix[0] for prefix in prefixes]
        logger.info(f"Retrieved unique member number prefixes successfully!")
        return result

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during member number prefixes data query!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during member number prefixes data query!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# generate member number prefix suggestions
@router.get(
    "/member-number-prefix-suggestions",
    summary="Suggest unused member_number_prefix values",
)
def retrieve_prefix_suggestions(db: Session = Depends(get_db)):
    try:
        logger.info(f"Suggesting member number prefixes...")
        suggestions = generate_member_number_prefix_suggestions(db)
        logger.info(f"Generated member_number_prefix suggestions successfully!")
        return suggestions

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during member number prefixes data suggestion!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during member number prefixes data suggestion!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# create/on-board parish, generate slug from parish name, check if parish exists with same name in lower case
@router.post(
    "/create",
    response_model=ParishDetails,
    summary="On-board a parish",
)
async def onboard_parish(
    parish_create: ParishCreate,
    invited_user_create: OnBoardParishInviteUserRequest,
    parish_subscription_create: ParishOnBoardingSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")
        email = parish_create.parish_data.contact_email.strip().lower()
        phone = parish_create.parish_data.contact_phone.strip()
        prefix = parish_create.member_number_prefix.strip()
        parish_name = parish_create.parish_data.parish_name

        logger.info(f"Starting onboarding parish...")

        # Phone format validation
        if not is_valid_phone_number(phone):
            logger.warning("Invalid parish phone number format!")
            raise HTTPException(
                status_code=400,
                detail="Invalid parish phone number. Must be in 2547XXXXXXXX format!",
            )

        # Check for duplicate email
        if (
            db.query(Parish)
            .filter(text("parish_data ->> 'contact_email' = :email"))
            .params(email=email)
            .first()
        ):
            logger.warning(f"Email already exists!")
            raise HTTPException(
                status_code=400, detail="Parish with this contact email already exists!"
            )

        # Check for duplicate phone
        if (
            db.query(Parish)
            .filter(text("parish_data ->> 'contact_phone' = :phone"))
            .params(phone=phone)
            .first()
        ):
            logger.warning(f"Phone already exists!")
            raise HTTPException(
                status_code=400, detail="Parish with this contact phone already exists!"
            )

        # Check for duplicate member number prefix
        if db.query(Parish).filter(Parish.member_number_prefix == prefix).first():
            logger.warning(f"Member number prefix already exists!")
            raise HTTPException(
                status_code=400,
                detail="A parish with this member number prefix already exists!",
            )

        # Create parish
        parish_slug = generate_unique_slug(parish_name, db)
        parish_data = {
            "parish_name": parish_name,
            "parish_slug": parish_slug,
            "contact_email": email,
            "contact_phone": phone,
        }
        existing_diocese = (
            db.query(Diocese).filter(Diocese.id == parish_create.diocese_id).first()
        )
        if not existing_diocese:
            raise HTTPException(status_code=404, detail="Diocese not found!")
        new_parish = Parish(
            diocese_id=parish_create.diocese_id,
            parish_data=parish_data,
            member_number_prefix=prefix,
            member_number_suffix=parish_create.member_number_suffix,
            parish_settings=parish_create.parish_settings,
        )
        db.add(new_parish)
        db.flush()

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Parish on boarded successfully!",
        )

        logger.info("201 | Parish on boarded successfully!")

        # Get the selected plan for parish onboarding
        # Validate subscription plan
        plan = (
            db.query(SubscriptionPlan)
            .filter_by(id=parish_subscription_create.subscription_plan_id)
            .first()
        )
        if not plan:
            logger.error("Invalid subscription plan ID!")
            raise HTTPException(status_code=400, detail="Invalid subscription plan ID!")

        # Check if parish already has a subscription
        existing_subscription = (
            db.query(ParishSubscription).filter_by(parish_id=new_parish.id).first()
        )
        if existing_subscription:
            logger.warning("Parish already has a subscription!")
            raise HTTPException(
                status_code=400,
                detail="This parish already has an active or pending subscription!",
            )

        # Create new subscription with same-day-next-month end date
        start_date = datetime.now(timezone.utc)
        end_date = start_date + relativedelta(months=1)

        new_subscription = ParishSubscription(
            parish_id=new_parish.id,
            subscription_plan_id=plan.id,
            start_date=start_date,
            end_date=end_date,
            last_renewed_at=start_date,
            status=SubscriptionStatus.inactive,
        )
        db.add(new_subscription)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Inactive parish subscription created with selected plan!",
        )

        logger.info("201 | Inactive parish subscription created with selected plan!")

        # Get role
        priest_role = db.query(Role).filter(func.lower(Role.title) == "priest").first()
        if not priest_role:
            logger.error("No 'priest' role found in the database!")
            raise HTTPException(status_code=404, detail="No priest role found!")

        # check if user details have been provided, otherwise skip user creation
        invited_user = None
        if any(
            [
                invited_user_create.first_name,
                invited_user_create.last_name,
                invited_user_create.email,
                invited_user_create.phone,
            ]
        ):
            logger.info("User details provided — proceeding to invite user.")

            # Check for existing user email
            if invited_user_create.email:
                if (
                    db.query(User)
                    .filter(User.email == invited_user_create.email)
                    .first()
                ):
                    logger.warning("User with this email already exists!")
                    raise HTTPException(
                        status_code=400, detail="User with this email already exists!"
                    )

            # Phone format and duplication
            if invited_user_create.phone:
                if not is_valid_phone_number(invited_user_create.phone):
                    logger.warning("Invalid phone number format!")
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid phone number format. Must be 2547XXXXXXXX!",
                    )

                if (
                    db.query(User)
                    .filter(User.phone == invited_user_create.phone)
                    .first()
                ):
                    logger.warning("User with this phone number already exists!")
                    raise HTTPException(
                        status_code=400,
                        detail="User with this phone number already exists!",
                    )

            # Check for duplicate invite
            if (
                db.query(InvitedUser)
                .filter(
                    (InvitedUser.email == invited_user_create.email)
                    | (InvitedUser.phone == invited_user_create.phone)
                )
                .first()
            ):
                logger.warning("User already invited!")
                raise HTTPException(
                    status_code=400,
                    detail="User with this email or phone number has already been invited!",
                )

            # Create invite
            token = str(uuid4())
            user_data = {
                "role_id": priest_role.id,
                "parish_id": new_parish.id,
                "is_active": True,
                "is_used": False,
                "invited_by": user.id,
                "token": token,
            }

            if invited_user_create.first_name:
                user_data["first_name"] = invited_user_create.first_name
            if invited_user_create.last_name:
                user_data["last_name"] = invited_user_create.last_name
            if invited_user_create.email:
                user_data["email"] = invited_user_create.email
            if invited_user_create.phone:
                user_data["phone"] = invited_user_create.phone

            invited_user = InvitedUser(
                **{**invited_user_create.model_dump(), **user_data}
            )
            db.add(invited_user)
            db.flush()

            create_notification(
                db=db,
                user_id=user.id,
                parish_id=user.parish_id,
                notification_type=NotificationType.info,
                message=f"Invited user created and notification sent successfully!",
            )

            logger.info(
                "201 | Invited user created and notification sent successfully!"
            )

            # Email logic now inside the same block
            parish_display_name = parish_name
            try:
                if isinstance(parish_data, str):
                    parish_data = json.loads(parish_data)
                parish_display_name = parish_data.get("parish_name", parish_name)
            except Exception as e:
                logger.warning("Error extracting parish name for email invite!")

            if invited_user.email:
                try:
                    send_email_invite(
                        invitee_first_name=invited_user.first_name,
                        invitee_last_name=invited_user.last_name,
                        invitee_id=invited_user.id,
                        to_email=invited_user.email,
                        invitee_token=invited_user.token,
                        parish_name=parish_display_name,
                    )
                    logger.info("Invitation email sent to parish user!")
                except Exception as e:
                    logger.error(f"Failed to send invitation email: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail="Parish created but email failed to reach parish user!",
                    )

        db.commit()
        db.refresh(new_parish)
        if invited_user:
            db.refresh(invited_user)
        return new_parish

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} - {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "Database error during parish creation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error during parish creation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred!",
        )


# retrieve parish details
@router.get(
    "/details/{parish_id}",
    response_model=ParishDetails,
    summary="Get details of an existing parish",
)
async def retrieve_parish_details(
    parish_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        logger.info(f"Retrieving parish details...!")
        db_parish = db.query(Parish).filter(Parish.id == parish_id).first()

        if db_parish is None:
            logger.warning("Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

        logger.info("Parish details retrieved successfully!")
        return db_parish

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | Database error during parish details query!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during parish details query!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retrieve parish parish subscription
@router.get(
    "/{parish_id}/subscription",
    response_model=dict,
    summary="Get parish subscription including plan features",
)
async def get_parish_subscription(parish_id: str, db: Session = Depends(get_db)):
    try:
        logger.info("Fetching active subscription for parish...")

        # Get active parish subscription
        parish_subscription = (
            db.query(ParishSubscription)
            .filter(ParishSubscription.parish_id == parish_id)
            .options(
                joinedload(ParishSubscription.parish),
                joinedload(ParishSubscription.subscription)
                .joinedload(SubscriptionPlan.features_pivot)
                .joinedload(SubscriptionPlanFeaturePivot.feature),
                joinedload(ParishSubscription.next_plan),
            )
            .order_by(ParishSubscription.created_at.desc())
            .first()
        )

        if not parish_subscription:
            logger.warning("404 | No active subscription found for parish!")
            raise HTTPException(
                status_code=404, detail="Active parish subscription not found!"
            )

        # Filter only enabled features
        if parish_subscription.subscription:
            parish_subscription.subscription.features_pivot = [
                pivot
                for pivot in parish_subscription.subscription.features_pivot
                if pivot.enabled
            ]
            logger.info(
                "Filtered disabled features... Showing enabled features for parish subscription..."
            )

        # Get latest change
        latest_change = (
            db.query(ParishSubscriptionChange)
            .filter(ParishSubscriptionChange.parish_id == parish_id)
            .order_by(ParishSubscriptionChange.change_date.desc())
            .first()
        )

        logger.info("200 | Retrieved subscription and change for parish successfully!")

        response = {
            "subscription": serialize_parish_parish_subscription(parish_subscription),
            "change": (
                ParishSubscriptionChangeDetails.from_orm(latest_change)
                if latest_change
                else None
            ),
        }

        return response

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during parish subscription features query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during parish subscription features query!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# update parish, generate new slug if parish name has been changed
@router.put(
    "/update/{parish_id}",
    summary="Update parish and reassign member numbers",
)
def update_parish(
    request: Request,
    parish_id: UUID,
    parish_update: ParishUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Request to update parish details...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

        changed = False

        # update parish name and regenerate slug if changed
        current_name = parish.parish_data.get("parish_name")
        new_name = parish_update.parish_data.get("parish_name")
        if new_name and new_name != current_name:
            slug = generate_unique_slug(new_name, db)
            parish.parish_data["parish_name"] = new_name
            parish.parish_data["parish_slug"] = slug
            changed = True
            logger.info("Updated parish name and slug!")

        # update member_number_prefix
        if (
            parish_update.member_number_prefix
            and parish_update.member_number_prefix != parish.member_number_prefix
        ):
            existing_prefix = (
                db.query(Parish)
                .filter(
                    Parish.member_number_prefix == parish_update.member_number_prefix,
                    Parish.id != parish.id,
                )
                .first()
            )
            if existing_prefix:
                logger.warning("409 | Member number prefix already exists!")
                raise HTTPException(
                    status_code=400,
                    detail="Member number prefix already exists for another parish!",
                )
            parish.member_number_prefix = parish_update.member_number_prefix
            changed = True
            logger.info("Updated member number prefix for parish!")

        # update member_number_suffix
        if (
            parish_update.member_number_suffix
            and parish_update.member_number_suffix != parish.member_number_suffix
        ):
            parish.member_number_suffix = parish_update.member_number_suffix
            changed = True
            logger.info("Updated member number suffix for parish!")

        # update contact_email
        new_email = parish_update.parish_data.get("contact_email")
        if new_email and new_email != parish.parish_data.get("contact_email"):
            parish.parish_data["contact_email"] = new_email
            changed = True
            logger.info("Updated contact_email for parish!")

        # update contact_phone
        new_phone = parish_update.parish_data.get("contact_phone")
        if new_phone and new_phone != parish.parish_data.get("contact_phone"):
            parish.parish_data["contact_phone"] = new_phone
            changed = True
            logger.info("Updated contact_phone for parish!")

        if changed:
            db.commit()

            logger.info("Committed parish updates for parish!")
            update_member_numbers(parish_id=parish.id, db=db)
            logger.info("Member numbers reassigned for parish members!")
        else:
            logger.info("No updates made to parish!")

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Parish updated and notification sent successfully!",
        )

        logger.info("201 | Parish updated and notification sent successfully!")

        return {"message": "Parish updated successfully!"}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during parish data update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during parish data update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# archive parish
@router.post(
    "/archive/{parish_id}",
    summary="Archive parish ",
)
async def archive_parish(
    parish_id: UUID,
    db=Depends(get_db),
):
    logger.info("Attempting to archive parish...")

    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish.is_archived = True
    db.add(parish)
    db.commit()
    db.refresh(parish)
    return {"message": "Parish successfuly archived!"}


# unarchive parish
@router.post(
    "/unarchive/{parish_id}",
    summary="Unarchive parish",
)
async def unarchive_parish(
    parish_id: UUID,
    db=Depends(get_db),
):
    logger.info("Attempting to unarchive parish data...")

    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish.is_archived = False
    db.add(parish)
    db.commit()
    db.refresh(parish)
    return {"message": "Parish successfuly unarchived!"}


# parish analytics
@router.get("/analytics/{parish_id}")
def get_parish_analytics(
    parish_id: str,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user),
):
    logger.info("Attempting to export all parish data...")
    # current user check
    user = db.query(User).filter(User.id == current_user_id).first()
    if not user:
        logger.info("404 | User not found!")
        raise HTTPException(status_code=404, detail="User not found!")
    parish_analytics = []
    # 1. User Engagement (logins last 30 days)
    login_data = (
        db.query(
            LoginActivity.timestamp.label("timestamp"),
            User.id.label("user_id"),
            User.first_name,
            User.last_name,
            User.email,
        )
        .join(User, User.id == LoginActivity.user_id)
        .filter(User.parish_id == parish_id)
        .filter(LoginActivity.timestamp >= datetime.utcnow() - timedelta(days=30))
        .order_by(LoginActivity.timestamp.desc())
        .all()
    )

    logins = [
        {
            "timestamp": str(row.timestamp),
            "user_id": str(row.user_id),
            "first_name": row.first_name,
            "last_name": row.last_name,
            "email": row.email,
        }
        for row in login_data
    ]

    # 2a. Parish Growth Summary (new users per month)
    users_data = (
        db.query(
            extract("year", User.created_at).label("year"),
            extract("month", User.created_at).label("month"),
            func.count(User.id).label("new_users"),
        )
        .filter(User.parish_id == parish_id)
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    users_summary = [
        {"year": int(row.year), "month": int(row.month), "new_users": row.new_users}
        for row in users_data
    ]

    # 2b. Parish Growth Details (actual users)
    users_details = (
        db.query(
            User.id,
            User.first_name,
            User.last_name,
            User.email,
            User.created_at,
        )
        .filter(User.parish_id == parish_id)
        .order_by(User.created_at.desc())
        .all()
    )

    users = [
        {
            "user_id": str(row.id),
            "first_name": row.first_name,
            "last_name": row.last_name,
            "email": row.email,
            "joined_at": str(row.created_at),
        }
        for row in users_details
    ]

    # 3. Parishioner Growth (members joining per month)
    members_data = (
        db.query(
            extract("year", Member.created_at).label("year"),
            extract("month", Member.created_at).label("month"),
            func.count(Member.id).label("new_members"),
        )
        .filter(Member.parish_id == parish_id)
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )
    members_growth = [
        {"year": int(row.year), "month": int(row.month), "new_members": row.new_members}
        for row in members_data
    ]

    # 4. All actual members in the parish
    all_members = (
        db.query(Member)
        .filter(Member.parish_id == parish_id)
        .order_by(Member.created_at.desc())
        .all()
    )

    members_list = []
    for m in all_members:
        data = m.member_data or {}
        members_list.append(
            {
                "id": str(m.id),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "joined_at": m.created_at.isoformat(),
            }
        )

    # 4a. Collections (aggregated per month)
    collections_data = (
        db.query(
            extract("year", Collection.created_at).label("year"),
            extract("month", Collection.created_at).label("month"),
            func.sum(Collection.amount).label("total_collections"),
        )
        .filter(Collection.parish_id == parish_id)
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )
    collections = [
        {
            "year": int(row.year),
            "month": int(row.month),
            "total_collections": float(row.total_collections or 0),
        }
        for row in collections_data
    ]

    # 4b. Actual Collection Records
    collections_list = (
        db.query(Collection)
        .filter(Collection.parish_id == parish_id)
        .order_by(Collection.created_at.desc())
        .all()
    )
    collections_detail = [
        {
            "id": str(c.id),
            "amount": float(c.amount),
            "contributor_id": str(c.member_id) if c.member_id else None,
            "project_id": str(c.project_id) if hasattr(c, "project_id") else None,
            "created_at": c.created_at.isoformat(),
        }
        for c in collections_list
    ]

    parish_analytics.append(
        {
            "parish_analytics": {
                "parish_id": parish_id,
                "user_engagement": logins,
                "users_growth": users,
                "members_growth": members_growth,
                "members": members_list,
                "collections": collections,
                "collections_detail": collections_detail,
            }
        }
    )

    return parish_analytics
