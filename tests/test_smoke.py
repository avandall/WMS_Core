def test_smoke_imports():
    import app.application.dtos  # noqa: F401
    import app.application.services  # noqa: F401
    import app.infrastructure.ai  # noqa: F401
    import app.infrastructure.persistence.models  # noqa: F401
    import app.api  # noqa: F401


def test_domain_layer_imports():
    """Test that all domain components can be imported."""
    import app.domain.entities  # noqa: F401
    import app.domain.exceptions  # noqa: F401
    import app.domain.interfaces  # noqa: F401


def test_core_layer_imports():
    """Test that core components can be imported."""
    import app.core  # noqa: F401
    import app.core.exceptions  # noqa: F401


def test_utils_imports():
    """Test that utility components can be imported."""
    import app.utils  # noqa: F401
    import app.utils.domain  # noqa: F401
    import app.utils.application  # noqa: F401
    import app.utils.infrastructure  # noqa: F401


def test_dto_imports():
    """Test that all DTOs can be imported."""
    from app.application.dtos import (
        CustomerCreate,
        DocumentCreate,
        InventoryItemCreate,
        ProductCreate,
        UserCreate,
        WarehouseCreate,
    )
    assert CustomerCreate is not None
    assert DocumentCreate is not None
    assert InventoryItemCreate is not None
    assert ProductCreate is not None
    assert UserCreate is not None
    assert WarehouseCreate is not None


def test_exception_imports():
    """Test that all exceptions can be imported."""
    from app.domain.exceptions import (
        ValidationError,
        EntityNotFoundError,
        BusinessRuleViolationError,
    )
    from app.core.exceptions import (
        ApplicationError,
        RepositoryError,
    )
    assert ValidationError is not None
    assert EntityNotFoundError is not None
    assert BusinessRuleViolationError is not None
    assert ApplicationError is not None
    assert RepositoryError is not None
