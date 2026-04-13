from db.models.collection import Collection
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func
from db.models.attendance import Attendance
from db.models.certificate import Certificate
from db.models.fund_project import FundProject
from db.models.member import Member
from db.models.parish import Parish
from db.models.role import Role
from db.models.sacrament import Sacrament, SacramentRecord
from db.models.user import User
from db.models.user_invite import InvitedUser
from db.session import get_db
from sqlalchemy.orm import Session
from log_config import logger
from services.auth_service import get_current_user
from services.user_service import get_user_details
from sqlalchemy.exc import SQLAlchemyError


router = APIRouter()


# attendance analytics
@router.get(
    "/attendance-records/analytics",
    summary="Attendance analytics with totals, averages, and parish filters",
)
def get_attendance_analytics(
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    is_archived: Optional[bool] = Query(None, description="Filter by archive status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate attendance records analytics...")
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")
        # Base query
        query = db.query(Attendance).filter(Attendance.is_archived == False)

        if parish_id:
            query = query.filter(Attendance.parish_id == parish_id)

        records = query.all()

        # archive filter
        if is_archived is None:
            query = query.filter(Certificate.is_archived == False)
        else:
            query = query.filter(Certificate.is_archived == is_archived)

        if not records:
            return {"message": "No attendance records found."}

        # Totals
        total_visitors = sum(r.data.get("visitors_present", 0) for r in records)
        total_children = sum(r.data.get("children_present", 0) for r in records)
        total_men = sum(r.data.get("men_present", 0) for r in records)
        total_women = sum(r.data.get("women_present", 0) for r in records)

        totals = {
            "visitors": total_visitors,
            "children": total_children,
            "men": total_men,
            "women": total_women,
        }

        # Averages (rounded, no decimals)
        count = len(records)
        averages = {
            "visitors": round(total_visitors / count),
            "children": round(total_children / count),
            "men": round(total_men / count),
            "women": round(total_women / count),
        }

        # Parish with most attendance (only if no parish filter is applied)
        parish_with_most_attendance = None
        if not parish_id:
            parish_totals = (
                db.query(
                    Attendance.parish_id,
                    func.sum(
                        Attendance.data["visitors_present"].as_integer()
                        + Attendance.data["children_present"].as_integer()
                        + Attendance.data["men_present"].as_integer()
                        + Attendance.data["women_present"].as_integer()
                    ).label("total"),
                )
                .filter(Attendance.is_archived == False)
                .group_by(Attendance.parish_id)
                .order_by(
                    func.sum(
                        Attendance.data["visitors_present"].as_integer()
                        + Attendance.data["children_present"].as_integer()
                        + Attendance.data["men_present"].as_integer()
                        + Attendance.data["women_present"].as_integer()
                    ).desc()
                )
                .first()
            )

            if parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == parish_totals.parish_id)
                    .scalar()
                )
                parish_with_most_attendance = {
                    "parish_id": parish_totals.parish_id,
                    "parish_name": parish_name,
                    "total_attendance": parish_totals.total,
                }

        # Monthly breakdown (grouping by year-month)
        monthly_data = db.query(
            func.date_trunc("month", Attendance.event_date).label("month"),
            func.sum(Attendance.data["visitors_present"].as_integer()).label(
                "visitors"
            ),
            func.sum(Attendance.data["children_present"].as_integer()).label(
                "children"
            ),
            func.sum(Attendance.data["men_present"].as_integer()).label("men"),
            func.sum(Attendance.data["women_present"].as_integer()).label("women"),
        ).filter(Attendance.is_archived == False)

        if parish_id:
            monthly_data = monthly_data.filter(Attendance.parish_id == parish_id)

        monthly_data = monthly_data.group_by(
            func.date_trunc("month", Attendance.event_date)
        ).all()

        monthly_breakdown = [
            {
                "month": m.month.strftime("%Y-%m"),
                "visitors": m.visitors or 0,
                "children": m.children or 0,
                "men": m.men or 0,
                "women": m.women or 0,
            }
            for m in monthly_data
        ]

        return {
            "totals": totals,
            "averages": averages,
            "parish_with_most_attendance": parish_with_most_attendance,
            "monthly_breakdown": monthly_breakdown,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | DB error during attendance records analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating attendance records analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during attendance records analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating attendance records analytics generation.",
        )


