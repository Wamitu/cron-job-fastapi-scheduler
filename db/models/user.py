import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base_class import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    diocese_id = Column(UUID(as_uuid=True), ForeignKey("dioceses.id"), nullable=True)
    parish_id = Column(UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    role = relationship("Role", back_populates="users")
    parish = relationship("Parish", back_populates="users")
    diocese = relationship("Diocese", back_populates="users")
    # user_permissions = relationship("UserPermission", back_populates="user")
    # permissions = relationship(
    #     "Permission",
    #     secondary="user_permissions",
    #     back_populates="users",
    #     viewonly=True,
    # )

    def __str__(self):
        return f"User(id={self.id}, parish_id={self.parish_id}, email={self.email})"
