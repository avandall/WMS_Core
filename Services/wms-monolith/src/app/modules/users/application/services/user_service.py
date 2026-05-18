from __future__ import annotations

from typing import Dict

from app.shared.core.auth import create_token, hash_password, verify_password
from app.shared.core.settings import settings
from app.modules.users.domain.entities.user import User
from app.shared.domain.business_exceptions import EntityNotFoundError, ValidationError
from app.modules.users.domain.interfaces.user_repo import IUserRepo


class UserService:
    def __init__(self, user_repo: IUserRepo):
        self.user_repo = user_repo

    def create_user(
        self,
        email: str,
        password: str,
        role: str = "user",
        full_name: str | None = None,
    ) -> User:
        if self.user_repo.get_by_email(email):
            raise ValidationError("User already exists")
        hashed = hash_password(password)
        user = User(
            user_id=0,
            email=email,
            hashed_password=hashed,
            role=role,
            full_name=full_name,
        )
        return self.user_repo.save(user)

    def authenticate(self, email: str, password: str) -> dict:
        user = self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise ValidationError("Invalid credentials")
        if not user.is_active:
            raise ValidationError("User is inactive")
        access = create_token(
            str(user.user_id),
            settings.access_token_expire_minutes,
            {"role": user.role},
        )
        refresh = create_token(
            str(user.user_id),
            settings.refresh_token_expire_minutes,
            {"role": user.role, "type": "refresh"},
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "user": user,
        }

    def get_user(self, user_id: int) -> User:
        user = self.user_repo.get(user_id)
        if not user:
            raise EntityNotFoundError("User not found")
        return user

    def list_users(self) -> Dict[int, User]:
        return self.user_repo.get_all()

    def update_role(self, user_id: int, role: str) -> User:
        user = self.get_user(user_id)
        updated = User(
            user_id=user.user_id,
            email=user.email,
            hashed_password=user.hashed_password,
            role=role,
            full_name=user.full_name,
            is_active=user.is_active,
        )
        return self.user_repo.save(updated)

    def change_password(self, user_id: int, old_password: str, new_password: str) -> User:
        user = self.get_user(user_id)
        if not verify_password(old_password, user.hashed_password):
            raise ValidationError("Current password is incorrect")
        if len(new_password) < 6:
            raise ValidationError("New password must be at least 6 characters")
        hashed = hash_password(new_password)
        updated = User(
            user_id=user.user_id,
            email=user.email,
            hashed_password=hashed,
            role=user.role,
            full_name=user.full_name,
            is_active=user.is_active,
        )
        return self.user_repo.save(updated)

    def delete_user(self, user_id: int) -> None:
        self.get_user(user_id)
        self.user_repo.delete(user_id)
