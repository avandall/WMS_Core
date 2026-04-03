from __future__ import annotations

from typing import Optional

from app.domain.exceptions import ValidationError
from app.domain.interfaces.entity import DomainEntity


class User(DomainEntity):
    """Domain entity for application users."""

    def __init__(
        self,
        user_id: int,
        email: str,
        hashed_password: str,
        role: str = "user",
        full_name: Optional[str] = None,
        is_active: bool = True,
    ) -> None:
        self._validate_email(email)
        self._validate_role(role)

        self.user_id = user_id
        self.email = email.lower()
        self.hashed_password = hashed_password
        self.role = role
        self.full_name = full_name
        self.is_active = is_active

    @staticmethod
    def _validate_email(email: str) -> None:
        if not isinstance(email, str) or "@" not in email:
            raise ValidationError("email must be a valid email address")

    @staticmethod
    def _validate_role(role: str) -> None:
        allowed = {"admin", "user", "sales", "warehouse", "accountant"}
        if role not in allowed:
            raise ValidationError(
                f"role must be one of: {', '.join(sorted(allowed))}"
            )

    @property
    def identity(self) -> int:
        return self.user_id

    def __str__(self) -> str:
        return f"User(id={self.user_id}, email='{self.email}', role='{self.role}')"

    def __repr__(self) -> str:
        return self.__str__()
