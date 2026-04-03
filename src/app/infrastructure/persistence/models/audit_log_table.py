from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Index, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    path = Column(String(500), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    client_ip = Column(String(100))
    user_agent = Column(String(300))
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    user = relationship("UserModel", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_user_path", "user_id", "path"),
        Index("ix_audit_logs_created", "created_at"),
    )
