from abc import ABC, abstractmethod
from typing import List


class ICustomerRepo(ABC):
    """Interface for customer repository operations"""
    
    @abstractmethod
    def create(self, data: dict):
        pass

    @abstractmethod
    def get(self, customer_id: int):
        pass

    @abstractmethod
    def get_all(self) -> List[dict]:
        pass

    @abstractmethod
    def update_debt(self, customer_id: int, delta: float) -> None:
        pass

    @abstractmethod
    def record_purchase(self, customer_id: int, document_id: int, total_value: float) -> None:
        pass

    @abstractmethod
    def list_purchases(self, customer_id: int) -> List[dict]:
        pass

    @abstractmethod
    def update(self, customer_id: int, data: dict) -> None:
        pass


# Alias for backward compatibility
CustomerRepo = ICustomerRepo
