"""
Unit tests for TASK-065 / CRIT-04:
Triệt tiêu Fallback Regex Trích xuất Chữ số SKU trong Inventory Service.
Ensures invalid SKUs are strictly rejected with ValueError and never mistakenly mapped to wrong products.
"""
import inspect
import pytest
from sqlalchemy import create_engine, Column, BigInteger, String, Float, Integer
from sqlalchemy.orm import declarative_base, sessionmaker

from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.infrastructure.models.draft_proposal import DraftProposalModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel


CatalogBase = declarative_base()


class MockProductModel(CatalogBase):
    __tablename__ = "products"
    product_id = Column(BigInteger, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, default=0.0)


@pytest.fixture
def catalog_db_session():
    """In-memory SQLite session with catalog products and draft proposals."""
    engine = create_engine("sqlite:///:memory:")
    CatalogBase.metadata.create_all(bind=engine)
    DraftProposalModel.metadata.create_all(bind=engine)
    WarehouseInventoryModel.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed catalog products
    p1 = MockProductModel(product_id=42, name="LAP-PRO-15", price=1500.0)
    p2 = MockProductModel(product_id=10, name="DESK-WOOD-010", price=300.0)
    p3 = MockProductModel(product_id=5, name="EXPENSIVE-SERVER-005", price=10000.0)
    session.add_all([p1, p2, p3])

    # Seed inventory for product 42
    inv = WarehouseInventoryModel(
        product_id=42,
        warehouse_id=1,
        quantity=100,
        physical_qty=100,
        reserved_qty=0,
        incoming_qty=0,
        in_transit_qty=0,
    )
    session.add(inv)
    session.commit()

    yield session
    session.close()


def test_valid_sku_resolves_correctly_to_product_id(catalog_db_session):
    """A registered SKU code resolves to its actual product_id."""
    repo = InventoryRepo(catalog_db_session)
    service = InventoryService(repo)

    pid1 = service.resolve_sku_to_product_id("LAP-PRO-15")
    assert pid1 == 42

    pid2 = service.resolve_sku_to_product_id("DESK-WOOD-010")
    assert pid2 == 10


def test_invalid_sku_raises_value_error_without_regex_fallback(catalog_db_session):
    """
    CRIT-04 Safety Rule:
    SKU 'CHAIR-RED-005' does NOT exist in catalog.
    Old buggy behavior: Extracted digits '005' -> assigned product_id = 5 (EXPENSIVE-SERVER-005)!
    New safe behavior: Strictly raises ValueError and never assigns product_id 5 or defaults to 1.
    """
    repo = InventoryRepo(catalog_db_session)
    service = InventoryService(repo)

    with pytest.raises(ValueError, match="Invalid SKU 'CHAIR-RED-005': Product does not exist in catalog"):
        service.resolve_sku_to_product_id("CHAIR-RED-005")

    with pytest.raises(ValueError, match="Invalid SKU 'UNKNOWN-999': Product does not exist in catalog"):
        service.resolve_sku_to_product_id("UNKNOWN-999")

    with pytest.raises(ValueError, match="Invalid SKU '9999': Product does not exist in catalog"):
        service.resolve_sku_to_product_id("9999")


def test_approve_draft_proposal_rejects_nonexistent_sku(catalog_db_session):
    """
    Approving a proposal with an invalid/non-existent SKU must abort transaction
    and raise ValueError, preventing silent corruption of inventory.
    """
    repo = InventoryRepo(catalog_db_session)
    service = InventoryService(repo)

    # Create proposal with non-existent SKU that has embedded digits
    proposal = DraftProposalModel(
        proposal_id="PROP-INVALID-SKU-01",
        proposal_type="DraftAdjustmentProposal",
        sku_code="GHOST-ITEM-005",
        warehouse_id=1,
        current_quantity=0,
        proposed_quantity=10,
        adjustment=10,
        requested_by="operator_bob",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal)
    catalog_db_session.commit()

    with pytest.raises(ValueError, match="Invalid SKU 'GHOST-ITEM-005': Product does not exist in catalog"):
        service.approve_draft_proposal("PROP-INVALID-SKU-01", approved_by="manager_alice")

    # Verify status did not change to APPROVED
    reloaded = repo.get_draft_proposal("PROP-INVALID-SKU-01")
    assert reloaded.status == "DRAFT_PROPOSAL"
    assert reloaded.approved_by is None


def test_source_code_contains_no_regex_digits_fallback():
    """Verify that filter(str.isdigit, sku_str) is eliminated from InventoryService."""
    source = inspect.getsource(InventoryService.resolve_sku_to_product_id)
    assert "filter(str.isdigit" not in source, "Found forbidden filter(str.isdigit) in resolve_sku_to_product_id"

    approve_source = inspect.getsource(InventoryService.approve_draft_proposal)
    assert "filter(str.isdigit" not in approve_source, "Found forbidden filter(str.isdigit) in approve_draft_proposal"
