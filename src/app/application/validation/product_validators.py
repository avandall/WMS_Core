"""Product validation logic separated from business logic."""

from typing import Dict, List

from app.shared.domain.business_exceptions import ValidationError


class ProductValidator:
    """Validator for product-related operations following SRP."""

    @staticmethod
    def validate_csv_rows(rows: List[Dict]) -> None:
        """Validate CSV import rows."""
        required = {"product_id", "name", "price"}
        for row in rows:
            if not required.issubset(row.keys()):
                raise ValidationError("CSV must include product_id,name,price")

    @staticmethod
    def validate_import_data(product_id: int, name: str, price: float) -> None:
        """Validate product import data."""
        if not isinstance(product_id, int) or product_id <= 0:
            raise ValidationError("product_id must be a positive integer")
        
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("name must be a non-empty string")
        
        if not isinstance(price, (int, float)) or price < 0:
            raise ValidationError("price must be a non-negative number")
