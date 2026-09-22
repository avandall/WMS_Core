from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.shared.core.database import Base


class UserModel(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user", index=True)
    full_name = Column(String(255))
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
