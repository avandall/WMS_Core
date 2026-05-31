"""
Comprehensive Unit Tests for StockMovementService
Covers all StockMovementService methods, validation, edge cases, and business logic
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from app.modules.inventory.application.services.stock_movement_service import StockMovementService
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    InsufficientStockError,
    InvalidQuantityError,
    ValidationError,
)
from app.modules.positions.domain.interfaces.position_repo import IPositionRepo
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo
from app.modules.audit.domain.interfaces.audit_event_repo import IAuditEventRepo


class TestStockMovementService:
    """Test StockMovementService Application Service"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_position_repo(self):
        """Mock position repository"""
        repo = Mock(spec=IPositionRepo)
        repo.get_total_quantity_for_product.return_value = 0
        return repo

    @pytest.fixture
    def mock_warehouse_repo(self):
        """Mock warehouse repository"""
        repo = Mock(spec=IWarehouseRepo)
        repo.get_warehouse_inventory.return_value = []
        return repo

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session

    @pytest.fixture
    def mock_audit_repo(self):
        """Mock audit event repository"""
        return Mock(spec=IAuditEventRepo)

    @pytest.fixture
    def stock_movement_service(self, mock_position_repo, mock_warehouse_repo, mock_session, mock_audit_repo):
        """StockMovementService instance with mocked dependencies"""
        return StockMovementService(
            position_repo=mock_position_repo,
            warehouse_repo=mock_warehouse_repo,
            session=mock_session,
            audit_event_repo=mock_audit_repo,
        )

    @pytest.fixture
    def mock_from_position(self):
        """Mock from position model"""
        position = Mock()
        position.id = 1
        position.code = "RECEIVING"
        return position

    @pytest.fixture
    def mock_to_position(self):
        """Mock to position model"""
        position = Mock()
        position.id = 2
        position.code = "STORAGE"
        return position

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_stock_movement_service_initialization(self, mock_position_repo, mock_warehouse_repo, mock_session):
        """Test StockMovementService initialization"""
        service = StockMovementService(
            position_repo=mock_position_repo,
            warehouse_repo=mock_warehouse_repo,
            session=mock_session,
        )
        assert service.position_repo == mock_position_repo
        assert service.warehouse_repo == mock_warehouse_repo
        assert service.session == mock_session

    # ============================================================================
    # PUT AWAY TESTS
    # ============================================================================

    def test_put_away_success(self, stock_movement_service, mock_position_repo, mock_from_position, mock_to_position):
        """Test put_away operation"""
        mock_position_repo.get_position_model.side_effect = [mock_from_position, mock_to_position]

        result = stock_movement_service.put_away(
            warehouse_id=1,
            product_id=1,
            quantity=50,
            from_position_code="RECEIVING",
            to_position_code="STORAGE",
            user_id=1
        )

        assert result["warehouse_id"] == 1
        assert result["product_id"] == 1
        assert result["quantity"] == 50
        assert result["from_position"] == "RECEIVING"
        assert result["to_position"] == "STORAGE"

    def test_put_away_defaults(self, stock_movement_service, mock_position_repo, mock_from_position, mock_to_position):
        """Test put_away with default positions"""
        mock_position_repo.get_position_model.side_effect = [mock_from_position, mock_to_position]

        result = stock_movement_service.put_away(
            warehouse_id=1,
            product_id=1,
            quantity=50
        )

        assert result["from_position"] == "RECEIVING"
        assert result["to_position"] == "STORAGE"

    # ============================================================================
    # PICK TESTS
    # ============================================================================

    def test_pick_success(self, stock_movement_service, mock_position_repo, mock_from_position, mock_to_position):
        """Test pick operation"""
        mock_from_position.code = "STORAGE"
        mock_to_position.code = "SHIPPING"
        mock_position_repo.get_position_model.side_effect = [mock_from_position, mock_to_position]

        result = stock_movement_service.pick(
            warehouse_id=1,
            product_id=1,
            quantity=50,
            from_position_code="STORAGE",
            to_position_code="SHIPPING",
            user_id=1
        )

        assert result["warehouse_id"] == 1
        assert result["product_id"] == 1
        assert result["quantity"] == 50
        assert result["from_position"] == "STORAGE"
        assert result["to_position"] == "SHIPPING"

    def test_pick_defaults(self, stock_movement_service, mock_position_repo, mock_from_position, mock_to_position):
        """Test pick with default positions"""
        mock_from_position.code = "STORAGE"
        mock_to_position.code = "SHIPPING"
        mock_position_repo.get_position_model.side_effect = [mock_from_position, mock_to_position]

        result = stock_movement_service.pick(
            warehouse_id=1,
            product_id=1,
            quantity=50
        )

        assert result["from_position"] == "STORAGE"
        assert result["to_position"] == "SHIPPING"

    # ============================================================================
    # MOVE WITHIN WAREHOUSE TESTS
    # ============================================================================

    
    def test_move_within_warehouse_success(self, stock_movement_service, mock_position_repo, mock_from_position, mock_to_position):
        """Test move_within_warehouse success"""
        mock_position_repo.get_position_model.side_effect = [mock_from_position, mock_to_position]

        result = stock_movement_service.move_within_warehouse(
            warehouse_id=1,
            product_id=1,
            quantity=50,
            from_position_code="RECEIVING",
            to_position_code="STORAGE",
            user_id=1
        )

        assert result["warehouse_id"] == 1
        assert result["product_id"] == 1
        assert result["quantity"] == 50
        assert result["from_position"] == "RECEIVING"
        assert result["to_position"] == "STORAGE"

        mock_position_repo.adjust_position_stock.assert_any_call(position_id=1, product_id=1, delta=-50)
        mock_position_repo.adjust_position_stock.assert_any_call(position_id=2, product_id=1, delta=50)

    
    def test_move_within_warehouse_invalid_quantity(self, stock_movement_service):
        """Test move_within_warehouse with invalid quantity"""
        with pytest.raises(InvalidQuantityError, match="Quantity must be positive"):
            stock_movement_service.move_within_warehouse(
                warehouse_id=1,
                product_id=1,
                quantity=0,
                from_position_code="RECEIVING",
                to_position_code="STORAGE"
            )

    
    def test_move_within_warehouse_negative_quantity(self, stock_movement_service):
        """Test move_within_warehouse with negative quantity"""
        with pytest.raises(InvalidQuantityError, match="Quantity must be positive"):
            stock_movement_service.move_within_warehouse(
                warehouse_id=1,
                product_id=1,
                quantity=-10,
                from_position_code="RECEIVING",
                to_position_code="STORAGE"
            )

    
    def test_move_within_warehouse_same_position(self, stock_movement_service):
        """Test move_within_warehouse with same from and to position"""
        with pytest.raises(BusinessRuleViolationError, match="from_position and to_position must differ"):
            stock_movement_service.move_within_warehouse(
                warehouse_id=1,
                product_id=1,
                quantity=50,
                from_position_code="STORAGE",
                to_position_code="STORAGE"
            )

    
    def test_move_within_warehouse_insufficient_stock(self, stock_movement_service, mock_position_repo, mock_from_position, mock_to_position, mock_session):
        """Test move_within_warehouse with insufficient stock"""
        mock_position_repo.get_position_model.side_effect = [mock_from_position, mock_to_position]
        mock_position_repo.adjust_position_stock.side_effect = InsufficientStockError("Insufficient stock")

        with pytest.raises(InsufficientStockError):
            stock_movement_service.move_within_warehouse(
                warehouse_id=1,
                product_id=1,
                quantity=50,
                from_position_code="RECEIVING",
                to_position_code="STORAGE"
            )

        mock_session.rollback.assert_called_once()

    
    def test_move_within_warehouse_generic_error(self, stock_movement_service, mock_position_repo, mock_from_position, mock_to_position, mock_session):
        """Test move_within_warehouse with generic error"""
        mock_position_repo.get_position_model.side_effect = [mock_from_position, mock_to_position]
        mock_position_repo.adjust_position_stock.side_effect = Exception("Generic error")

        with pytest.raises(ValidationError):
            stock_movement_service.move_within_warehouse(
                warehouse_id=1,
                product_id=1,
                quantity=50,
                from_position_code="RECEIVING",
                to_position_code="STORAGE"
            )

        mock_session.rollback.assert_called_once()

    # ============================================================================
    # TRANSFER BETWEEN WAREHOUSES TESTS
    # ============================================================================

    
    def test_transfer_between_warehouses_success(self, stock_movement_service, mock_position_repo, mock_warehouse_repo, mock_to_position):
        """Test transfer_between_warehouses success"""
        mock_position_repo.get_position_model.return_value = mock_to_position
        mock_position_repo.allocate_and_remove.return_value = [("STORAGE", 50)]
        mock_warehouse_repo.get_warehouse_inventory.return_value = []

        result = stock_movement_service.transfer_between_warehouses(
            from_warehouse_id=1,
            to_warehouse_id=2,
            product_id=1,
            quantity=50,
            from_position_code="SHIPPING",
            to_position_code="RECEIVING",
            user_id=1
        )

        assert result["product_id"] == 1
        assert result["quantity"] == 50
        assert result["from"]["warehouse_id"] == 1
        assert result["to"]["warehouse_id"] == 2

    
    def test_transfer_between_warehouses_invalid_quantity(self, stock_movement_service):
        """Test transfer_between_warehouses with invalid quantity"""
        with pytest.raises(InvalidQuantityError, match="Quantity must be positive"):
            stock_movement_service.transfer_between_warehouses(
                from_warehouse_id=1,
                to_warehouse_id=2,
                product_id=1,
                quantity=0,
                from_position_code="SHIPPING",
                to_position_code="RECEIVING"
            )

    
    def test_transfer_between_warehouses_same_warehouse(self, stock_movement_service):
        """Test transfer_between_warehouses with same warehouse"""
        with pytest.raises(ValidationError, match="Cannot transfer within the same warehouse"):
            stock_movement_service.transfer_between_warehouses(
                from_warehouse_id=1,
                to_warehouse_id=1,
                product_id=1,
                quantity=50,
                from_position_code="SHIPPING",
                to_position_code="RECEIVING"
            )

    
    def test_transfer_between_warehouses_insufficient_stock(self, stock_movement_service, mock_position_repo, mock_to_position, mock_session):
        """Test transfer_between_warehouses with insufficient stock"""
        mock_position_repo.get_position_model.return_value = mock_to_position
        mock_position_repo.allocate_and_remove.side_effect = InsufficientStockError("Insufficient stock")

        with pytest.raises(InsufficientStockError):
            stock_movement_service.transfer_between_warehouses(
                from_warehouse_id=1,
                to_warehouse_id=2,
                product_id=1,
                quantity=50
            )

        mock_session.rollback.assert_called_once()

    # ============================================================================
    # ENSURE DEFAULTS AND BALANCE TESTS
    # ============================================================================

    
    def test_ensure_defaults_and_balance_no_diff(self, stock_movement_service, mock_position_repo, mock_warehouse_repo):
        """Test _ensure_defaults_and_balance when warehouse and position totals match"""
        mock_warehouse_repo.get_warehouse_inventory.return_value = [Mock(product_id=1, quantity=100)]
        mock_position_repo.get_total_quantity_for_product.return_value = 100

        stock_movement_service._ensure_defaults_and_balance(1, 1)

        mock_position_repo.adjust_position_stock.assert_not_called()

    
    def test_ensure_defaults_and_balance_positive_diff(self, stock_movement_service, mock_position_repo, mock_warehouse_repo):
        """Test _ensure_defaults_and_balance when warehouse has more stock"""
        mock_warehouse_repo.get_warehouse_inventory.return_value = [Mock(product_id=1, quantity=100)]
        mock_position_repo.get_total_quantity_for_product.return_value = 80
        mock_unassigned = Mock()
        mock_unassigned.id = 1
        mock_position_repo.get_position_model.return_value = mock_unassigned

        stock_movement_service._ensure_defaults_and_balance(1, 1)

        mock_position_repo.adjust_position_stock.assert_called_once_with(position_id=1, product_id=1, delta=20)

    
    def test_ensure_defaults_and_balance_negative_diff(self, stock_movement_service, mock_position_repo, mock_warehouse_repo):
        """Test _ensure_defaults_and_balance when positions have more stock"""
        mock_warehouse_repo.get_warehouse_inventory.return_value = [Mock(product_id=1, quantity=80)]
        mock_position_repo.get_total_quantity_for_product.return_value = 100
        mock_unassigned = Mock()
        mock_unassigned.id = 1
        mock_position_repo.get_position_model.return_value = mock_unassigned

        stock_movement_service._ensure_defaults_and_balance(1, 1)

        mock_position_repo.adjust_position_stock.assert_called_once_with(position_id=1, product_id=1, delta=-20)

    
    def test_ensure_defaults_and_balance_negative_diff_insufficient(self, stock_movement_service, mock_position_repo, mock_warehouse_repo):
        """Test _ensure_defaults_and_balance when position stock exceeds and insufficient to adjust"""
        mock_warehouse_repo.get_warehouse_inventory.return_value = [Mock(product_id=1, quantity=80)]
        mock_position_repo.get_total_quantity_for_product.return_value = 100
        mock_unassigned = Mock()
        mock_unassigned.id = 1
        mock_position_repo.get_position_model.return_value = mock_unassigned
        mock_position_repo.adjust_position_stock.side_effect = InsufficientStockError("Insufficient")

        with pytest.raises(ValidationError, match="Position stock exceeds warehouse stock"):
            stock_movement_service._ensure_defaults_and_balance(1, 1)

    # ============================================================================
    # GET WAREHOUSE PRODUCT QUANTITY TESTS
    # ============================================================================

    
    def test_get_warehouse_product_quantity_found(self, stock_movement_service, mock_warehouse_repo):
        """Test _get_warehouse_product_quantity when product found"""
        mock_warehouse_repo.get_warehouse_inventory.return_value = [
            Mock(product_id=1, quantity=100),
            Mock(product_id=2, quantity=50),
        ]

        result = stock_movement_service._get_warehouse_product_quantity(1, 1)

        assert result == 100

    
    def test_get_warehouse_product_quantity_not_found(self, stock_movement_service, mock_warehouse_repo):
        """Test _get_warehouse_product_quantity when product not found"""
        mock_warehouse_repo.get_warehouse_inventory.return_value = [
            Mock(product_id=2, quantity=50),
        ]

        result = stock_movement_service._get_warehouse_product_quantity(1, 1)

        assert result == 0

    
    def test_get_warehouse_product_quantity_empty(self, stock_movement_service, mock_warehouse_repo):
        """Test _get_warehouse_product_quantity with empty inventory"""
        mock_warehouse_repo.get_warehouse_inventory.return_value = []

        result = stock_movement_service._get_warehouse_product_quantity(1, 1)

        assert result == 0

    # ============================================================================
    # SET REPOS AUTO COMMIT TESTS
    # ============================================================================

    
    def test_set_repos_auto_commit_enabled(self, stock_movement_service, mock_position_repo, mock_warehouse_repo, mock_audit_repo):
        """Test _set_repos_auto_commit with enabled=True"""
        mock_position_repo.set_auto_commit = Mock()
        mock_warehouse_repo.set_auto_commit = Mock()
        mock_audit_repo.set_auto_commit = Mock()

        stock_movement_service._set_repos_auto_commit(True)

        mock_position_repo.set_auto_commit.assert_called_once_with(True)
        mock_warehouse_repo.set_auto_commit.assert_called_once_with(True)
        mock_audit_repo.set_auto_commit.assert_called_once_with(True)

    
    def test_set_repos_auto_commit_disabled(self, stock_movement_service, mock_position_repo, mock_warehouse_repo, mock_audit_repo):
        """Test _set_repos_auto_commit with enabled=False"""
        mock_position_repo.set_auto_commit = Mock()
        mock_warehouse_repo.set_auto_commit = Mock()
        mock_audit_repo.set_auto_commit = Mock()

        stock_movement_service._set_repos_auto_commit(False)

        mock_position_repo.set_auto_commit.assert_called_once_with(False)
        mock_warehouse_repo.set_auto_commit.assert_called_once_with(False)
        mock_audit_repo.set_auto_commit.assert_called_once_with(False)

    
    def test_set_repos_auto_commit_none_repo(self, mock_position_repo, mock_warehouse_repo, mock_session):
        """Test _set_repos_auto_commit with None repo"""
        service = StockMovementService(
            position_repo=mock_position_repo,
            warehouse_repo=mock_warehouse_repo,
            session=mock_session,
            audit_event_repo=None,
        )

        # Should not raise error
        service._set_repos_auto_commit(True)
