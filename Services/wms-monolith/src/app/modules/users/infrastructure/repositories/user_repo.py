from typing import Optional, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.domain.entities.user import User
from app.shared.core.transaction import TransactionalRepository
from app.modules.users.domain.interfaces.user_repo import IUserRepo
from app.modules.users.infrastructure.models.user import UserModel


class UserRepo(TransactionalRepository, IUserRepo):
    def __init__(self, session: Session):
        super().__init__(session)

    def save(self, user: User) -> User:
        model = self.session.get(UserModel, user.user_id) if user.user_id else None
        if model:
            model.email = user.email
            model.hashed_password = user.hashed_password
            model.role = user.role
            model.full_name = user.full_name
            model.is_active = 1 if user.is_active else 0
        else:
            model = UserModel(
                email=user.email,
                hashed_password=user.hashed_password,
                role=user.role,
                full_name=user.full_name,
                is_active=1 if user.is_active else 0,
            )
            self.session.add(model)
            self.session.flush()
            user.user_id = model.user_id
        self._commit_if_auto()
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        row = self.session.execute(
            select(UserModel).where(UserModel.email == email.lower())
        ).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def get(self, user_id: int) -> Optional[User]:
        row = self.session.get(UserModel, user_id)
        return self._to_domain(row) if row else None

    def get_all(self) -> Dict[int, User]:
        # Ensure any pending transactions are flushed
        self.session.flush()
        rows = self.session.execute(select(UserModel)).scalars().all()
        # Force load all attributes to prevent lazy load issues
        for row in rows:
            _ = row.email, row.role, row.full_name
        return {row.user_id: self._to_domain(row) for row in rows}

    def delete(self, user_id: int) -> None:
        """Delete a user by ID."""
        user = self.session.get(UserModel, user_id)
        if user:
            self.session.delete(user)
            self._commit_if_auto()

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            user_id=model.user_id,
            email=model.email,
            hashed_password=model.hashed_password,
            role=model.role,
            full_name=model.full_name,
            is_active=bool(model.is_active),
        )
