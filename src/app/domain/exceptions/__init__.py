"""Domain exceptions module.

This module contains all exceptions related to business logic, validation,
and domain entity operations.
"""

from .business_exceptions import (
    DomainError,
    ValidationError,
    InvalidIDError,
    InvalidQuantityError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    InvalidDocumentStatusError,
    InsufficientStockError,
    ProductNotFoundError,
    WarehouseNotFoundError,
    DocumentNotFoundError,
    DuplicateWarehouseError,
    DuplicateProductError,
    DuplicateDocumentError,
    create_validation_error,
    create_business_rule_error,
    create_entity_not_found_error,
)

__all__ = [
    "DomainError",
    "ValidationError",
    "InvalidIDError",
    "InvalidQuantityError", 
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "BusinessRuleViolationError",
    "InvalidDocumentStatusError",
    "InsufficientStockError",
    "ProductNotFoundError",
    "WarehouseNotFoundError",
    "DocumentNotFoundError",
    "DuplicateWarehouseError",
    "DuplicateProductError",
    "DuplicateDocumentError",
    "create_validation_error",
    "create_business_rule_error",
    "create_entity_not_found_error",
]
