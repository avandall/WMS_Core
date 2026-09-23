from app.shared.domain.business_exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    InvalidDocumentStatusError,
)


class DocumentNotFoundError(EntityNotFoundError):
    """Raised when a requested document does not exist."""


class DuplicateDocumentError(EntityAlreadyExistsError):
    """Raised when trying to create a document with an existing ID."""

