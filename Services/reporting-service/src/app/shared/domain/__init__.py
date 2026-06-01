"""Shared domain layer with base classes and common exceptions."""

from .business_exceptions import (
    DomainError,
    ValidationError,
    InvalidIDError,
    InvalidQuantityError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    InsufficientStockError,
    create_validation_error,
    create_business_rule_error,
    create_entity_not_found_error,
)
from .entity import DomainEntity

__all__ = [
    # Base classes
    "DomainError",
    "ValidationError",
    "InvalidIDError",
    "InvalidQuantityError",
    # Entity errors
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    # Business rule violations
    "BusinessRuleViolationError",
    "InsufficientStockError",
    # Factory functions
    "create_validation_error",
    "create_business_rule_error",
    "create_entity_not_found_error",
    # Base entity
    "DomainEntity",
]
