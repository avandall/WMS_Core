from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserModel(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user", index=True)
    full_name = Column(String(255))
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    audit_logs = relationship("AuditLogModel", back_populates="user")
