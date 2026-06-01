from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def _reset_app_imports(service_src: Path) -> None:
    sys.path.insert(0, str(service_src))
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]


def test_product_service_uses_direct_application_service_and_dtos() -> None:
    service = (
        ROOT_DIR
        / "Services/product-service/src/app/modules/products/application/services/product_service.py"
    ).read_text()
    application_root = ROOT_DIR / "Services/product-service/src/app/modules/products/application"

    assert "ProductCommandHandler" not in service
    assert "ProductQueryHandler" not in service
    assert "ProductValidator" not in service
    for folder in ["commands", "queries", "validation"]:
        assert list((application_root / folder).glob("*.py")) == []
    assert (application_root / "dtos/commands.py").exists()


def test_empty_domain_folders_were_removed_from_lightweight_crud_services() -> None:
    removed_paths = [
        "Services/customer-service/src/app/modules/customers/domain/entities",
        "Services/customer-service/src/app/modules/customers/domain/exceptions",
        "Services/identity-service/src/app/modules/users/domain/exceptions",
        "Services/product-service/src/app/modules/products/domain/exceptions",
    ]

    for relative_path in removed_paths:
        path = ROOT_DIR / relative_path
        assert [
            child for child in path.glob("*.py") if child.name != "__init__.py"
        ] == []
        assert not (path / "__init__.py").exists()


def test_product_service_crud_still_enforces_domain_rules() -> None:
    _reset_app_imports(ROOT_DIR / "Services/product-service/src")

    from app.modules.products.application.services.product_service import ProductService
    from app.modules.products.domain.entities.product import Product
    from app.shared.domain.business_exceptions import EntityAlreadyExistsError, EntityNotFoundError

    class ProductRepo:
        def __init__(self) -> None:
            self.products: dict[int, Product] = {}

        def save(self, product: Product) -> None:
            self.products[product.product_id] = product

        def get(self, product_id: int) -> Product | None:
            return self.products.get(product_id)

        def get_all(self) -> dict[int, Product]:
            return dict(self.products)

        def get_price(self, product_id: int) -> float:
            return self.products[product_id].price

        def delete(self, product_id: int) -> None:
            del self.products[product_id]

    service = ProductService(ProductRepo())

    created = service.create_product(product_id=1, name="SKU-1", price=10)
    updated = service.update_product(product_id=1, price=12)
    service.delete_product(1)

    assert created.product_id == 1
    assert updated.price == 12
    try:
        service.get_product_details(1)
    except EntityNotFoundError:
        pass
    else:
        raise AssertionError("deleted product was returned")

    service.create_product(product_id=1, name="SKU-1", price=10)
    try:
        service.create_product(product_id=1, name="SKU-1", price=10)
    except EntityAlreadyExistsError:
        pass
    else:
        raise AssertionError("duplicate product was accepted")


def test_identity_service_keeps_auth_policy_in_application_boundary() -> None:
    service = (
        ROOT_DIR / "Services/identity-service/src/app/modules/users/application/services/user_service.py"
    ).read_text()
    domain = (ROOT_DIR / "Services/identity-service/src/app/modules/users/domain/entities/user.py").read_text()

    assert "create_token" in service
    assert "hash_password" in service
    assert "verify_password" in service
    assert "create_token" not in domain
    assert "hash_password" not in domain
