"""
Comprehensive Unit Tests for PositionService
Covers all PositionService methods, validation, edge cases, and business logic
"""

import pytest
from unittest.mock import Mock, MagicMock

from app.modules.positions.application.services.position_service import PositionService
from app.modules.positions.domain.entities.position import Position, PositionInventoryItem
from app.modules.positions.domain.interfaces.position_repo import IPositionRepo
from app.modules.audit.domain.interfaces.audit_event_repo import IAuditEventRepo


class TestPositionService:
    """Test PositionService Application Service"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_position_repo(self):
        """Mock position repository"""
        return Mock(spec=IPositionRepo)

    @pytest.fixture
    def mock_audit_repo(self):
        """Mock audit event repository"""
        return Mock(spec=IAuditEventRepo)

    @pytest.fixture
    def position_service(self, mock_position_repo, mock_audit_repo):
        """PositionService instance with mocked dependencies"""
        return PositionService(mock_position_repo, mock_audit_repo)

    @pytest.fixture
    def position_service_no_audit(self, mock_position_repo):
        """PositionService instance without audit repo"""
        return PositionService(mock_position_repo, None)

    @pytest.fixture
    def sample_position(self):
        """Sample position for testing"""
        return Position(
            id=1,
            warehouse_id=1,
            code="A-01-01",
            type="STORAGE",
            description="Test Position"
        )

    @pytest.fixture
    def sample_inventory_item(self):
        """Sample inventory item for testing"""
        return PositionInventoryItem(
            warehouse_id=1,
            position_code="A-01-01",
            product_id=1,
            quantity=50
        )

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_position_service_initialization(self, mock_position_repo, mock_audit_repo):
        """Test PositionService initialization"""
        service = PositionService(mock_position_repo, mock_audit_repo)
        assert service.position_repo == mock_position_repo
        assert service.audit_event_repo == mock_audit_repo

    def test_position_service_initialization_no_audit(self, mock_position_repo):
        """Test PositionService initialization without audit repo"""
        service = PositionService(mock_position_repo, None)
        assert service.position_repo == mock_position_repo
        assert service.audit_event_repo is None

    # ============================================================================
    # ENSURE DEFAULTS TESTS
    # ============================================================================

    def test_ensure_defaults(self, position_service, mock_position_repo):
        """Test ensure default positions"""
        position_service.ensure_defaults(1)

        mock_position_repo.ensure_default_positions.assert_called_once_with(1)

    # ============================================================================
    # CREATE POSITION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_create_position_success(self, position_service, mock_position_repo, mock_audit_repo, sample_position):
        """Test create position with valid data"""
        mock_position_repo.create_position.return_value = sample_position

        result = await position_service.create_position(
            warehouse_id=1,
            code="A-01-01",
            type="STORAGE",
            description="Test Position",
            user_id=1
        )

        mock_position_repo.ensure_default_positions.assert_called_once_with(1)
        mock_position_repo.create_position.assert_called_once_with(
            warehouse_id=1,
            code="A-01-01",
            type="STORAGE",
            description="Test Position",
            capacity=None,
            zone=None
        )
        mock_audit_repo.create_event.assert_called_once()
        assert result == sample_position

    @pytest.mark.asyncio
    async def test_create_position_without_audit(self, position_service_no_audit, mock_position_repo, sample_position):
        """Test create position without audit repo"""
        mock_position_repo.create_position.return_value = sample_position

        result = await position_service_no_audit.create_position(
            warehouse_id=1,
            code="A-01-01",
            type="STORAGE"
        )

        mock_position_repo.ensure_default_positions.assert_called_once_with(1)
        mock_position_repo.create_position.assert_called_once()
        assert result == sample_position

    @pytest.mark.asyncio
    async def test_create_position_default_type(self, position_service, mock_position_repo, sample_position):
        """Test create position with default type"""
        mock_position_repo.create_position.return_value = sample_position

        await position_service.create_position(
            warehouse_id=1,
            code="A-01-01"
        )

        mock_position_repo.create_position.assert_called_once_with(
            warehouse_id=1,
            code="A-01-01",
            type="STORAGE",
            description=None,
            capacity=None,
            zone=None
        )

    @pytest.mark.asyncio
    async def test_create_position_without_user(self, position_service, mock_position_repo, mock_audit_repo, sample_position):
        """Test create position without user_id"""
        mock_position_repo.create_position.return_value = sample_position

        await position_service.create_position(
            warehouse_id=1,
            code="A-01-01"
        )

        # Check audit event was created without user_id
        call_args = mock_audit_repo.create_event.call_args
        assert call_args.kwargs.get("user_id") is None

    # ============================================================================
    # LIST POSITIONS TESTS
    # ============================================================================

    def test_list_positions_active_only(self, position_service, mock_position_repo, sample_position):
        """Test list positions with active only"""
        mock_position_repo.list_positions.return_value = [sample_position]

        result = position_service.list_positions(1, include_inactive=False)

        mock_position_repo.ensure_default_positions.assert_called_once_with(1)
        mock_position_repo.list_positions.assert_called_once_with(1, include_inactive=False)
        assert len(result) == 1
        assert result[0] == sample_position

    def test_list_positions_include_inactive(self, position_service, mock_position_repo, sample_position):
        """Test list positions including inactive"""
        mock_position_repo.list_positions.return_value = [sample_position]

        result = position_service.list_positions(1, include_inactive=True)

        mock_position_repo.list_positions.assert_called_once_with(1, include_inactive=True)
        assert len(result) == 1

    def test_list_positions_empty(self, position_service, mock_position_repo):
        """Test list positions with no positions"""
        mock_position_repo.list_positions.return_value = []

        result = position_service.list_positions(1)

        assert result == []

    def test_list_positions_multiple(self, position_service, mock_position_repo):
        """Test list positions with multiple positions"""
        position1 = Position(id=1, warehouse_id=1, code="A-01-01", type="STORAGE")
        position2 = Position(id=2, warehouse_id=1, code="A-01-02", type="STORAGE")
        mock_position_repo.list_positions.return_value = [position1, position2]

        result = position_service.list_positions(1)

        assert len(result) == 2

    # ============================================================================
    # LIST POSITION INVENTORY TESTS
    # ============================================================================

    def test_list_position_inventory(self, position_service, mock_position_repo, sample_inventory_item):
        """Test list position inventory"""
        mock_position_repo.list_position_inventory.return_value = [sample_inventory_item]

        result = position_service.list_position_inventory(1, "A-01-01")

        mock_position_repo.ensure_default_positions.assert_called_once_with(1)
        mock_position_repo.list_position_inventory.assert_called_once_with(1, "A-01-01")
        assert len(result) == 1
        assert result[0] == sample_inventory_item

    def test_list_position_inventory_empty(self, position_service, mock_position_repo):
        """Test list position inventory with no items"""
        mock_position_repo.list_position_inventory.return_value = []

        result = position_service.list_position_inventory(1, "A-01-01")

        assert result == []

    def test_list_position_inventory_multiple(self, position_service, mock_position_repo):
        """Test list position inventory with multiple items"""
        item1 = PositionInventoryItem(warehouse_id=1, position_code="A-01-01", product_id=1, quantity=50)
        item2 = PositionInventoryItem(warehouse_id=1, position_code="A-01-01", product_id=2, quantity=30)
        mock_position_repo.list_position_inventory.return_value = [item1, item2]

        result = position_service.list_position_inventory(1, "A-01-01")

        assert len(result) == 2
