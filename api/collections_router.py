from typing import Literal, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session, joinedload
from api.serializers import serialize_collections
from db.models.receipt import Receipt
from db.models.user import User
from log_config import logger
from db.models.collection import Collection
from db.models.fund_project import FundProject
from db.models.parish import Parish
from db.models.sacrament import SacramentRecord
from db.session import get_db
from schemas.collection_schema import (
    CollectionCreate,
    CollectionDetails,
    PaginatedCollectionResponse,
)
from sqlalchemy.exc import SQLAlchemyError
from schemas.fund_project_schema import FundProjectStatus
from schemas.notification_schema import NotificationType
from services.auth_service import (
    get_current_user,
)
from services.notification_service import create_notification
from services.user_service import get_user_details
from utils.receipt_no_generator import generate_receipt_number

router = APIRouter()


# retrieve db/parish collection count with parish filter
@router.get(
    "/count",
    summary="Fetch all count of collection records (optionally filtered by parish)",
)
async def count_collection_records(
    parish_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Retrieving all collection count...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view collection count.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view collection count from another parish.",
                )

        query = db.query(Collection)

        if parish_id:
            query = query.filter(Collection.parish_id == parish_id)

        total_count = query.count()
        logger.info("200 | Collection count fetched successfully!")
        return {"total": total_count}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | Database error during collection count!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error("500 | Unexpected error during collection count!", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retrieve db/parish collections with parish filter
@router.get(
    "/all",
    response_model=PaginatedCollectionResponse,
    summary="Fetch all collection records (optionally filtered by parish)",
)
async def retrieve_all_parish_collections(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None),
    project_id: Optional[UUID] = Query(None),
    is_archived: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Literal["asc", "desc"] = Query("asc"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to retrieve all collections...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        role_title = user.role.title if hasattr(user.role, "title") else None

        # role and parish based check
        if role_title == "Priest":
            if parish_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Priests must specify a parish_id to view collection data.",
                )
            if parish_id != user.parish_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view collection data from another parish.",
                )

        offset = (page - 1) * page_size

        # model relationship connector
        query = db.query(Collection).options(joinedload(Collection.recorded_by_user))

        # archive filter
        if is_archived is None:
            query = query.filter(Collection.is_archived == False)
        else:
            query = query.filter(Collection.is_archived == is_archived)

        # parish filter
        if parish_id:
            query = query.filter(Collection.parish_id == parish_id)

        # project filter
        if project_id:
            query = query.filter(Collection.project_id == project_id)

        # search parameter
        if search:
            search = search.lower()
            query = query.filter(
                or_(
                    func.lower(cast(Collection.collection_type, String)).like(
                        f"%{search}%"
                    ),
                    func.lower(cast(Collection.collection_method, String)).like(
                        f"%{search}%"
                    ),
                )
            )

        # sorting
        allowed_sort_fields = {"collection_type", "collection_method", "created_at"}

        if sort_by:
            if sort_by not in allowed_sort_fields:
                logger.warning(f"400 | Invalid sort_by field: {sort_by}")
                raise HTTPException(status_code=400, detail="Invalid sort_by field.")
            column = (
                cast(getattr(Collection, sort_by), String)
                if sort_by != "created_at"
                else getattr(Collection, sort_by)
            )
            query = query.order_by(
                column.desc() if sort_order == "desc" else column.asc()
            )
        else:
            query = query.order_by(Collection.created_at.desc())

        total_count = query.count()
        collections = query.offset(offset).limit(page_size).all()

        logger.info("200 | Collections retrieved successfully!")

        return {
            "items": serialize_collections(collections),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "pages": (total_count + page_size - 1) // page_size,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as db_err:
        logger.error(f"Database error while retrieving collections!: {str(db_err)}")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while retrieving collections!",
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"500 | Unexpected error during all user data query! {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# create collection linked to a parish, for a sacrament record, fund project, or neither
@router.post(
    "/create",
    response_model=CollectionDetails,
    summary="Create a collection, linked to a parish",
)
def create_collection(
    collection_create: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to make a collection...")
        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        db_parish = (
            db.query(Parish).filter(Parish.id == collection_create.parish_id).first()
        )
        if not db_parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

        # Create new collection
        new_collection = Collection(
            **collection_create.model_dump(), recorded_by=user.id
        )

        # Sacrament Record logic
        if collection_create.sacrament_record_id:
            sacrament_record = (
                db.query(SacramentRecord)
                .filter_by(id=collection_create.sacrament_record_id)
                .first()
            )
            if not sacrament_record:
                logger.warning("404 | Sacrament record not found!")
                raise HTTPException(
                    status_code=404, detail="Sacrament record not found!"
                )

            remaining_balance = (
                sacrament_record.outstanding_balance - collection_create.amount
            )

            sacrament_record.outstanding_balance = max(0, remaining_balance)
            sacrament_record.is_settled = remaining_balance <= 0
            db.add(sacrament_record)

        # Fund project logic
        elif collection_create.project_id:
            project = (
                db.query(FundProject).filter_by(id=collection_create.project_id).first()
            )
            if not project:
                logger.warning("404 | Project not found!")
                raise HTTPException(status_code=404, detail="Project not found!")

            project.current_amount += collection_create.amount
            if project.current_amount >= project.target_amount:
                project.status = FundProjectStatus.completed
            db.add(project)

        db.add(new_collection)
        db.flush()

        receipt_no = generate_receipt_number(db, db_parish.id)

        new_receipt = Receipt(
            parish_id=db_parish.id,
            subscription_payment_id=None,
            collection_id=new_collection.id,
            receipt_no=receipt_no,
            generated_by=user.id,
        )

        db.add(new_receipt)
        db.commit()
        db.refresh(new_collection)
        db.refresh(new_receipt)

        create_notification(
            db=db,
            user_id=user.id,
            parish_id=user.parish_id,
            notification_type=NotificationType.info,
            message="Collection record created successfully!",
        )

        logger.info("201 | Collection record created successfully!")
        return CollectionDetails.from_orm(new_collection)

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | Database error during collection creation!", exc_info=True)
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during collection creation!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# retrieve collection details
@router.get(
    "/details/{collection_id}",
    response_model=CollectionDetails,
    summary="Get details of an existing collection",
)
async def get_collection_details(
    collection_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        logger.info("Attempting to retrieve collection details...")
        collection = (
            db.query(Collection)
            .options(joinedload(Collection.recorded_by_user))
            .filter(Collection.id == collection_id)
            .first()
        )

        if not collection:
            logger.warning("404 | Collection not found!")
            raise HTTPException(status_code=404, detail="Collection not found!")

        logger.info("200 | Retrieved collection details successfully!")
        return collection

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during collection details query!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during collection details query!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")


# archive collection
@router.post(
    "/archive/{collection_id}",
    summary="Archive collection",
)
async def archive_collection(
    collection_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive collection data ...")
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
                detail="Priests must specify a parish_id to archive collection data.",
            )

        # check that parish exists
        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive collection data from another parish.",
            )

    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found!")
    collection.is_archived = True
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return {"message": "Collection successfuly archived!"}


# unarchive collection
@router.post("/unarchive/{collection_id}", summary="Unarchive collection")
async def unarchive_collection(
    collection_id: UUID,
    db=Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive certificate data...")
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
                detail="Priests must specify a parish_id to archive collection data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive collection data from another parish.",
            )

    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found!")
    collection.is_archived = False
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return {"message": "Collection successfuly unarchived!"}
