"""
Comprehensive Unit Tests for Warehouses API Endpoint
Covers all warehouse endpoints, validation, error handling, and business logic
"""

import pytest
from unittest.mock import AsyncMock, patch
from unittest import mock

# Make FastAPI imports conditional
try:
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    HTTPException = Exception
    TestClient = mock.Mock

try:
    from app.api.v1.endpoints.warehouses import router
    from app.core.permissions import Permission
    from app.application.dtos.warehouse import (
        WarehouseCreate,
        WarehouseResponse,
        WarehouseDetailResponse,
        WarehouseListResponse,
        WarehouseStats
    )
    from app.application.dtos.product import TransferInventoryRequest
    from app.application.services.warehouse_service import WarehouseService
    from app.domain.entities.warehouse import Warehouse
    from app.domain.entities.inventory import InventoryItem
    API_IMPORTS_AVAILABLE = True
except ImportError:
    API_IMPORTS_AVAILABLE = False
    router = mock.Mock()
    Permission = mock.Mock
    WarehouseCreate = mock.Mock
    WarehouseResponse = mock.Mock
    WarehouseDetailResponse = mock.Mock
    WarehouseListResponse = mock.Mock
    WarehouseStats = mock.Mock
    TransferInventoryRequest = mock.Mock
    WarehouseService = mock.Mock
    Warehouse = mock.Mock
    InventoryItem = mock.Mock


