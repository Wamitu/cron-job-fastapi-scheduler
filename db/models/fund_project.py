import uuid
from sqlalchemy import (
    Boolean,
    Column,
    String,
    Text,
    Numeric,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.base_class import Base
from schemas.fund_project_schema import FundProjectStatus


class FundProject(Base):
    __tablename__ = "fund_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    parish_id = Column(
        UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=False, index=True
    )
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    account_suffix = Column(String, nullable=False)
    status = Column(
        SAEnum(FundProjectStatus), nullable=False, default=FundProjectStatus.active
    )
    target_amount = Column(Numeric(10, 2), nullable=False)
    current_amount = Column(Numeric(10, 2), nullable=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    parish = relationship("Parish")
