from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from app.shared.domain.business_exceptions import InvalidIDError, InvalidQuantityError, ValidationError
from app.shared.domain.entity import DomainEntity


@dataclass
class ProductUOM:
    uom_code: str
    conversion_factor: float = 1.0
    to_uom_code: str = "EACH"


class Product(DomainEntity):
    """Domain entity for a product with physical dimensions and multi-UOM support."""

    def __init__(
        self,
        product_id: int,
        name: str,
        description: Optional[str] = None,
        price: float = 0.0,
        length_cm: float = 0.0,
        width_cm: float = 0.0,
        height_cm: float = 0.0,
        gross_weight_kg: float = 0.0,
        net_weight_kg: float = 0.0,
        base_uom: str = "EACH",
        uoms: Optional[List[ProductUOM]] = None,
    ) -> None:
        self._validate_product_id(product_id)
        self._validate_name(name)
        self._validate_price(price)
        self._validate_non_negative("length_cm", length_cm)
        self._validate_non_negative("width_cm", width_cm)
        self._validate_non_negative("height_cm", height_cm)
        self._validate_non_negative("gross_weight_kg", gross_weight_kg)
        self._validate_non_negative("net_weight_kg", net_weight_kg)

        self.product_id = product_id
        self.name = name
        self.description = description
        self.price = float(price)
        self.length_cm = float(length_cm)
        self.width_cm = float(width_cm)
        self.height_cm = float(height_cm)
        self.gross_weight_kg = float(gross_weight_kg)
        self.net_weight_kg = float(net_weight_kg)
        self.base_uom = base_uom or "EACH"
        self.uoms: List[ProductUOM] = uoms or []

    @staticmethod
    def _validate_product_id(product_id: int) -> None:
        if not isinstance(product_id, int) or product_id <= 0:
            raise InvalidIDError("product_id must be a positive integer")

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("name must be a non-empty string")
        if len(name) > 100:
            raise ValidationError("name must be at most 100 characters")

    @staticmethod
    def _validate_price(price: float) -> None:
        if not isinstance(price, (int, float, Decimal)) or price < 0:
            raise InvalidQuantityError("price must be a non-negative number")

    @staticmethod
    def _validate_non_negative(field_name: str, val: float) -> None:
        if not isinstance(val, (int, float, Decimal)) or val < 0:
            raise ValidationError(f"{field_name} must be a non-negative number")

    @property
    def volume_cbm(self) -> float:
        """Volume in cubic meters calculated as (D * R * C) / 1,000,000."""
        if self.length_cm > 0 and self.width_cm > 0 and self.height_cm > 0:
            return round((self.length_cm * self.width_cm * self.height_cm) / 1_000_000.0, 6)
        return 0.0

    def convert_uom_quantity(
        self, quantity: float, from_uom: str, to_uom: Optional[str] = None
    ) -> float:
        """
        Convert quantity from one UOM to target UOM (defaults to base_uom).
        Supports multi-level ratio conversion (e.g. 1 CARTON = 24 EACH, 1 PALLET = 40 CARTONS).
        """
        target_uom = to_uom or self.base_uom
        if from_uom == target_uom:
            return float(quantity)

        factors = {self.base_uom: 1.0}
        changed = True
        while changed:
            changed = False
            for uom in self.uoms:
                if uom.to_uom_code in factors and uom.uom_code not in factors:
                    factors[uom.uom_code] = factors[uom.to_uom_code] * uom.conversion_factor
                    changed = True

        if from_uom not in factors:
            raise ValidationError(f"Unknown UOM '{from_uom}' for product {self.product_id}")
        if target_uom not in factors:
            raise ValidationError(f"Unknown target UOM '{target_uom}' for product {self.product_id}")

        qty_in_base = quantity * factors[from_uom]
        return qty_in_base / factors[target_uom]

    def update_dimensions(self, length_cm: float, width_cm: float, height_cm: float) -> None:
        self._validate_non_negative("length_cm", length_cm)
        self._validate_non_negative("width_cm", width_cm)
        self._validate_non_negative("height_cm", height_cm)
        self.length_cm = float(length_cm)
        self.width_cm = float(width_cm)
        self.height_cm = float(height_cm)

    def update_weights(self, gross_weight_kg: float, net_weight_kg: float) -> None:
        self._validate_non_negative("gross_weight_kg", gross_weight_kg)
        self._validate_non_negative("net_weight_kg", net_weight_kg)
        self.gross_weight_kg = float(gross_weight_kg)
        self.net_weight_kg = float(net_weight_kg)

    def update_price(self, new_price: float) -> None:
        self._validate_price(new_price)
        self.price = float(new_price)

    def update_name(self, new_name: str) -> None:
        self._validate_name(new_name)
        self.name = new_name

    def update_description(self, new_description: Optional[str]) -> None:
        self.description = new_description

    def calculate_total_value(self, quantity: int) -> float:
        if not isinstance(quantity, int) or quantity < 0:
            raise InvalidQuantityError("quantity must be a non-negative integer")
        return self.price * quantity

    @property
    def identity(self) -> int:
        return self.product_id

    def __str__(self) -> str:
        return f"Product(id={self.product_id}, name='{self.name}', price={self.price}, volume_cbm={self.volume_cbm})"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Product):
            return False
        return self.product_id == other.product_id

    def __hash__(self) -> int:
        return hash(self.product_id)