# certificates analytics
@router.get(
    "/certificates/analytics",
    summary="Certificate analytics with totals, averages, and parish filters",
)
async def get_certificate_analytics(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    is_archived: Optional[bool] = Query(None, description="Filter by archive status"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate certificate analytics...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        query = db.query(Certificate)

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

        records = query.all()
        if not records:
            return {"message": "No certificate records found."}

        # totals & Averages
        total_certificates = len(records)

        totals = {"total_certificates": total_certificates}

        # parish with most certificates (only if no parish filter)
        parish_with_most_certificates = None
        if not parish_id:
            parish_totals = (
                db.query(
                    Certificate.parish_id,
                    func.count(Certificate.id).label("total"),
                )
                .filter(Certificate.is_archived == False)
                .group_by(Certificate.parish_id)
                .order_by(func.count(Certificate.id).desc())
                .first()
            )
            if parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == parish_totals.parish_id)
                    .scalar()
                )
                parish_with_most_certificates = {
                    "parish_id": parish_totals.parish_id,
                    "parish_name": parish_name,
                    "total_certificates": parish_totals.total,
                }

        # hierarchy of parishes with most to least certificates
        parish_hierarchy = None
        if not parish_id:
            parish_totals = (
                db.query(
                    Certificate.parish_id,
                    func.count(Certificate.id).label("total"),
                )
                .filter(Certificate.is_archived == False)
                .group_by(Certificate.parish_id)
                .order_by(func.count(Certificate.id).desc())
                .all()
            )

            parish_hierarchy = []
            for p in parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == p.parish_id)
                    .scalar()
                )
                parish_hierarchy.append(
                    {
                        "parish_id": p.parish_id,
                        "parish_name": parish_name,
                        "total_certificates": p.total,
                    }
                )

        # monthly breakdown
        monthly_data = db.query(
            func.date_trunc("month", Certificate.created_at).label("month"),
            func.count(Certificate.id).label("total_certificates"),
        ).filter(
            Certificate.is_archived
            == (is_archived if is_archived is not None else False)
        )

        if parish_id:
            monthly_data = monthly_data.filter(Certificate.parish_id == parish_id)

        monthly_data = monthly_data.group_by(
            func.date_trunc("month", Certificate.created_at)
        ).all()

        monthly_breakdown = [
            {
                "month": m.month.strftime("%Y-%m"),
                "total_certificates": m.total_certificates,
            }
            for m in monthly_data
        ]

        logger.info("200 | Certificate analytics generated successfully!")
        return {
            "totals": totals,
            "parish_with_most_certificates": parish_with_most_certificates,
            "parish_hierarchy": parish_hierarchy,
            "monthly_breakdown": monthly_breakdown,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | DB error during certificates analytics generation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating certificates analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during certificates analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating certificates analytics generation.",
        )


