from sqlalchemy import Column, String, DateTime, UUID, ForeignKey, Text, func
import uuid
from db.base_class import Base
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.orm import relationship


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    diocese_id = Column(UUID(as_uuid=True), ForeignKey("dioceses.id"), nullable=True)
    parish_id = Column(UUID(as_uuid=True), ForeignKey("parishes.id"), nullable=True)
    method = Column(String)  # get/post/put/delete/patch
    path = Column(String)  # api url
    status_code = Column(String)  # 200,300,400
    request_body = Column(Text, nullable=True)  # data requested
    response_body = Column(Text, nullable=True)  # data response
    ip_address = Column(String)  # user ip address
    before_data = Column(Text, nullable=True)  # data before update
    after_data = Column(Text, nullable=True)  # data after update
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    diocese = relationship("Diocese")
    parish = relationship("Parish")
