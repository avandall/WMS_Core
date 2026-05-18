from app.shared.domain.business_exceptions import EntityNotFoundError, EntityAlreadyExistsError


class ProductNotFoundError(EntityNotFoundError):
    """Raised when a product cannot be found in the expected context."""


class DuplicateProductError(EntityAlreadyExistsError):
    """Raised when trying to create a product with an existing ID."""