# collections analytics
@router.get("/collections/analytics", summary="Get collection analytics")
def get_collection_analytics(
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate collection analytics...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        # Base query
        query = db.query(Collection)

        if parish_id is not None:
            query = query.filter(Collection.parish_id == parish_id)

        # total collections amount
        total_amount = query.with_entities(
            func.coalesce(func.sum(Collection.amount), 0)
        ).scalar()

        # total transactions
        total_transactions = query.with_entities(func.count(Collection.id)).scalar()

        # group by collection_type
        collections_by_type = (
            query.with_entities(
                Collection.collection_type,
                func.coalesce(func.sum(Collection.amount), 0),
            )
            .group_by(Collection.collection_type)
            .all()
        )

        # group by collection_method
        collections_by_method = (
            query.with_entities(
                Collection.collection_method,
                func.coalesce(func.sum(Collection.amount), 0),
            )
            .group_by(Collection.collection_method)
            .all()
        )

        # only compute per-parish breakdown if no parish_id filter
        collections_per_parish = []
        if parish_id is None:
            collections_per_parish = (
                db.query(
                    Collection.parish_id, func.coalesce(func.sum(Collection.amount), 0)
                )
                .group_by(Collection.parish_id)
                .all()
            )

        # monthly trend
        monthly_collections = (
            query.with_entities(
                func.date_trunc("month", Collection.created_at).label("month"),
                func.coalesce(func.sum(Collection.amount), 0).label("total"),
            )
            .group_by(func.date_trunc("month", Collection.created_at))
            .order_by("month")
            .all()
        )

        response = {
            "total_amount": float(total_amount),
            "total_transactions": total_transactions,
            "collections_by_type": [
                {"type": t.name, "total": float(total)}
                for t, total in collections_by_type
            ],
            "collections_by_method": [
                {"method": m.name, "total": float(total)}
                for m, total in collections_by_method
            ],
            "monthly_collections": [
                {"month": month.strftime("%Y-%m"), "total": float(total)}
                for month, total in monthly_collections
            ],
        }

        # include parish breakdown only if not filtering by parish
        if parish_id is None:
            response["collections_per_parish"] = [
                {"parish_id": str(pid), "total": float(total)}
                for pid, total in collections_per_parish
            ]

        return response

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | DB error during collections analytics generation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating collections analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during collections analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating collections analytics generation.",
        )


# fund projects analytics
@router.get(
    "/fund-projects/analytics",
    summary="Fund project analytics with totals, averages, and parish filters",
)
async def get_fund_projects_analytics(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    is_archived: Optional[bool] = Query(None, description="Filter by archive status"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate fund projects analytics...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        query = db.query(FundProject)

        # archive filter
        if is_archived is None:
            query = query.filter(FundProject.is_archived == False)
        else:
            query = query.filter(FundProject.is_archived == is_archived)

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                logger.warning("404 | Parish not found!")
                raise HTTPException(status_code=404, detail="Parish not found!")
            query = query.filter(FundProject.parish_id == parish_id)

        records = query.all()
        if not records:
            return {"message": "No fund project records found."}

        # totals & Averages
        total_fund_projects = len(records)

        totals = {"total_fund_projects": total_fund_projects}

        # parish with most fund projects (only if no parish filter)
        parish_with_most_fund_projects = None
        if not parish_id:
            parish_totals = (
                db.query(
                    FundProject.parish_id,
                    func.count(FundProject.id).label("total"),
                )
                .filter(FundProject.is_archived == False)
                .group_by(FundProject.parish_id)
                .order_by(func.count(FundProject.id).desc())
                .first()
            )
            if parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == parish_totals.parish_id)
                    .scalar()
                )
                parish_with_most_fund_projects = {
                    "parish_id": parish_totals.parish_id,
                    "parish_name": parish_name,
                    "total_fund_projects": parish_totals.total,
                }

        # hierarchy of parishes with most to least fund projects
        parish_hierarchy = None
        if not parish_id:
            parish_totals = (
                db.query(
                    FundProject.parish_id,
                    func.count(FundProject.id).label("total"),
                )
                .filter(FundProject.is_archived == False)
                .group_by(FundProject.parish_id)
                .order_by(func.count(FundProject.id).desc())
                .all()
            )

            parish_hierarchy = []
            for p in parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == p.parish_id)
                    .scalar()
                )
                parish_hierarchy.append(
                    {
                        "parish_id": p.parish_id,
                        "parish_name": parish_name,
                        "total_fund_projects": p.total,
                    }
                )

        # monthly breakdown
        monthly_data = db.query(
            func.date_trunc("month", FundProject.created_at).label("month"),
            func.count(FundProject.id).label("total_fund_projects"),
        ).filter(
            FundProject.is_archived
            == (is_archived if is_archived is not None else False)
        )

        if parish_id:
            monthly_data = monthly_data.filter(FundProject.parish_id == parish_id)

        monthly_data = monthly_data.group_by(
            func.date_trunc("month", FundProject.created_at)
        ).all()

        monthly_breakdown = [
            {
                "month": m.month.strftime("%Y-%m"),
                "total_fund_projects": m.total_fund_projects,
            }
            for m in monthly_data
        ]

        logger.info("200 | Fund projects analytics generated successfully!")
        return {
            "totals": totals,
            "parish_with_most_fund_projects": parish_with_most_fund_projects,
            "parish_hierarchy": parish_hierarchy,
            "monthly_breakdown": monthly_breakdown,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | DB error during fund projects analytics generation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating fund projects analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during fund projects analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating fund projects analytics generation.",
        )


