from app.shared.domain.business_exceptions import EntityNotFoundError, EntityAlreadyExistsError


class WarehouseNotFoundError(EntityNotFoundError):
    """Raised when a warehouse cannot be found."""


class DuplicateWarehouseError(EntityAlreadyExistsError):
    """Raised when trying to create a warehouse with an existing ID."""
