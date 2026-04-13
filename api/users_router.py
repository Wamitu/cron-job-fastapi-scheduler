from datetime import timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload
from api.serializers import serialize_users
from db.models.login_activity import LoginActivity
from db.models.parish import Parish
from db.models.user import User
from db.session import get_db
from log_config import logger
from schemas.user_schema import (
    PaginatedUserResponse,
    Token,
    UserDetails,
    UserLogin,
    UserUpdate,
)
from services.auth_service import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_jwt_token,
    get_current_user,
    verify_password,
)
from services.user_service import get_user_by_email, get_user_details
from services.notification_service import create_notification
from schemas.notification_schema import NotificationType
from utils.phone_number_eligibility_check import is_valid_phone_number


router = APIRouter()


# retrieve db/parish user count with parish filter
@router.get(
    "/count",
    summary="Get count of all users (optionally filtered by parish_id)",
)
async def count_users(
    parish_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to fetch user count...")
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
                    detail="Priests must specify a parish_id to view user count.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view user count from another parish.",
                )

        # parish filter
        if parish_id:
            logger.info(f" Filtering count by parish_id: {parish_id}")
            query = db.query(User).filter(User.parish_id == parish_id)
        else:
            logger.info(" Counting users across all parishes")
            query = db.query(User)

        total_count = query.count()
        logger.info(f" Total users found!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as db_err:
        logger.error(f" Database error while counting users!: {str(db_err)}")
        raise HTTPException(
            status_code=500, detail="Database error occurred while counting users!"
        )

    except Exception as e:
        logger.error(f" Unexpected error while counting users!: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Unexpected error occurred while counting users!"
        )


# retrieve db/parish users with parish filter
@router.get(
    "/all",
    response_model=PaginatedUserResponse,
    summary="Get all users in the system (optionally filtered by parish_id)",
)
async def retrieve_all_users(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None),
    is_archived: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to fetch users...")

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

        # role and parish based restrictions
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view user data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view user data from another parish.",
                )

        # pagination offset
        offset = (page - 1) * page_size

        # build query
        query = db.query(User).options(
            joinedload(User.role),
            joinedload(User.parish),
            joinedload(User.diocese),
        )

        # archive filter
        if is_archived is None:
            query = query.filter(User.is_archived == False)
        else:
            query = query.filter(User.is_archived == is_archived)

        # parish filter
        if parish_id:
            logger.info("Filtering users by parish_id...")
            query = query.filter(User.parish_id == parish_id)

        # search parameter
        if search:
            logger.info("Searching users with query...")
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    User.phone.ilike(f"%{search}%"),
                )
            )

        # sorting
        if sort_by and hasattr(User, sort_by):
            column = getattr(User, sort_by)
            logger.info("Sorting by sort parameter...")
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            logger.info("Sorting by default: created_at desc...")
            query = query.order_by(User.created_at.desc())

        # pagination + results
        total_count = query.count()
        users = query.offset(offset).limit(page_size).all()

        logger.info("Users retrieved successfully!")

        return {
            "message": "Users retrieved successfully!",
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
        logger.error(f"Database error while retrieving users!: {str(db_err)}")
        raise HTTPException(
            status_code=500, detail="Database error occurred while retrieving users!"
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"500 | Unexpected error during all user data query! {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# # create user
# @router.post(
#     "/create",
#     response_model=UserDetails,
#     summary="Create a user, linked to a parish",
#     dependencies=[
#         Depends(require_roles_by_titles("Priest")),
#     ],
# )
# async def create_user(user_create: UserCreate, db=Depends(get_db)):
#     try:
#         logger.info("Attempting to create user...")

#         # Check parish existence
#         db_parish = db.query(Parish).filter(Parish.id == user_create.parish_id).first()
#         if not db_parish:
#             logger.warning("404 | Parish not found!")
#             raise HTTPException(status_code=404, detail="Parish does not exist!")

#         # Check role existence
#         db_role = db.query(Role).filter(Role.id == user_create.role_id).first()
#         if not db_role:
#             logger.warning("404 | Role not found!")
#             raise HTTPException(status_code=404, detail="Role does not exist!")

#         # Check for existing user by email
#         if db.query(User).filter(User.email == user_create.email).first():
#             logger.warning("409 | User with same email already exists!")
#             raise HTTPException(
#                 status_code=400, detail="A user with this email already exists!"
#             )

#         # Validate phone format
#         if not is_valid_phone_number(user_create.phone):
#             logger.warning("400 | Invalid phone number format!")
#             raise HTTPException(
#                 status_code=400,
#                 detail="Invalid phone number format. Must be in 2547XXXXXXXX format!",
#             )

#         # Check for existing user by phone
#         if db.query(User).filter(User.phone == user_create.phone).first():
#             logger.warning("409 | User with same phone number already exists!")
#             raise HTTPException(
#                 status_code=409, detail="A user with this phone number already exists!"
#             )

#         # Create new user
#         hashed_pw = hash_password(user_create.password)
#         new_user = User(
#             parish_id=user_create.parish_id,
#             first_name=user_create.first_name,
#             last_name=user_create.last_name,
#             email=user_create.email,
#             phone=user_create.phone,
#             hashed_password=hashed_pw,
#             role_id=user_create.role_id,
#             is_active=True,
#         )

#         db.add(new_user)
#         db.commit()
#         db.refresh(new_user)

#         logger.info("201 | User created successfully!")
#         return new_user

#     except HTTPException as e:
#         logger.warning(f"{e.status_code} | {e.detail}")
#         raise

#     except SQLAlchemyError as db_err:
#         logger.error(f" Database error while creating user!: {str(db_err)}")
#         raise HTTPException(
#             status_code=500, detail="A database error occurred while creating the user!"
#         )

#     except Exception as e:
#         logger.error(f" Unexpected error: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail="An unexpected error occurred while creating the user!",
#         )


# get user details
@router.get(
    "/details/{user_id}",
    response_model=UserDetails,
    summary="Get details of an existing user",
)
async def retrieve_user_details(
    user_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        logger.info("Attempting to retrieve user details..")
        db_user = (
            db.query(User)
            .options(joinedload(User.role), joinedload(User.parish))
            .filter(User.id == user_id)
            .first()
        )

        if db_user is None:
            logger.warning("404 | User not found!")
            raise HTTPException(status_code=404, detail="User not found!")

        logger.info("200 | Successfully retrieved user!")
        return db_user

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as db_err:
        logger.error(f" Database error while retrieving user!: {str(db_err)}")
        raise HTTPException(
            status_code=500, detail="Database error while retrieving user!"
        )

    except Exception as e:
        logger.error(f" Unexpected error retrieving user!: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Unexpected error while retrieving user!"
        )


# update user
@router.put(
    "/update/{user_id}",
    response_model=UserDetails,
    summary="Update details of an existing user",
)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
):
    try:
        logger.info("Attempting to update user record...")

        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            logger.warning("404 | User not found!")
            raise HTTPException(status_code=404, detail="User not found!")

        update_data = user_update.dict(exclude_unset=True)
        #  Phone validation & uniqueness
        if "phone" in update_data:
            phone = update_data["phone"]
            if not is_valid_phone_number(phone):
                logger.warning("4-- | Invalid phone format!")
                raise HTTPException(
                    status_code=400, detail="Invalid phone number format!"
                )
            if db.query(User).filter(User.phone == phone, User.id != user_id).first():
                logger.warning("409 | Phone number already in use!")
                raise HTTPException(
                    status_code=400, detail="Phone number already in use!"
                )

        #  Email uniqueness
        if "email" in update_data:
            email = update_data["email"]
            if db.query(User).filter(User.email == email, User.id != user_id).first():
                logger.warning("409 | Email already in use!")
                raise HTTPException(status_code=400, detail="Email already in use")

        #  Apply updates
        for key, value in update_data.items():
            logger.info("Updating user details...")
            setattr(db_user, key, value)

        db.commit()
        db.refresh(db_user)

        logger.info("Successfully updated user!")
        return db_user

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during update!: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error!: " + str(e))

    except Exception as e:
        logger.error(f"Unexpected error during update: {str(e)}")
        raise HTTPException(status_code=400, detail="Update failed!: " + str(e))


# login
@router.post("/login", response_model=Token, summary="User login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    try:
        logger.info("Attempting to login...")

        db_user = get_user_by_email(db, email=user.email)
        if not db_user:
            logger.warning("404 | Login failed: user not found!")
            raise HTTPException(status_code=400, detail="Incorrect email or password!")

        if not db_user.is_active:
            logger.warning("400 | Login failed: user is inactive!")
            raise HTTPException(
                status_code=403, detail="Account is inactive. Please contact support!"
            )

        if not verify_password(user.password, db_user.hashed_password):
            logger.warning("400 | Login failed: invalid password!")
            raise HTTPException(status_code=400, detail="Incorrect email or password!")

        # save login timestamps
        login_activity = LoginActivity(user_id=db_user.id)
        db.add(login_activity)
        db.commit()

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_jwt_token(
            data={"sub": str(db_user.id)}, expires_delta=access_token_expires
        )

        logger.info("200 | Login successful!")

        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except Exception:
        logger.exception(f"Unexpected error during login for email!:")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred during login!"
        )


# validate token
@router.get(
    "/validate-token",
    summary="Validate token",
)
async def verify_token(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    logger.info("Attempting to validate user token...")

    try:
        user = get_user_details(db, current_user)

        if not user:
            logger.warning("404 | Token validation failed: user not found!")
            raise HTTPException(status_code=404, detail="User not found!")

        logger.info(f"Token is valid for user!")

        return {
            "valid": True,
            "user_id": str(user.id),  # Ensure UUID is returned as string
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as db_err:
        logger.error(f"Database error during token validation!: {str(db_err)}")
        raise HTTPException(
            status_code=500, detail="Database error during token validation!"
        )

    except Exception as e:
        logger.error(f"Unexpected error during token validation!: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Unexpected error during token validation!"
        )


# get current profile
@router.get("/me", response_model=UserDetails, summary="Get current user profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user = (
            db.query(User)
            .options(joinedload(User.role), joinedload(User.parish))
            .filter(User.id == current_user.id)
            .first()
        )

        if not user:
            logger.warning("404 | Profile fetch failed: User not found!")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found!"
            )

        logger.info("Successfully fetched user profile!")
        return user

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as db_err:
        logger.error(f"Database error while fetching profile!: {str(db_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching profile!",
        )

    except Exception as e:
        logger.error(f"Unexpected error while fetching profile!: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while fetching profile!",
        )


# update user
@router.put(
    "/me",
    response_model=UserUpdate,
    summary="Update current logged in user",
)
async def update_user(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    logger.info("Attempting to update current user...")

    user = get_user_details(db, current_user)
    if user is None:
        logger.warning("404 | User not found!")
        raise HTTPException(status_code=403, detail="User not found!")

    try:
        update_data = user_update.dict(exclude_unset=True)
        logger.info(f"Updating user with data!")

        if user_update.phone:
            if not is_valid_phone_number(user_update.phone):
                logger.warning("Invalid phone number format!")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid phone number format. Must be in 2547XXXXXXXX format!",
                )
            user.phone = user_update.phone
            logger.info(f"Phone updated!")

        if user_update.first_name:
            user.first_name = user_update.first_name
            logger.info(f"First name updated!")

        if user_update.last_name:
            user.last_name = user_update.last_name
            logger.info(f"Last name updated!")

        if user_update.email:
            user.email = user_update.email
            logger.info("Email updated!")

        db.commit()
        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message="Your profile has been updated successfully!",
        )
        logger.info("200 | Successfully updated user!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during user update!: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error: " + str(e))

    except Exception as e:
        logger.error(f"Unexpected error during user update!: {str(e)}")
        raise HTTPException(status_code=400, detail="Error: " + str(e))

    return user


# archive user
@router.post(
    "/archive/{user_id}",
    summary="Archive user",
)
async def archive_user(
    user_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive user data...")
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    role_title = user.role.title if hasattr(user.role, "title") else None

    # role and parish based check
    if role_title == "Priest":
        if parish_id is None:
            raise HTTPException(
                status_code=403,
                detail="Priests must specify a parish_id to archive user data.",
            )

        # check that parish exists
        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive user data from another parish.",
            )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")
    user.is_archived = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User successfuly archived!"}


# unarchive user
@router.post("/unarchive/{user_id}", summary="Unarchive user")
async def unarchive_user(
    user_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive user data...")
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    role_title = user.role.title if hasattr(user.role, "title") else None

    # role and parish based check
    if role_title == "Priest":
        if parish_id is None:
            raise HTTPException(
                status_code=403,
                detail="Priests must specify a parish_id to unarchive user data.",
            )

        # check that parish exists
        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to unarchive user data from another parish.",
            )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")
    user.is_archived = False
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User successfuly unarchived!"}