# members analytics
@router.get(
    "/members/analytics",
    summary="Member analytics with totals, averages, and parish filters",
)
async def get_members_analytics(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    is_archived: Optional[bool] = Query(None, description="Filter by archive status"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate members analytics...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        query = db.query(Member)

        # archive filter
        if is_archived is None:
            query = query.filter(Member.is_archived == False)
        else:
            query = query.filter(Member.is_archived == is_archived)

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                logger.warning("404 | Parish not found!")
                raise HTTPException(status_code=404, detail="Parish not found!")
            query = query.filter(Member.parish_id == parish_id)

        records = query.all()
        if not records:
            return {"message": "No member records found."}

        # totals & Averages
        total_members = len(records)

        totals = {"total_members": total_members}

        # parish with most members (only if no parish filter)
        parish_with_most_members = None
        if not parish_id:
            parish_totals = (
                db.query(
                    Member.parish_id,
                    func.count(Member.id).label("total"),
                )
                .filter(Member.is_archived == False)
                .group_by(Member.parish_id)
                .order_by(func.count(Member.id).desc())
                .first()
            )
            if parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == parish_totals.parish_id)
                    .scalar()
                )
                parish_with_most_members = {
                    "parish_id": parish_totals.parish_id,
                    "parish_name": parish_name,
                    "total_members": parish_totals.total,
                }

        # hierarchy of parishes with most to least members
        parish_hierarchy = None
        if not parish_id:
            parish_totals = (
                db.query(
                    Member.parish_id,
                    func.count(Member.id).label("total"),
                )
                .filter(Member.is_archived == False)
                .group_by(Member.parish_id)
                .order_by(func.count(Member.id).desc())
                .all()
            )

            parish_hierarchy = []
            for p in parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == p.parish_id)
                    .scalar()
                )
                parish_hierarchy.append(
                    {
                        "parish_id": p.parish_id,
                        "parish_name": parish_name,
                        "total_members": p.total,
                    }
                )

        # monthly breakdown
        monthly_data = db.query(
            func.date_trunc("month", Member.created_at).label("month"),
            func.count(Member.id).label("total_members"),
        ).filter(
            Member.is_archived == (is_archived if is_archived is not None else False)
        )

        if parish_id:
            monthly_data = monthly_data.filter(Member.parish_id == parish_id)

        monthly_data = monthly_data.group_by(
            func.date_trunc("month", Member.created_at)
        ).all()

        monthly_breakdown = [
            {
                "month": m.month.strftime("%Y-%m"),
                "total_members": m.total_members,
            }
            for m in monthly_data
        ]

        logger.info("200 | Member analytics generated successfully!")
        return {
            "totals": totals,
            "parish_with_most_members": parish_with_most_members,
            "parish_hierarchy": parish_hierarchy,
            "monthly_breakdown": monthly_breakdown,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | DB error during members analytics generation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating members analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during members analytics generation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating members analytics generation.",
        )


