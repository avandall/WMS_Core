"""Dependency injection for Identity Service endpoints."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.users.application.services.user_service import UserService
from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.shared.core.database import get_session


def get_user_repo(db: Session = Depends(get_session)) -> UserRepo:
    return UserRepo(db)


def get_user_service(db: Session = Depends(get_session)) -> UserService:
    return UserService(user_repo=UserRepo(db))

