from typing import Optional
from uuid import UUID
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
)
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from api.serializers import serialize_fund_projects
from db.models.fund_project import FundProject
from db.models.parish import Parish
from db.models.user import User
from db.session import get_db
from schemas.fund_project_schema import (
    PaginatedFundProjectResponse,
    FundProjectCreate,
    FundProjectDetails,
    FundProjectUpdate,
)
from sqlalchemy.exc import SQLAlchemyError
from log_config import logger
from schemas.notification_schema import NotificationType
from services.auth_service import (
    get_current_user,
)
from services.notification_service import create_notification
from services.user_service import get_user_details
from utils.account_suffix_generator import generate_account_suffix

router = APIRouter()


# retrieve db/parish fund project count with parish filter
@router.get(
    "/count",
    summary="Fetch all count of fund projects records (optionally filtered by parish)",
)
async def count_fund_projects(
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve all fund project count...")
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
                    detail="Priests must specify a parish_id to view fund project count.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view fund project count from another parish.",
                )

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                logger.warning(f"404 | Parish {parish_id} not found")
                raise HTTPException(status_code=404, detail="Parish not found")

            count = (
                db.query(FundProject).filter(FundProject.parish_id == parish_id).count()
            )
        else:
            count = db.query(FundProject).count()

        logger.info("200 | Fund project count fetched successfully")
        return {"total": count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during fund project count retrieval!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during fund project count retrieval!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retrieve db/parish fund projects with parish filter
@router.get(
    "/all",
    response_model=PaginatedFundProjectResponse,
    summary="Fetch all fund project records (optionally filtered by parish)",
)
async def retrieve_all_fund_projects(
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
        logger.info("Attempting to retrieve all fund project data...")
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
                    detail="Priests must specify a parish_id to view fund project data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view fund project data from another parish.",
                )

        offset = (page - 1) * page_size

        # model relationship connector
        query = db.query(FundProject).options(joinedload(FundProject.parish))

        # archive filter
        if is_archived is None:
            query = query.filter(FundProject.is_archived == False)
        else:
            query = query.filter(FundProject.is_archived == is_archived)

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                logger.warning(f"404 | Parish {parish_id} not found")
                raise HTTPException(status_code=404, detail="Parish not found")
            query = query.filter(FundProject.parish_id == parish_id)

        # search parameter
        if search:
            query = query.filter(
                or_(
                    FundProject.name.ilike(f"%{search}%"),
                    FundProject.account_suffix.ilike(f"%{search}%"),
                )
            )

        # sort parameter
        if sort_by and hasattr(FundProject, sort_by):
            column = getattr(FundProject, sort_by)
            if sort_order == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())
        else:
            query = query.order_by(FundProject.created_at.desc())

        total = query.count()
        fund_projects = query.offset(offset).limit(page_size).all()

        logger.info("200 | Fund projects retrieved successfully")

        return {
            "items": serialize_fund_projects(fund_projects),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during fund project data retrieval!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception as e:
        db.rollback()
        logger.error(
            f"500 | Unexpected error during all fund project data query! {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# create fund project
@router.post(
    "/create",
    response_model=FundProjectDetails,
    summary="Create a fund project, linked to a parish",
)
async def create_fund_project(
    fund_project_create: FundProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to create a fund project...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        name_lower = fund_project_create.name.strip().lower()

        existing = (
            db.query(FundProject)
            .filter(func.lower(FundProject.name) == name_lower)
            .first()
        )
        if existing:
            logger.warning("400 | Fund project already exists")
            raise HTTPException(
                status_code=400,
                detail="Fund project already exists.",
            )

        account_suffix = generate_account_suffix(
            fund_project_create.name,
            fund_project_create.parish_id,
            db,
        )

        new_project = FundProject(
            **fund_project_create.model_dump(),
            account_suffix=account_suffix,
            current_amount=0,
        )

        db.add(new_project)
        try:
            db.commit()
            db.refresh(new_project)
        except Exception:
            db.rollback()
            logger.error("500 | Commit failed while creating fund project")
            raise HTTPException(status_code=500, detail="Database error")

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Fund project record created successfully!",
        )

        logger.info("201 | Fund project record created successfully!")
        return new_project

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during fund project creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during fund project creation!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# get fund project details
@router.get(
    "/details/{fund_project_id}",
    response_model=FundProjectDetails,
    summary="Get details of an existing fund project",
)
async def retrieve_fund_project_details(
    fund_project_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        logger.info("Attempting to retrieve fund project details...")
        fund_project = (
            db.query(FundProject)
            .options(joinedload(FundProject.parish))
            .filter(FundProject.id == fund_project_id)
            .first()
        )

        if fund_project is None:
            logger.warning("404 | Fund project not found")
            raise HTTPException(status_code=404, detail="Fund project not found")

        logger.info("200 | Fund project retrieved successfully")
        return fund_project

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during fund project details retrieval!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during fund project details retrieval!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# update fund project
@router.put(
    "/update/{fund_project_id}",
    response_model=FundProjectDetails,
    summary="Update an existing fund project",
)
async def update_fund_project(
    fund_project_id: UUID,
    fund_project_update: FundProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to update a fund project...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")
        fund_project = (
            db.query(FundProject).filter(FundProject.id == fund_project_id).first()
        )

        if not fund_project:
            logger.warning("404 | Fund project not found for update")
            raise HTTPException(status_code=404, detail="Fund project not found")

        update_data = fund_project_update.dict(exclude_unset=True)
        new_name = update_data.get("name", fund_project.name)

        # duplicate data check
        duplicate = (
            db.query(FundProject)
            .filter(FundProject.id != fund_project_id, FundProject.name == new_name)
            .first()
        )

        if duplicate:
            logger.warning("409 | Fund project name conflict")
            raise HTTPException(
                status_code=409,
                detail="A fund project with this name already exists.",
            )

        # update project
        for key, value in update_data.items():
            setattr(fund_project, key, value)

        db.commit()
        db.refresh(fund_project)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message=f"Fund project record updated successfully!",
        )

        logger.info("201 | Fund project record updated successfully!")
        return fund_project

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during fund project update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during fund project update!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# archive fund project
@router.post(
    "/archive/{fund_project_id}",
    summary="Archive fund project",
)
async def archive_fund_project(
    fund_project_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive fund project...")
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
                detail="Priests must specify a parish_id to archive fund project data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive fund project data from another parish.",
            )

    fund_project = (
        db.query(FundProject).filter(FundProject.id == fund_project_id).first()
    )
    if not fund_project:
        raise HTTPException(status_code=404, detail="Fund project not found!")
    fund_project.is_archived = True
    db.add(fund_project)
    db.commit()
    db.refresh(fund_project)
    return {"message": "Fund project successfuly archived!"}


# unarchive fund project
@router.post("/unarchive/{fund_project_id}", summary="Unarchive fund project")
async def unarchive_fund_project(
    fund_project_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive data...")
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
    fund_project = (
        db.query(FundProject).filter(FundProject.id == fund_project_id).first()
    )
    if not fund_project:
        raise HTTPException(status_code=404, detail="Fund project not found!")
    fund_project.is_archived = False
    db.add(fund_project)
    db.commit()
    db.refresh(fund_project)
    return {"message": "Fund project successfuly unarchived!"}