# sacraments analytics
@router.get(
    "/sacraments/analytics",
    summary="Sacrament analytics with totals, averages, and parish filters",
)
async def get_sacraments_analytics(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    is_archived: Optional[bool] = Query(None, description="Filter by archive status"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate sacraments analytics...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        query = db.query(Sacrament)

        # archive filter
        if is_archived is None:
            query = query.filter(Sacrament.is_archived == False)
        else:
            query = query.filter(Sacrament.is_archived == is_archived)

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                logger.warning("404 | Parish not found!")
                raise HTTPException(status_code=404, detail="Parish not found!")
            query = query.filter(Sacrament.parish_id == parish_id)

        records = query.all()
        if not records:
            return {"message": "No sacrament records found."}

        # totals & Averages
        total_sacraments = len(records)

        totals = {"total_sacraments": total_sacraments}

        # parish with most sacraments (only if no parish filter)
        parish_with_most_sacraments = None
        if not parish_id:
            parish_totals = (
                db.query(
                    Sacrament.parish_id,
                    func.count(Sacrament.id).label("total"),
                )
                .filter(Sacrament.is_archived == False)
                .group_by(Sacrament.parish_id)
                .order_by(func.count(Sacrament.id).desc())
                .first()
            )
            if parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == parish_totals.parish_id)
                    .scalar()
                )
                parish_with_most_sacraments = {
                    "parish_id": parish_totals.parish_id,
                    "parish_name": parish_name,
                    "total_sacraments": parish_totals.total,
                }

        # hierarchy of parishes with most to least sacraments
        parish_hierarchy = None
        if not parish_id:
            parish_totals = (
                db.query(
                    Sacrament.parish_id,
                    func.count(Sacrament.id).label("total"),
                )
                .filter(Sacrament.is_archived == False)
                .group_by(Sacrament.parish_id)
                .order_by(func.count(Sacrament.id).desc())
                .all()
            )

            parish_hierarchy = []
            for p in parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == p.parish_id)
                    .scalar()
                )
                parish_hierarchy.append(
                    {
                        "parish_id": p.parish_id,
                        "parish_name": parish_name,
                        "total_sacraments": p.total,
                    }
                )

        # monthly breakdown
        monthly_data = db.query(
            func.date_trunc("month", Sacrament.created_at).label("month"),
            func.count(Sacrament.id).label("total_sacraments"),
        ).filter(
            Sacrament.is_archived == (is_archived if is_archived is not None else False)
        )

        if parish_id:
            monthly_data = monthly_data.filter(Sacrament.parish_id == parish_id)

        monthly_data = monthly_data.group_by(
            func.date_trunc("month", Sacrament.created_at)
        ).all()

        monthly_breakdown = [
            {
                "month": m.month.strftime("%Y-%m"),
                "total_sacraments": m.total_sacraments,
            }
            for m in monthly_data
        ]

        logger.info("200 | Sacrament analytics generated successfully!")
        return {
            "totals": totals,
            "parish_with_most_sacraments": parish_with_most_sacraments,
            "parish_hierarchy": parish_hierarchy,
            "monthly_breakdown": monthly_breakdown,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | DB error during sacraments analytics generation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating sacraments analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacraments analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating sacraments analytics generation.",
        )


