from sqlalchemy import (
    Column,
    String,
    Numeric,
    ForeignKey,
    Boolean,
    DateTime,
    func,
    JSON,
)
from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base_class import Base
import uuid


class Sacrament(Base):
    __tablename__ = "sacraments"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    parish_id = Column(
        UUID(as_uuid=True),
        ForeignKey("parishes.id"),
        nullable=True,
        index=True,
    )
    name = Column(String, nullable=False)
    rules = Column(JSON, default=list, nullable=True)
    fee_amount = Column(Numeric(10, 2), default=0)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    parish = relationship("Parish")


class SacramentRecord(Base):
    __tablename__ = "sacrament_records"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid4)
    reference_no = Column(String, nullable=False, unique=True)
    parish_id = Column(
        UUID(as_uuid=True),
        ForeignKey("parishes.id"),
        nullable=False,
        index=False,
    )
    sacrament_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sacraments.id"),
        nullable=False,
        index=True,
    )
    data = Column(JSON, nullable=False)
    generate_certificate = Column(Boolean, nullable=False, default=False)
    fee_amount = Column(Numeric(10, 2), nullable=True)
    outstanding_balance = Column(Numeric(10, 2), nullable=True)
    is_settled = Column(Boolean, nullable=False, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    parish = relationship("Parish")
    sacrament = relationship("Sacrament")
    created_by_user = relationship("User")
