from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from app.modules.products.domain.entities.product import Product


class IProductRepo(ABC):
    @abstractmethod
    def save(self, product: "Product") -> None:
        pass

    @abstractmethod
    def get(self, product_id: int) -> Optional["Product"]:
        pass

    @abstractmethod
    def get_all(self) -> Dict[int, "Product"]:
        pass

    @abstractmethod
    def get_price(self, product_id: int) -> float:
        pass

    @abstractmethod
    def delete(self, product_id: int) -> None:
        pass
