from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from db.models.audit_log import AuditLog
from db.models.user import User
from db.session import get_db
from services.auth_service import get_current_user
from services.user_service import get_user_details
from schemas.audit_log_schema import PaginatedAuditLogResponse, AuditLogDetails

router = APIRouter()


# retrieve all audit logs
@router.get("/all", response_model=PaginatedAuditLogResponse)
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    method: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = None,
    user_id: Optional[UUID] = None,
    parish_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    query = db.query(AuditLog).options(
        joinedload(AuditLog.user),
        joinedload(AuditLog.parish),
        joinedload(AuditLog.diocese),
    ).order_by(AuditLog.created_at.desc())

    # If user is Priest → filter only parish logs
    if user.role.title == "Priest":
        if not user.parish_id:
            raise HTTPException(
                status_code=403, detail="Priest not assigned to a parish."
            )
        parish_user_ids = (
            db.query(User.id).filter(User.parish_id == user.parish_id).subquery()
        )
        query = query.filter(AuditLog.user_id.in_(parish_user_ids))

    # If user is SysAdmin → no parish filter (see everything)
    elif user.role.title == "SysAdmin":
        pass

    else:
        raise HTTPException(status_code=403, detail="You are not allowed to view logs.")

    # 🔎 apply filters dynamically
    if method:
        query = query.filter(AuditLog.method == method)
    if path:
        query = query.filter(AuditLog.path.ilike(f"%{path}%"))
    if status_code is not None:
        query = query.filter(AuditLog.status_code == status_code)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if parish_id:
        query = query.filter(AuditLog.parish_id == parish_id)
    if ip_address:
        query = query.filter(AuditLog.ip_address == ip_address)

    total = query.count()

    offset = (page - 1) * page_size
    logs = query.offset(offset).limit(page_size).all()

    return {
        "items": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }
