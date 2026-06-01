"""Domain-specific business exceptions.

This module contains all exceptions related to business logic, validation,
and domain entity operations.
"""

from __future__ import annotations

from typing import Any, Optional


# Base Domain Exception
class DomainError(Exception):
    """Base class for all domain errors."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# Validation Errors
class ValidationError(DomainError):
    """Raised when a domain validation fails."""


class InvalidIDError(ValidationError):
    """Raised when an identifier is invalid (e.g., non-positive integer)."""


class InvalidQuantityError(ValidationError):
    """Raised when a quantity value is invalid (e.g., negative)."""


# Entity Errors
class EntityNotFoundError(DomainError):
    """Raised when a referenced entity cannot be found."""


class EntityAlreadyExistsError(DomainError):
    """Raised when an entity already exists in the target collection."""


# Business Rule Violations
class BusinessRuleViolationError(DomainError):
    """Raised when a business rule is violated."""


class InvalidDocumentStatusError(BusinessRuleViolationError):
    """Raised when a document is in an invalid status for the operation."""


class InsufficientStockError(BusinessRuleViolationError):
    """Raised when there is not enough stock for the requested operation."""


# Specific Entity Errors
class ProductNotFoundError(EntityNotFoundError):
    """Raised when a product cannot be found in the expected context."""


class WarehouseNotFoundError(EntityNotFoundError):
    """Raised when a warehouse cannot be found."""


class DocumentNotFoundError(EntityNotFoundError):
    """Raised when a requested document does not exist."""


# Duplicate Entity Errors
class DuplicateWarehouseError(EntityAlreadyExistsError):
    """Raised when trying to create a warehouse with an existing ID."""


class DuplicateProductError(EntityAlreadyExistsError):
    """Raised when trying to create a product with an existing ID."""


class DuplicateDocumentError(EntityAlreadyExistsError):
    """Raised when trying to create a document with an existing ID."""


# Factory Functions
def create_validation_error(field: str, value: Any, constraint: str) -> ValidationError:
    """Factory function for creating validation errors."""
    return ValidationError(
        f"Validation failed for field '{field}' with value '{value}': {constraint}",
        details={"field": field, "value": value, "constraint": constraint},
    )


def create_business_rule_error(
    rule: str, context: Optional[dict] = None
) -> BusinessRuleViolationError:
    """Factory function for creating business rule violation errors."""
    return BusinessRuleViolationError(
        f"Business rule violated: {rule}", details=context or {}
    )


def create_entity_not_found_error(
    entity_type: str, entity_id: Any
) -> EntityNotFoundError:
    """Factory function for creating entity not found errors."""
    return EntityNotFoundError(
        f"{entity_type} with ID '{entity_id}' not found",
        details={"entity_type": entity_type, "entity_id": entity_id},
    )


__all__ = [
    # Base classes
    "DomainError",
    "ValidationError",
    "InvalidIDError", 
    "InvalidQuantityError",
    # Entity errors
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "ProductNotFoundError",
    "WarehouseNotFoundError",
    "DocumentNotFoundError",
    "DuplicateWarehouseError",
    "DuplicateProductError", 
    "DuplicateDocumentError",
    # Business rule violations
    "BusinessRuleViolationError",
    "InvalidDocumentStatusError",
    "InsufficientStockError",
    # Factory functions
    "create_validation_error",
    "create_business_rule_error",
    "create_entity_not_found_error",
]
