import pytest
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentType,
)
from app.shared.domain.business_exceptions import BusinessRuleViolationError


def test_add_multi_lot_same_product():
    """TASK-028: Test adding multiple items with the same product_id but different lot_numbers."""
    doc = Document(
        document_id=1,
        doc_type=DocumentType.IMPORT,
        to_warehouse_id=10,
        created_by="test_user",
    )

    item_lot1 = DocumentProduct(
        product_id=101,
        quantity=50,
        unit_price=10.0,
        lot_number="LOT-2026-A",
    )
    item_lot2 = DocumentProduct(
        product_id=101,
        quantity=30,
        unit_price=10.0,
        lot_number="LOT-2026-B",
    )

    # 1. Adding 2 items with same product_id but different lot_number should succeed
    doc.add_item(item_lot1)
    doc.add_item(item_lot2)

    assert len(doc.items) == 2
    assert doc.items[0].product_id == 101
    assert doc.items[0].lot_number == "LOT-2026-A"
    assert doc.items[1].product_id == 101
    assert doc.items[1].lot_number == "LOT-2026-B"

    # 2. Adding item with same product_id and same lot_number should raise BusinessRuleViolationError
    item_duplicate_lot = DocumentProduct(
        product_id=101,
        quantity=20,
        unit_price=10.0,
        lot_number="LOT-2026-A",
    )

    with pytest.raises(BusinessRuleViolationError) as exc_info:
        doc.add_item(item_duplicate_lot)
    assert "already exists" in str(exc_info.value)


def test_add_same_product_same_empty_lot():
    """Test duplicate check for items with default/empty lot_numbers."""
    doc = Document(
        document_id=2,
        doc_type=DocumentType.IMPORT,
        to_warehouse_id=10,
        created_by="test_user",
    )

    item1 = DocumentProduct(product_id=202, quantity=10, unit_price=5.0)
    item2 = DocumentProduct(product_id=202, quantity=15, unit_price=5.0)

    doc.add_item(item1)
    with pytest.raises(BusinessRuleViolationError):
        doc.add_item(item2)
