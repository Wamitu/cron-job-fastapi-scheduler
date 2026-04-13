import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from db.base_class import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, unique=True, index=True)

    # user_permissions = relationship("UserPermission", back_populates="permission")


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id"))
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # user = relationship("User", back_populates="user_permissions")
    # permission = relationship("Permission", back_populates="user_permissions")
