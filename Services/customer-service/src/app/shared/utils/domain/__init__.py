"""Domain utilities (compatibility).

These helpers were present in `src-old/app/utils/domain`.
Prefer placing new validation/business-rule logic directly on domain entities.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from app.shared.domain.business_exceptions import BusinessRuleViolationError, ValidationError


class ValidationUtils:
    @staticmethod
    def validate_required(value: Any, field_name: str) -> None:
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError(f"{field_name} is required")

    @staticmethod
    def validate_positive_int(value: Any, field_name: str) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValidationError(f"{field_name} must be a positive integer")

    @staticmethod
    def validate_non_negative_number(value: Any, field_name: str) -> None:
        if not isinstance(value, (int, float)) or value < 0:
            raise ValidationError(f"{field_name} must be a non-negative number")


class BusinessRulesUtils:
    @staticmethod
    def ensure(condition: bool, message: str, details: Optional[dict] = None) -> None:
        if not condition:
            raise BusinessRuleViolationError(message)


class DateUtils:
    @staticmethod
    def get_current_datetime() -> datetime:
        return datetime.now()

    @staticmethod
    def format_date_for_display(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def is_date_in_range(target_date: date, start_date: date, end_date: date) -> bool:
        return start_date <= target_date <= end_date


__all__ = ["ValidationUtils", "BusinessRulesUtils", "DateUtils"]
