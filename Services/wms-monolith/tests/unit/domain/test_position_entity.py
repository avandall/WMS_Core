"""
Comprehensive Unit Tests for Position Domain Entity
Covers all Position entity methods, validation, edge cases, and business rules
"""

import pytest
from app.modules.positions.domain.entities.position import Position, PositionInventoryItem


class TestPositionEntity:
    """Test Position Domain Entity"""

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_position_initialization_valid_data(self):
        """Test Position initialization with valid data"""
        position = Position(
            id=1,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE",
            description="Main storage area",
            is_active=True
        )
        assert position.id == 1
        assert position.warehouse_id == 1
        assert position.code == "STORAGE"
        assert position.type == "STORAGE"
        assert position.description == "Main storage area"
        assert position.is_active is True

    def test_position_initialization_minimal_data(self):
        """Test Position initialization with minimal required data"""
        position = Position(
            id=1,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE"
        )
        assert position.id == 1
        assert position.warehouse_id == 1
        assert position.code == "STORAGE"
        assert position.type == "STORAGE"
        assert position.description is None
        assert position.is_active is True

    def test_position_initialization_inactive(self):
        """Test Position initialization with inactive status"""
        position = Position(
            id=1,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE",
            is_active=False
        )
        assert position.is_active is False

    # ============================================================================
    # POSITION INVENTORY ITEM TESTS
    # ============================================================================

    def test_position_inventory_item_initialization(self):
        """Test PositionInventoryItem initialization"""
        item = PositionInventoryItem(
            warehouse_id=1,
            position_code="STORAGE",
            product_id=100,
            quantity=50
        )
        assert item.warehouse_id == 1
        assert item.position_code == "STORAGE"
        assert item.product_id == 100
        assert item.quantity == 50

    def test_position_inventory_item_zero_quantity(self):
        """Test PositionInventoryItem with zero quantity"""
        item = PositionInventoryItem(
            warehouse_id=1,
            position_code="STORAGE",
            product_id=100,
            quantity=0
        )
        assert item.quantity == 0

    def test_position_inventory_item_large_quantity(self):
        """Test PositionInventoryItem with large quantity"""
        item = PositionInventoryItem(
            warehouse_id=1,
            position_code="STORAGE",
            product_id=100,
            quantity=10000
        )
        assert item.quantity == 10000

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_position_with_unicode_code(self):
        """Test Position with Unicode characters in code"""
        position = Position(
            id=1,
            warehouse_id=1,
            code="STÖRÄGÉ",
            type="STORAGE"
        )
        assert position.code == "STÖRÄGÉ"

    def test_position_with_unicode_description(self):
        """Test Position with Unicode characters in description"""
        position = Position(
            id=1,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE",
            description="Mäin Störägé Ärëä"
        )
        assert position.description == "Mäin Störägé Ärëä"

    def test_position_with_special_characters_in_description(self):
        """Test Position with special characters in description"""
        position = Position(
            id=1,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE",
            description="Area-1 @#$%"
        )
        assert position.description == "Area-1 @#$%"

    def test_position_with_very_long_description(self):
        """Test Position with very long description"""
        long_desc = "a" * 1000
        position = Position(
            id=1,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE",
            description=long_desc
        )
        assert position.description == long_desc

    # ============================================================================
    # BUSINESS LOGIC TESTS
    # ============================================================================

    def test_position_type_variations(self):
        """Test Position with different types"""
        types = ["RECEIVING", "STORAGE", "SHIPPING", "UNASSIGNED"]
        
        for pos_type in types:
            position = Position(
                id=1,
                warehouse_id=1,
                code=pos_type,
                type=pos_type
            )
            assert position.type == pos_type

    def test_position_code_normalization(self):
        """Test position codes are stored as-is (no normalization in entity)"""
        position = Position(
            id=1,
            warehouse_id=1,
            code="storage",
            type="STORAGE"
        )
        assert position.code == "storage"

    # ============================================================================
    # DATA INTEGRITY TESTS
    # ============================================================================

    def test_position_with_extreme_values(self):
        """Test position creation with extreme values"""
        # Very large id
        position1 = Position(
            id=2147483647,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE"
        )
        assert position1.id == 2147483647

        # Very large warehouse_id
        position2 = Position(
            id=1,
            warehouse_id=2147483647,
            code="STORAGE",
            type="STORAGE"
        )
        assert position2.warehouse_id == 2147483647

    def test_position_attribute_types(self):
        """Test that position attributes maintain correct types"""
        position = Position(
            id=1,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE",
            description="Test",
            is_active=True
        )
        
        assert isinstance(position.id, int)
        assert isinstance(position.warehouse_id, int)
        assert isinstance(position.code, str)
        assert isinstance(position.type, str)
        assert isinstance(position.description, (str, type(None)))
        assert isinstance(position.is_active, bool)

    def test_position_inventory_item_attribute_types(self):
        """Test that position inventory item attributes maintain correct types"""
        item = PositionInventoryItem(
            warehouse_id=1,
            position_code="STORAGE",
            product_id=100,
            quantity=50
        )
        
        assert isinstance(item.warehouse_id, int)
        assert isinstance(item.position_code, str)
        assert isinstance(item.product_id, int)
        assert isinstance(item.quantity, int)