# sacrament records analytics
@router.get(
    "/sacrament-records/analytics",
    summary="Sacrament records analytics with totals, averages, and parish filters",
)
async def get_sacrament_records_analytics(
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    is_archived: Optional[bool] = Query(None, description="Filter by archive status"),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate sacrament records analytics...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        query = db.query(SacramentRecord)

        # archive filter
        if is_archived is None:
            query = query.filter(SacramentRecord.is_archived == False)
        else:
            query = query.filter(SacramentRecord.is_archived == is_archived)

        # parish filter
        if parish_id:
            parish = db.query(Parish).filter(Parish.id == parish_id).first()
            if not parish:
                logger.warning("404 | Parish not found!")
                raise HTTPException(status_code=404, detail="Parish not found!")
            query = query.filter(SacramentRecord.parish_id == parish_id)

        records = query.all()
        if not records:
            return {"message": "No sacrament_records  records found."}

        # totals & Averages
        total_sacrament_records = len(records)

        totals = {"total_sacrament_records": total_sacrament_records}

        # parish with most sacrament recordss (only if no parish filter)
        parish_with_most_sacrament_records = None
        if not parish_id:
            parish_totals = (
                db.query(
                    SacramentRecord.parish_id,
                    func.count(SacramentRecord.id).label("total"),
                )
                .filter(SacramentRecord.is_archived == False)
                .group_by(SacramentRecord.parish_id)
                .order_by(func.count(SacramentRecord.id).desc())
                .first()
            )
            if parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == parish_totals.parish_id)
                    .scalar()
                )
                parish_with_most_sacrament_records = {
                    "parish_id": parish_totals.parish_id,
                    "parish_name": parish_name,
                    "total_sacraments_records": parish_totals.total,
                }

        # hierarchy of parishes with most to least sacraments records
        parish_hierarchy = None
        if not parish_id:
            parish_totals = (
                db.query(
                    SacramentRecord.parish_id,
                    func.count(SacramentRecord.id).label("total"),
                )
                .filter(SacramentRecord.is_archived == False)
                .group_by(SacramentRecord.parish_id)
                .order_by(func.count(SacramentRecord.id).desc())
                .all()
            )

            parish_hierarchy = []
            for p in parish_totals:
                parish_name = (
                    db.query(cast(Parish.parish_data["parish_name"], String))
                    .filter(Parish.id == p.parish_id)
                    .scalar()
                )
                parish_hierarchy.append(
                    {
                        "parish_id": p.parish_id,
                        "parish_name": parish_name,
                        "total_sacrament_records": p.total,
                    }
                )

        # monthly breakdown
        monthly_data = db.query(
            func.date_trunc("month", SacramentRecord.created_at).label("month"),
            func.count(SacramentRecord.id).label("total_sacrament_records"),
        ).filter(
            SacramentRecord.is_archived
            == (is_archived if is_archived is not None else False)
        )

        if parish_id:
            monthly_data = monthly_data.filter(SacramentRecord.parish_id == parish_id)

        monthly_data = monthly_data.group_by(
            func.date_trunc("month", SacramentRecord.created_at)
        ).all()

        monthly_breakdown = [
            {
                "month": m.month.strftime("%Y-%m"),
                "total_sacrament_records": m.total_sacrament_records,
            }
            for m in monthly_data
        ]

        logger.info("200 | Sacrament record analytics generated successfully!")
        return {
            "totals": totals,
            "parish_with_most_sacraments": parish_with_most_sacrament_records,
            "parish_hierarchy": parish_hierarchy,
            "monthly_breakdown": monthly_breakdown,
        }

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | DB error during sacrament records analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating sacrament records analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during sacrament records analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating sacrament records analytics generation.",
        )


