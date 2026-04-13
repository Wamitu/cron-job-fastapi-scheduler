import uuid
from db.base_class import Base
from schemas.collection_schema import CollectionMethod, CollectionType
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    Numeric,
    func,
    Enum as SAEnum,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class Collection(Base):
    __tablename__ = "collections"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    collection_type = Column(
        SAEnum(CollectionType),
        nullable=False,
        index=True,
        default=CollectionType.offering,
    )
    member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("members.id"),
        nullable=True,
        index=True,
    )
    parish_id = Column(
        UUID(as_uuid=True),
        ForeignKey("parishes.id"),
        nullable=False,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fund_projects.id"),
        nullable=True,
        index=True,
    )
    sacrament_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sacrament_records.id"),
        nullable=True,
        index=True,
    )
    collection_method = Column(
        SAEnum(CollectionMethod),
        index=True,
        nullable=False,
        default=CollectionMethod.cash,
    )
    collection_data = Column(MutableDict.as_mutable(JSON), nullable=False)
    contributor_data = Column(MutableDict.as_mutable(JSON), nullable=True)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    member = relationship("Member")
    parish = relationship("Parish")
    project = relationship("FundProject")
    record = relationship("SacramentRecord")
    recorded_by_user = relationship("User")
