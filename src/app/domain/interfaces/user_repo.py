from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from app.domain.entities.user import User


class IUserRepo(ABC):
    @abstractmethod
    def save(self, user: "User") -> "User":
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional["User"]:
        pass

    @abstractmethod
    def get(self, user_id: int) -> Optional["User"]:
        pass

    @abstractmethod
    def get_all(self) -> Dict[int, "User"]:
        pass

    @abstractmethod
    def delete(self, user_id: int) -> None:
        pass
