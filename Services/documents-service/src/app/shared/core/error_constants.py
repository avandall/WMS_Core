"""
Error constants for the WMS application.
Centralized error messages for consistent error handling across all layers.
"""

from typing import Any


class ErrorMessages:
    """Centralized error message constants."""

    INVALID_ID_POSITIVE_INTEGER = "ID must be a positive integer"
    INVALID_PRODUCT_ID = "Product ID must be a positive integer"
    INVALID_WAREHOUSE_ID = "Warehouse ID must be a positive integer"
    INVALID_DOCUMENT_ID = "Document ID must be a positive integer"
    INVALID_PRODUCT_NAME_EMPTY = "Product name cannot be empty"
    INVALID_PRODUCT_NAME_TOO_LONG = "Product name cannot exceed 100 characters"
    INVALID_WAREHOUSE_LOCATION_EMPTY = "Warehouse location cannot be empty"
    INVALID_WAREHOUSE_LOCATION_TOO_LONG = "Warehouse location cannot exceed 200 characters"
    INVALID_CREATED_BY_EMPTY = "Created by cannot be empty"
    INVALID_PRODUCT_PRICE_NEGATIVE = "Product price must be non-negative"
    INVALID_UNIT_PRICE_NEGATIVE = "Unit price must be non-negative"
    INVALID_QUANTITY_NEGATIVE = "Quantity cannot be negative"
    INVALID_QUANTITY_NON_NEGATIVE_INTEGER = "Quantity must be a non-negative integer"
    INVALID_QUANTITY_POSITIVE = "Quantity must be a positive integer"
    INVALID_QUANTITY_NEGATIVE_ADD = "Cannot add negative quantity"
    INVALID_QUANTITY_NEGATIVE_REMOVE = "Cannot remove negative quantity"
    INSUFFICIENT_STOCK = "Insufficient stock. Available: {available}, Requested: {requested}"
    INVALID_DOCUMENT_TYPE = "Invalid document type"
    IMPORT_MISSING_DESTINATION = "Import document must have a destination warehouse"
    EXPORT_MISSING_SOURCE = "Export document must have a source warehouse"
    TRANSFER_MISSING_WAREHOUSES = "Transfer document must have both source and destination warehouses"
    TRANSFER_SAME_WAREHOUSE = "Transfer document cannot have same source and destination warehouse"
    PRODUCT_ALREADY_EXISTS_IN_DOCUMENT = "Product {product_id} already exists in document"
    CANNOT_MODIFY_POSTED_DOCUMENT = "Cannot modify document {document_id} that is not in DRAFT status"
    CANNOT_POST_EMPTY_DOCUMENT = "Cannot post document without items"
    APPROVED_BY_EMPTY = "Approved by cannot be empty"
    CANNOT_CANCEL_POSTED_DOCUMENT = "Cannot cancel a posted document {document_id}"
    CANNOT_TRANSFER_SAME_WAREHOUSE = "Cannot transfer to the same warehouse"
    PRODUCT_NOT_FOUND = "Product {product_id} not found"
    WAREHOUSE_NOT_FOUND = "Warehouse {warehouse_id} not found"
    DOCUMENT_NOT_FOUND = "Document {document_id} not found"
    PRODUCT_NOT_FOUND_IN_WAREHOUSE = "Product {product_id} not found in warehouse {warehouse_id}"
    WAREHOUSE_ALREADY_EXISTS = "Warehouse {warehouse_id} already exists"
    PRODUCT_ALREADY_EXISTS = "Product {product_id} already exists"
    DOCUMENT_ALREADY_EXISTS = "Document {document_id} already exists"
    CANNOT_START_NEGATIVE_INVENTORY = "Cannot start with negative inventory for {product_id}"
    CANNOT_DELETE_NON_ZERO_QUANTITY = "Cannot delete item with non-zero quantity"
    INVALID_OPERATION = "Invalid operation in current context"


class ErrorCodes:
    """Error code constants for API responses and logging."""

    INVALID_ID = 1001
    INVALID_PRODUCT_ID = 1002
    INVALID_WAREHOUSE_ID = 1003
    INVALID_DOCUMENT_ID = 1004
    INVALID_NAME = 1005
    INVALID_PRICE = 1006
    INVALID_QUANTITY = 1007
    INVALID_DOCUMENT_TYPE = 1008
    BUSINESS_RULE_VIOLATION = 2001
    INSUFFICIENT_STOCK = 2002
    INVALID_DOCUMENT_STATUS = 2003
    DUPLICATE_ENTITY = 2004
    ENTITY_NOT_FOUND = 3001
    PRODUCT_NOT_FOUND = 3002
    WAREHOUSE_NOT_FOUND = 3003
    DOCUMENT_NOT_FOUND = 3004
    REPOSITORY_ERROR = 4001
    DATA_ACCESS_ERROR = 4002
    EXTERNAL_SERVICE_ERROR = 4003
    AUTHENTICATION_ERROR = 5001
    AUTHORIZATION_ERROR = 5002
    RATE_LIMIT_ERROR = 5003
    INPUT_VALIDATION_ERROR = 5004


class ErrorContext:
    """Standard keys for error context dictionaries."""

    FIELD = "field"
    VALUE = "value"
    CONSTRAINT = "constraint"
    ENTITY_TYPE = "entity_type"
    ENTITY_ID = "entity_id"
    AVAILABLE_QUANTITY = "available"
    REQUESTED_QUANTITY = "requested"
    PRODUCT_ID = "product_id"
    WAREHOUSE_ID = "warehouse_id"
    DOCUMENT_ID = "document_id"


class ErrorSeverity:
    """Error severity levels for logging and monitoring."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory:
    """Error categories for classification and handling."""

    VALIDATION = "validation"
    BUSINESS_RULE = "business_rule"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    CONFIGURATION = "configuration"


def format_insufficient_stock_message(available: int, requested: int) -> str:
    """Format insufficient stock error message."""
    return ErrorMessages.INSUFFICIENT_STOCK.format(
        available=available, requested=requested
    )


def format_entity_not_found_message(entity_type: str, entity_id: Any) -> str:
    """Format entity not found error message."""
    return f"{entity_type} with ID '{entity_id}' not found"


def format_duplicate_entity_message(entity_type: str, entity_id: Any) -> str:
    """Format duplicate entity error message."""
    return f"{entity_type} with ID '{entity_id}' already exists"


__all__ = [
    "ErrorMessages",
    "ErrorCodes",
    "ErrorContext",
    "ErrorSeverity",
    "ErrorCategory",
    "format_insufficient_stock_message",
    "format_entity_not_found_message",
    "format_duplicate_entity_message",
]
