import uuid
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    func,
    Enum as SAEnum,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base_class import Base
from schemas.member_schema import MemberGroup
from sqlalchemy.ext.mutable import MutableDict


class Member(Base):
    __tablename__ = "members"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    parish_id = Column(
        UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=False, index=True
    )
    member_no = Column(String, nullable=False)
    member_data = Column(MutableDict.as_mutable(JSON), nullable=False)
    member_group = Column(
        SAEnum(MemberGroup), nullable=False, default=MemberGroup.men_in_action
    )
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