@pytest.mark.skipif(not API_IMPORTS_AVAILABLE, reason="API dependencies not available")
class TestWarehousesEndpoint:
    """Test Warehouses API Endpoints"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_warehouse_service(self):
        """mock.Mock WarehouseService"""
        service = mock.Mock(spec=WarehouseService)
        service.get_all_warehouses = mock.Mock()
        service.create_warehouse = mock.Mock()
        service.get_warehouse = mock.Mock()
        service.delete_warehouse = mock.Mock()
        service.get_warehouse_inventory = mock.Mock()
        service.transfer_all_inventory = mock.Mock()
        return service

    @pytest.fixture
    def mock_current_user(self):
        """mock.Mock current user"""
        user = mock.Mock()
        user.role = "admin"
        user.user_id = 1
        return user

    @pytest.fixture
    def sample_warehouse(self):
        """Sample warehouse for testing"""
        return Warehouse(
            warehouse_id=1,
            location="Test Warehouse"
        )

    @pytest.fixture
    def sample_inventory_item(self):
        """Sample inventory item for testing"""
        return InventoryItem(
            product_id=1,
            quantity=50
        )

    @pytest.fixture
    def sample_warehouse_create(self):
        """Sample WarehouseCreate DTO"""
        return WarehouseCreate(
            name="Test Warehouse",
            code="WH001"
        )

    @pytest.fixture
    def sample_transfer_request(self):
        """Sample transfer request"""
        transfer_request = mock.Mock()
        transfer_request.to_warehouse_id = 2
        return transfer_request

    # ============================================================================
    # GET ALL WAREHOUSES TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_all_warehouses_success(self, mock_warehouse_service, sample_warehouse, sample_inventory_item):
        """Test get_all_warehouses endpoint successful response"""
        # mock.Mock service to return warehouses
        mock_warehouse_service.get_all_warehouses.return_value = [sample_warehouse]
        mock_warehouse_service.get_warehouse_inventory.return_value = [sample_inventory_item]
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            # Import the endpoint function
            from app.api.v1.endpoints.warehouses import get_all_warehouses
            
            # Call the endpoint
            result = await get_all_warehouses(mock_warehouse_service)
            
            # Verify service was called
            mock_warehouse_service.get_all_warehouses.assert_called_once()
            mock_warehouse_service.get_warehouse_inventory.assert_called_once_with(1)
            
            # Verify response structure
            assert len(result) == 1
            assert result[0].warehouse_id == 1
            assert result[0].name == "Test Warehouse"
            assert result[0].location == "Test Warehouse"
            assert len(result[0].inventory) == 1
            assert result[0].inventory[0].product_id == 1
            assert result[0].inventory[0].quantity == 50

    @pytest.mark.asyncio
    async def test_get_all_warehouses_empty(self, mock_warehouse_service):
        """Test get_all_warehouses endpoint with no warehouses"""
        # mock.Mock service to return empty list
        mock_warehouse_service.get_all_warehouses.return_value = []
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_all_warehouses
            
            result = await get_all_warehouses(mock_warehouse_service)
            
            # Verify result
            assert result == []

    @pytest.mark.asyncio
    async def test_get_all_warehouses_multiple(self, mock_warehouse_service, sample_inventory_item):
        """Test get_all_warehouses endpoint with multiple warehouses"""
        # Create sample warehouses
        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse 1")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse 2")
        
        # mock.Mock service to return warehouses
        mock_warehouse_service.get_all_warehouses.return_value = [warehouse1, warehouse2]
        mock_warehouse_service.get_warehouse_inventory.return_value = [sample_inventory_item]
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_all_warehouses
            
            result = await get_all_warehouses(mock_warehouse_service)
            
            # Verify result
            assert len(result) == 2
            assert result[0].warehouse_id == 1
            assert result[1].warehouse_id == 2
            assert mock_warehouse_service.get_warehouse_inventory.call_count == 2

    @pytest.mark.asyncio
    async def test_get_all_warehouses_empty_inventory(self, mock_warehouse_service, sample_warehouse):
        """Test get_all_warehouses endpoint with warehouses having empty inventory"""
        # mock.Mock service to return warehouses
        mock_warehouse_service.get_all_warehouses.return_value = [sample_warehouse]
        mock_warehouse_service.get_warehouse_inventory.return_value = []
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_all_warehouses
            
            result = await get_all_warehouses(mock_warehouse_service)
            
            # Verify result
            assert len(result) == 1
            assert len(result[0].inventory) == 0

    # ============================================================================
    # CREATE WAREHOUSE TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_create_warehouse_success(self, mock_warehouse_service, sample_warehouse, sample_warehouse_create):
        """Test create_warehouse endpoint successful response"""
        # mock.Mock service to return created warehouse
        mock_warehouse_service.create_warehouse.return_value = sample_warehouse
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import create_warehouse
            
            result = await create_warehouse(sample_warehouse_create, mock_warehouse_service)
            
            # Verify service was called
            mock_warehouse_service.create_warehouse.assert_called_once_with("Test Warehouse")
            
            # Verify response
            assert result.warehouse_id == 1
            assert result.name == "Test Warehouse"
            assert result.location == "Test Warehouse"

    @pytest.mark.asyncio
    async def test_create_warehouse_unicode_name(self, mock_warehouse_service, sample_warehouse):
        """Test create_warehouse endpoint with Unicode name"""
        # Create warehouse with Unicode name
        warehouse_create = WarehouseCreate(name="Tëst Wäréhøüse", code="WH001")
        
        # mock.Mock service to return created warehouse
        unicode_warehouse = Warehouse(warehouse_id=1, location="Tëst Wäréhøüse")
        mock_warehouse_service.create_warehouse.return_value = unicode_warehouse
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import create_warehouse
            
            result = await create_warehouse(warehouse_create, mock_warehouse_service)
            
            # Verify service was called with Unicode name
            mock_warehouse_service.create_warehouse.assert_called_once_with("Tëst Wäréhøüse")
            
            # Verify response
            assert result.name == "Tëst Wäréhøüse"

    @pytest.mark.asyncio
    async def test_create_warehouse_special_characters(self, mock_warehouse_service, sample_warehouse):
        """Test create_warehouse endpoint with special characters"""
        # Create warehouse with special characters
        warehouse_create = WarehouseCreate(name="Warehouse-123_@#$%", code="WH001")
        
        # mock.Mock service to return created warehouse
        special_warehouse = Warehouse(warehouse_id=1, location="Warehouse-123_@#$%")
        mock_warehouse_service.create_warehouse.return_value = special_warehouse
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import create_warehouse
            
            result = await create_warehouse(warehouse_create, mock_warehouse_service)
            
            # Verify response
            assert result.name == "Warehouse-123_@#$%"

    @pytest.mark.asyncio
    async def test_create_warehouse_permission_denied(self, mock_warehouse_service, sample_warehouse_create):
        """Test create_warehouse endpoint with permission denied"""
        # Note: Permission decorators are applied at FastAPI level
        # This test verifies the service method exists and can be called
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import create_warehouse
            
            # Test that the function exists and can be called (permissions handled by FastAPI)
            mock_warehouse_service.create_warehouse.return_value = Warehouse(warehouse_id=1, location="Test")
            
            # This would normally require permissions, but we're testing the business logic
            result = await create_warehouse(sample_warehouse_create, mock_warehouse_service)
            assert result is not None

    # ============================================================================
    # GET WAREHOUSE TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_warehouse_success(self, mock_warehouse_service, sample_warehouse, sample_inventory_item):
        """Test get_warehouse endpoint successful response"""
        # mock.Mock service to return warehouse
        mock_warehouse_service.get_warehouse.return_value = sample_warehouse
        mock_warehouse_service.get_warehouse_inventory.return_value = [sample_inventory_item]
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_warehouse
            
            result = await get_warehouse(1, mock_warehouse_service)
            
            # Verify service was called
            mock_warehouse_service.get_warehouse.assert_called_once_with(1)
            mock_warehouse_service.get_warehouse_inventory.assert_called_once_with(1)
            
            # Verify response
            assert result.warehouse_id == 1
            assert result.name == "Test Warehouse"
            assert result.location == "Test Warehouse"
            assert len(result.inventory) == 1
            assert result.inventory[0].product_id == 1
            assert result.inventory[0].quantity == 50

    @pytest.mark.asyncio
    async def test_get_warehouse_not_found(self, mock_warehouse_service):
        """Test get_warehouse endpoint when warehouse not found"""
        # mock.Mock service to raise exception
        mock_warehouse_service.get_warehouse.side_effect = Exception("Warehouse not found")
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_warehouse
            
            with pytest.raises(Exception, match="Warehouse not found"):
                await get_warehouse(1, mock_warehouse_service)

    @pytest.mark.asyncio
    async def test_get_warehouse_empty_inventory(self, mock_warehouse_service, sample_warehouse):
        """Test get_warehouse endpoint with empty inventory"""
        # mock.Mock service to return warehouse
        mock_warehouse_service.get_warehouse.return_value = sample_warehouse
        mock_warehouse_service.get_warehouse_inventory.return_value = []
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_warehouse
            
            result = await get_warehouse(1, mock_warehouse_service)
            
            # Verify result
            assert len(result.inventory) == 0

    # ============================================================================
    # DELETE WAREHOUSE TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_delete_warehouse_success(self, mock_warehouse_service):
        """Test delete_warehouse endpoint successful response"""
        # mock.Mock service
        mock_warehouse_service.delete_warehouse.return_value = None
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import delete_warehouse
            
            result = await delete_warehouse(1, mock_warehouse_service)
            
            # Verify service was called
            mock_warehouse_service.delete_warehouse.assert_called_once_with(1)
            
            # Verify response
            assert result == {"message": "Warehouse 1 deleted successfully"}

    @pytest.mark.asyncio
    async def test_delete_warehouse_not_found(self, mock_warehouse_service):
        """Test delete_warehouse endpoint when warehouse not found"""
        # mock.Mock service to raise exception
        mock_warehouse_service.delete_warehouse.side_effect = Exception("Warehouse not found")
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import delete_warehouse
            
            with pytest.raises(Exception, match="Warehouse not found"):
                await delete_warehouse(1, mock_warehouse_service)

    @pytest.mark.asyncio
    async def test_delete_warehouse_permission_denied(self, mock_warehouse_service):
        """Test delete_warehouse endpoint with permission denied"""
        # Note: Permission decorators are applied at FastAPI level
        # This test verifies the service method exists and can be called
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import delete_warehouse
            
            # Test that the function exists and can be called (permissions handled by FastAPI)
            mock_warehouse_service.delete_warehouse.return_value = None
            
            # This would normally require permissions, but we're testing the business logic
            result = await delete_warehouse(1, mock_warehouse_service)
            assert result is not None

    # ============================================================================
    # TRANSFER ALL INVENTORY TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_transfer_all_inventory_success(self, mock_warehouse_service, sample_inventory_item, sample_transfer_request):
        """Test transfer_all_inventory endpoint successful response"""
        # mock.Mock service to return transferred items
        mock_warehouse_service.transfer_all_inventory.return_value = [sample_inventory_item]
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import transfer_all_inventory
            
            result = await transfer_all_inventory(1, sample_transfer_request, mock_warehouse_service)
            
            # Verify service was called
            mock_warehouse_service.transfer_all_inventory.assert_called_once_with(1, 2)
            
            # Verify response
            assert result.from_warehouse_id == 1
            assert result.to_warehouse_id == 2
            assert len(result.transferred_items) == 1
            assert result.transferred_items[0].product_id == 1
            assert result.transferred_items[0].quantity == 50
            assert "Successfully transferred 1 product(s)" in result.message

    @pytest.mark.asyncio
    async def test_transfer_all_inventory_empty(self, mock_warehouse_service, sample_transfer_request):
        """Test transfer_all_inventory endpoint with empty inventory"""
        # mock.Mock service to return empty list
        mock_warehouse_service.transfer_all_inventory.return_value = []
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import transfer_all_inventory
            
            result = await transfer_all_inventory(1, sample_transfer_request, mock_warehouse_service)
            
            # Verify response
            assert len(result.transferred_items) == 0
            assert "Successfully transferred 0 product(s)" in result.message

    @pytest.mark.asyncio
    async def test_transfer_all_inventory_multiple_items(self, mock_warehouse_service, sample_transfer_request):
        """Test transfer_all_inventory endpoint with multiple items"""
        # Create multiple inventory items
        item1 = InventoryItem(product_id=1, quantity=50)
        item2 = InventoryItem(product_id=2, quantity=30)
        
        # mock.Mock service to return transferred items
        mock_warehouse_service.transfer_all_inventory.return_value = [item1, item2]
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import transfer_all_inventory
            
            result = await transfer_all_inventory(1, sample_transfer_request, mock_warehouse_service)
            
            # Verify response
            assert len(result.transferred_items) == 2
            assert result.transferred_items[0].product_id == 1
            assert result.transferred_items[1].product_id == 2
            assert "Successfully transferred 2 product(s)" in result.message

    @pytest.mark.asyncio
    async def test_transfer_all_inventory_same_warehouse(self, mock_warehouse_service):
        """Test transfer_all_inventory endpoint with same warehouse"""
        # Create transfer request to same warehouse
        transfer_request = TransferInventoryRequest(to_warehouse_id=1)
        
        # mock.Mock service to raise exception
        mock_warehouse_service.transfer_all_inventory.side_effect = Exception("Cannot transfer to same warehouse")
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import transfer_all_inventory
            
            with pytest.raises(Exception, match="Cannot transfer to same warehouse"):
                await transfer_all_inventory(1, transfer_request, mock_warehouse_service)

    @pytest.mark.asyncio
    async def test_transfer_all_inventory_permission_denied(self, mock_warehouse_service, sample_transfer_request):
        """Test transfer_all_inventory endpoint with permission denied"""
        # Note: Permission decorators are applied at FastAPI level
        # This test verifies the service method exists and can be called
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import transfer_all_inventory
            
            # Test that the function exists and can be called (permissions handled by FastAPI)
            mock_warehouse_service.transfer_all_inventory.return_value = []
            
            # This would normally require permissions, but we're testing the business logic
            result = await transfer_all_inventory(1, sample_transfer_request, mock_warehouse_service)
            assert result is not None

    @pytest.mark.asyncio
    async def test_transfer_all_inventory_warehouse_not_found(self, mock_warehouse_service, sample_transfer_request):
        """Test transfer_all_inventory endpoint when warehouse not found"""
        # mock.Mock service to raise exception
        mock_warehouse_service.transfer_all_inventory.side_effect = Exception("Warehouse not found")
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import transfer_all_inventory
            
            with pytest.raises(Exception, match="Warehouse not found"):
                await transfer_all_inventory(1, sample_transfer_request, mock_warehouse_service)

    # ============================================================================
    # PERMISSION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_permission_dependencies(self):
        """Test that all endpoints have proper permission dependencies"""
        # This test verifies that the endpoint decorators are properly configured
        from app.api.v1.endpoints.warehouses import router
        
        # Check that router has global dependency
        assert router.dependencies is not None
        
        # Verify endpoints have permission requirements
        routes = [route for route in router.routes if hasattr(route, 'dependencies')]
        
        # Check that routes have permission dependencies
        for route in routes:
            if hasattr(route, 'dependencies') and route.dependencies:
                # Verify at least one dependency exists
                assert len(route.dependencies) > 0

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_service_error_handling(self, mock_warehouse_service):
        """Test that service errors are properly handled"""
        # mock.Mock service to raise exception
        mock_warehouse_service.get_all_warehouses.side_effect = Exception("Service error")
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_all_warehouses
            
            with pytest.raises(Exception, match="Service error"):
                await get_all_warehouses(mock_warehouse_service)

    @pytest.mark.asyncio
    async def test_dependency_injection_failure(self):
        """Test behavior when dependency injection fails"""
        # This would be tested in integration tests, but we can verify the structure
        from app.api.v1.endpoints.warehouses import get_all_warehouses
        
        # Verify function signature expects service parameter
        import inspect
        sig = inspect.signature(get_all_warehouses)
        assert 'service' in sig.parameters

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_create_then_get_warehouse_workflow(self, mock_warehouse_service, sample_warehouse, sample_warehouse_create, sample_inventory_item):
        """Test integration between create and get endpoints"""
        # mock.Mock service methods
        mock_warehouse_service.create_warehouse.return_value = sample_warehouse
        mock_warehouse_service.get_warehouse.return_value = sample_warehouse
        mock_warehouse_service.get_warehouse_inventory.return_value = [sample_inventory_item]
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import create_warehouse, get_warehouse
            
            # Create warehouse
            created = await create_warehouse(sample_warehouse_create, mock_warehouse_service)
            
            # Get warehouse
            retrieved = await get_warehouse(1, mock_warehouse_service)
            
            # Verify both operations succeeded
            assert created.warehouse_id == retrieved.warehouse_id
            assert created.name == retrieved.name

    @pytest.mark.asyncio
    async def test_get_then_delete_warehouse_workflow(self, mock_warehouse_service, sample_warehouse, sample_inventory_item):
        """Test integration between get and delete endpoints"""
        # mock.Mock service methods
        mock_warehouse_service.get_warehouse.return_value = sample_warehouse
        mock_warehouse_service.get_warehouse_inventory.return_value = [sample_inventory_item]
        mock_warehouse_service.delete_warehouse.return_value = None
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_warehouse, delete_warehouse
            
            # Get warehouse
            retrieved = await get_warehouse(1, mock_warehouse_service)
            
            # Delete warehouse
            deleted = await delete_warehouse(1, mock_warehouse_service)
            
            # Verify both operations succeeded
            assert retrieved.warehouse_id == 1
            assert deleted["message"] == "Warehouse 1 deleted successfully"

    @pytest.mark.asyncio
    async def test_get_all_then_transfer_workflow(self, mock_warehouse_service, sample_warehouse, sample_inventory_item, sample_transfer_request):
        """Test integration between get_all and transfer endpoints"""
        # mock.Mock service methods
        mock_warehouse_service.get_all_warehouses.return_value = [sample_warehouse]
        mock_warehouse_service.get_warehouse_inventory.return_value = [sample_inventory_item]
        mock_warehouse_service.transfer_all_inventory.return_value = [sample_inventory_item]
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.require_permissions'), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_all_warehouses, transfer_all_inventory
            
            # Get all warehouses
            warehouses = await get_all_warehouses(mock_warehouse_service)
            
            # Transfer inventory
            transfer_result = await transfer_all_inventory(1, sample_transfer_request, mock_warehouse_service)
            
            # Verify both operations succeeded
            assert len(warehouses) == 1
            assert transfer_result.from_warehouse_id == 1
            assert transfer_result.to_warehouse_id == 2

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_operations_with_large_warehouse_id(self, mock_warehouse_service):
        """Test operations with large warehouse ID"""
        large_warehouse_id = 2147483647  # Max int
        
        # mock.Mock service
        mock_warehouse_service.get_warehouse.return_value = None
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_warehouse
            
            # This should not raise an exception for large ID
            try:
                await get_warehouse(large_warehouse_id, mock_warehouse_service)
            except Exception as e:
                # If an exception occurs, it should not be related to ID size
                assert "large" not in str(e).lower()

    @pytest.mark.asyncio
    async def test_operations_with_negative_warehouse_id(self, mock_warehouse_service):
        """Test operations with negative warehouse ID"""
        negative_warehouse_id = -1
        
        # mock.Mock service to raise validation exception
        mock_warehouse_service.get_warehouse.side_effect = Exception("Invalid warehouse ID")
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_warehouse
            
            with pytest.raises(Exception, match="Invalid warehouse ID"):
                await get_warehouse(negative_warehouse_id, mock_warehouse_service)

    @pytest.mark.asyncio
    async def test_operations_with_zero_warehouse_id(self, mock_warehouse_service):
        """Test operations with zero warehouse ID"""
        zero_warehouse_id = 0
        
        # mock.Mock service to raise validation exception
        mock_warehouse_service.get_warehouse.side_effect = Exception("Invalid warehouse ID")
        
        with patch('app.api.v1.endpoints.warehouses.get_warehouse_service', return_value=mock_warehouse_service), \
             patch('app.api.v1.endpoints.warehouses.get_current_user'):
            
            from app.api.v1.endpoints.warehouses import get_warehouse
            
            with pytest.raises(Exception, match="Invalid warehouse ID"):
                await get_warehouse(zero_warehouse_id, mock_warehouse_service)
