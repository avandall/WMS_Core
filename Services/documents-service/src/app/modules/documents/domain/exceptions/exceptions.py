from app.shared.domain.business_exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
)


class DocumentNotFoundError(EntityNotFoundError):
    """Raised when a requested document does not exist."""


class DuplicateDocumentError(EntityAlreadyExistsError):
    """Raised when trying to create a document with an existing ID."""


class InvalidDocumentStatusError(BusinessRuleViolationError):
    """Raised when a document is in an invalid status for the operation."""
