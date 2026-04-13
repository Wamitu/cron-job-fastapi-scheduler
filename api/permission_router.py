from uuid import UUID
from typing import List
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from db.models import User, Permission, UserPermission
from db.session import get_db
from schemas.notification_schema import NotificationType
from schemas.permission_schema import UserPermissionDetails
from services.auth_service import get_current_user
from services.notification_service import create_notification
from services.user_service import get_user_details

router = APIRouter()


@router.get(
    "/{user_id}/view",
    response_model=List[UserPermissionDetails],
    summary="View user permissions",
)
async def view_user_permissions(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    user_permissions = (
        db.query(UserPermission).filter(UserPermission.user_id == user_id).all()
    )
    if not user_permissions:
        raise HTTPException(
            status_code=404, detail="No permissions found for this user!"
        )

    return user_permissions


@router.post("/add", summary="Add system permission")
async def add_permission(permission_name: str, db: Session = Depends(get_db)):
    permission = db.query(Permission).filter(Permission.name == permission_name).first()
    if permission:
        raise HTTPException(status_code=409, detail="Permission already exists!")

    permission = Permission(name=permission_name)
    db.add(permission)
    db.commit()
    db.refresh(permission)

    return {"message": "Permission added successfully!", "permission": permission}


@router.post("/assign", summary="Assign permission to a user")
async def assign_permission(
    user_id: UUID,
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logged_in_user = get_user_details(db, current_user)
    if not logged_in_user:
        raise HTTPException(status_code=404, detail="Current user not found!")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found!")

    existing_permission = (
        db.query(UserPermission)
        .filter_by(user_id=user.id, permission_id=permission.id)
        .first()
    )
    if existing_permission:
        raise HTTPException(
            status_code=409, detail="User already has current permission!"
        )

    user_permission = UserPermission(
        user_id=user.id, permission_id=permission.id, granted_by=current_user.id
    )
    db.add(user_permission)
    db.commit()
    db.refresh(user_permission)

    create_notification(
        db=db,
        user_id=logged_in_user.id,
        parish_id=logged_in_user.parish_id,
        notification_type=NotificationType.info,
        message=f"Permission '{permission.name}' assigned to user successfully!",
    )

    return user_permission


@router.post("/revoke", summary="Remove permission from a user")
async def revoke_permission(
    user_id: UUID, permission_id: UUID, db: Session = Depends(get_db)
):
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found!")

    user_permission = (
        db.query(UserPermission)
        .filter_by(user_id=user_id, permission_id=permission.id)
        .first()
    )
    if not user_permission:
        raise HTTPException(
            status_code=404, detail="User does not have this permission!"
        )

    db.delete(user_permission)
    db.commit()

    return {"message": "Permission revoked successfully!"}