# invited users analytics
@router.get(
    "/invited-users/analytics",
    summary="System analytics (users, invited users, parishes)",
)
def get_invited_users_analytics(
    parish_id: Optional[str] = Query(None, description="Optional parish filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate invited user records analytics...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        parish_query = db.query(Parish.id, Parish.parish_data)

        if parish_id:
            parish_query = parish_query.filter(Parish.id == parish_id)

        parish_results = parish_query.all()
        analytics_data = []

        for parish in parish_results:
            parish_name = None
            try:
                if parish.parish_data and "parish_name" in parish.parish_data:
                    parish_name = parish.parish_data["parish_name"]
            except Exception:
                parish_name = None

            # Active users in this parish
            total_users = (
                db.query(func.count(User.id))
                .filter(User.parish_id == parish.id, User.is_active == True)
                .scalar()
            ) or 0

            # Invited users counts
            total_invited_users = (
                db.query(func.count(InvitedUser.id))
                .filter(InvitedUser.parish_id == parish.id)
                .scalar()
            ) or 0

            accepted_invites = (
                db.query(func.count(InvitedUser.id))
                .filter(
                    InvitedUser.parish_id == parish.id,
                    InvitedUser.is_used == True,
                )
                .scalar()
            ) or 0

            pending_invites = (
                db.query(func.count(InvitedUser.id))
                .filter(
                    InvitedUser.parish_id == parish.id,
                    InvitedUser.is_used == False,
                )
                .scalar()
            ) or 0

            rejected_invites = (
                db.query(func.count(InvitedUser.id))
                .filter(
                    InvitedUser.parish_id == parish.id,
                    InvitedUser.is_active == False,
                )
                .scalar()
            ) or 0

            analytics_data.append(
                {
                    "parish_id": str(parish.id),
                    "parish_name": parish_name,
                    "total_users": total_users,
                    "total_invited_users": total_invited_users,
                    "accepted_invites": accepted_invites,
                    "pending_invites": pending_invites,
                    "rejected_invites": rejected_invites,
                    "total_people": total_users + total_invited_users,
                }
            )

        # Global stats if no parish_id
        if not parish_id:
            global_users = (
                db.query(func.count(User.id)).filter(User.is_active == True).scalar()
                or 0
            )
            global_invited_users = (db.query(func.count(InvitedUser.id)).scalar()) or 0

            global_accepted = (
                db.query(func.count(InvitedUser.id))
                .filter(InvitedUser.is_used == True)
                .scalar()
            ) or 0

            global_pending = (
                db.query(func.count(InvitedUser.id))
                .filter(InvitedUser.is_used == False)
                .scalar()
            ) or 0

            global_rejected = (
                db.query(func.count(InvitedUser.id))
                .filter(InvitedUser.is_active == False)
                .scalar()
            ) or 0

            global_total = global_users + global_invited_users

            return {
                "global analytics": {
                    "total_users": global_users,
                    "total_invited_users": global_invited_users,
                    "accepted_invites": global_accepted,
                    "pending_invites": global_pending,
                    "rejected_invites": global_rejected,
                    "total_people": global_total,
                },
                "parishes": analytics_data,
            }

        return {"parishes": analytics_data}

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | DB error during invited users analytics generation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating invited users analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during invited users analytics generation!",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating invited users analytics generation.",
        )


# user analytics
@router.get("/users/analytics", summary="User analytics with totals and breakdowns")
def get_user_analytics(
    parish_id: Optional[str] = Query(None, description="Optional parish filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info("Attempting to generate user analytics...")

        # current user check
        user = get_user_details(db, current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found!")

        # Base query
        query = db.query(User)
        if parish_id is not None:
            query = query.filter(User.parish_id == parish_id)

        # Total counts
        total_users = query.with_entities(func.count(User.id)).scalar()
        active_users = (
            query.with_entities(func.count(User.id))
            .filter(User.is_active == True)
            .scalar()
        )
        inactive_users = (
            query.with_entities(func.count(User.id))
            .filter(User.is_active == False)
            .scalar()
        )
        archived_users = (
            query.with_entities(func.count(User.id))
            .filter(User.is_archived == True)
            .scalar()
        )

        # Users per parish (only if parish_id not passed)
        users_per_parish = []
        if parish_id is None:
            users_per_parish = (
                db.query(
                    cast(Parish.parish_data["parish_name"], String).label(
                        "parish_name"
                    ),
                    func.count(User.id).label("user_count"),
                )
                .join(Parish, Parish.id == User.parish_id)
                .group_by(cast(Parish.parish_data["parish_name"], String))
                .all()
            )

        # Users per role (filtered if parish_id is provided)
        users_per_role = (
            query.join(Role, Role.id == User.role_id)
            .with_entities(
                role.title.label("role_title"), func.count(User.id).label("user_count")
            )
            .group_by(role.title)
            .all()
        )

        response = {
            "summary": {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": inactive_users,
                "archived_users": archived_users,
            },
            "users_per_role": [
                {"role_name": row.role_title, "user_count": row.user_count}
                for row in users_per_role
            ],
        }

        # include per-parish breakdown only if no parish filter
        if parish_id is None:
            response["users_per_parish"] = [
                {"parish_name": row.parish_name, "user_count": row.user_count}
                for row in users_per_parish
            ]

        return response

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("500 | DB error during users analytics generation!", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="A database error occurred while generating users analytics generation!",
        )

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during users analytics generation!", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating users analytics generation.",
        )


# parish subscriptions dashboard analytics
