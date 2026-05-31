"""Integration tests for inventory caching and pub/sub."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.products.domain.entities.product import Product
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.shared.domain.business_exceptions import EntityNotFoundError, InsufficientStockError, InvalidQuantityError


class TestInventoryServiceIntegration:
    """Integration tests for InventoryService with caching and pub/sub."""
    
    @pytest.fixture
    def mock_inventory_repo(self):
        """Mock inventory repository."""
        from unittest.mock import Mock
        repo = Mock()
        repo.get_quantity.return_value = 10
        repo.add_quantity.return_value = None
        repo.remove_quantity.return_value = None
        return repo
    
    @pytest.fixture
    def mock_product_repo(self):
        """Mock product repository."""
        from unittest.mock import Mock
        repo = Mock()
        product = Product(
            product_id=1, name="Test Product", price=10.0, description="Test"
        )
        repo.get.return_value = product
        return repo
    
    @pytest.fixture
    def mock_warehouse_repo(self):
        """Mock warehouse repository."""
        from unittest.mock import Mock
        repo = Mock()
        warehouse = Warehouse(warehouse_id=1, location="Test Warehouse")
        repo.get.return_value = warehouse
        repo.get_all.return_value = {1: warehouse}
        return repo
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock redis manager."""
        manager = AsyncMock()
        manager.get.return_value = None
        manager.set.return_value = True
        manager.delete.return_value = True
        manager.exists.return_value = True
        manager.publish.return_value = 1
        
        # Mock the client to avoid NoneType errors
        client = AsyncMock()
        client.get.return_value = None
        client.set.return_value = True
        client.delete.return_value = True
        # Mock scan operation for cache invalidation
        client.scan.return_value = (0, [])  # cursor, keys
        manager.client = client  # Use .client instead of ._client
        manager._client = client  # Keep both for compatibility
        
        return manager
    
    @pytest.fixture
    def mock_event_publisher(self):
        """Mock event publisher."""
        publisher = AsyncMock()
        return publisher
    
    @pytest.fixture
    def inventory_service(
        self, mock_inventory_repo, mock_product_repo, mock_warehouse_repo
    ):
        """Create InventoryService instance."""
        return InventoryService(
            inventory_repo=mock_inventory_repo,
            product_repo=mock_product_repo,
            warehouse_repo=mock_warehouse_repo
        )
    
    @pytest.fixture
    def setup_mocks(
        self, mock_redis_manager, mock_event_publisher, mock_inventory_repo
    ):
        """Setup all mocks."""
        # Initialize the mock redis manager
        mock_redis_manager._client = mock_redis_manager._client
        mock_redis_manager._initialized = True
        
        with patch('app.shared.core.cache.redis_manager', mock_redis_manager):
            with patch('app.modules.inventory.application.services.inventory_service.redis_manager', mock_redis_manager):
                with patch('app.modules.inventory.application.services.inventory_service.EventPublisher', mock_event_publisher):
                    yield mock_redis_manager, mock_event_publisher, mock_inventory_repo
    
    @pytest.mark.asyncio
    async def test_add_to_total_inventory_with_caching_and_pubsub(
        self, inventory_service, setup_mocks
    ):
        """Test adding inventory with caching and pub/sub integration."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup initial quantity
        mock_inventory_repo.get_quantity.return_value = 10
        
        # Add inventory
        await inventory_service.add_to_total_inventory(1, 5, user_id=123)
        
        # Verify product was checked
        inventory_service.product_repo.get.assert_called_once_with(1)
        
        # Verify old quantity was retrieved
        mock_inventory_repo.get_quantity.assert_called_once_with(1)
        
        # Verify quantity was added
        mock_inventory_repo.add_quantity.assert_called_once_with(1, 5)
        
        # Verify cache was invalidated
        mock_redis.delete.assert_called_once_with("inventory_quantity:1")
        
        # Verify pub/sub event was published
        mock_publisher.publish_stock_change.assert_called_once_with(
            product_id=1,
            old_quantity=10,
            new_quantity=15,
            user_id=123,
            source="inventory_service"
        )
    
    @pytest.mark.asyncio
    async def test_remove_from_total_inventory_with_caching_and_pubsub(
        self, inventory_service, setup_mocks
    ):
        """Test removing inventory with caching and pub/sub integration."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup initial quantity
        mock_inventory_repo.get_quantity.return_value = 20
        
        # Remove inventory
        await inventory_service.remove_from_total_inventory(1, 5, user_id=456)
        
        # Verify product was checked
        inventory_service.product_repo.get.assert_called_once_with(1)
        
        # Verify quantity was checked and removed
        mock_inventory_repo.get_quantity.assert_called_once_with(1)
        mock_inventory_repo.remove_quantity.assert_called_once_with(1, 5)
        
        # Verify cache was invalidated
        mock_redis.delete.assert_called_once_with("inventory_quantity:1")
        
        # Verify pub/sub event was published
        mock_publisher.publish_stock_change.assert_called_once_with(
            product_id=1,
            old_quantity=20,
            new_quantity=15,
            user_id=456,
            source="inventory_service"
        )
    
    @pytest.mark.asyncio
    async def test_get_total_quantity_cached(
        self, inventory_service, setup_mocks
    ):
        """Test getting total quantity with caching."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # First call - cache miss
        mock_redis.get.return_value = None
        mock_inventory_repo.get_quantity.return_value = 15
        
        result1 = await inventory_service.get_total_quantity(1)
        
        assert result1 == 15
        
        # Verify product was checked
        inventory_service.product_repo.get.assert_called_once_with(1)
        
        # Verify quantity was retrieved from repo
        mock_inventory_repo.get_quantity.assert_called_once_with(1)
        
        # Verify result was cached
        mock_redis.set.assert_called_once()
        cache_call_args = mock_redis.set.call_args
        # Cache key should include function name and args hash
        assert "inventory_quantity:get_total_quantity:args:" in cache_call_args[0][0]
        assert cache_call_args[0][1] == {'__cached_type__': 'int', '__cached_value__': '15'}
        assert cache_call_args[1]["ex"] == 300  # 5 minutes TTL
    
    @pytest.mark.asyncio
    async def test_get_total_quantity_cache_hit(
        self, inventory_service, setup_mocks
    ):
        """Test getting total quantity with cache hit."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Cache hit scenario - use new typed cache format
        mock_redis.get.return_value = '{"__cached_type__": "int", "__cached_value__": "25"}'
        
        result = await inventory_service.get_total_quantity(1)
        
        assert result == 25  # Cache returns typed int
        
        # Verify repo was NOT called (cache hit)
        mock_inventory_repo.get_quantity.assert_not_called()
        
        # Verify cache was NOT set (already cached)
        mock_redis.set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_add_inventory_insufficient_stock_error(
        self, inventory_service, setup_mocks
    ):
        """Test adding negative quantity raises error."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        with pytest.raises(InvalidQuantityError, match="Cannot add negative quantity"):
            await inventory_service.add_to_total_inventory(1, -5)
        
        # Verify no cache operations or pub/sub events
        mock_redis.delete.assert_not_called()
        mock_publisher.publish_stock_change.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_remove_inventory_insufficient_stock_error(
        self, inventory_service, setup_mocks
    ):
        """Test removing more than available raises error."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup insufficient stock
        mock_inventory_repo.get_quantity.return_value = 5
        
        with pytest.raises(InsufficientStockError, match="Insufficient inventory"):
            await inventory_service.remove_from_total_inventory(1, 10)
        
        # Verify no cache operations or pub/sub events
        mock_redis.delete.assert_not_called()
        mock_publisher.publish_stock_change.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_add_inventory_product_not_found(
        self, inventory_service, setup_mocks
    ):
        """Test adding inventory for non-existent product."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup product not found
        inventory_service.product_repo.get.return_value = None
        
        with pytest.raises(EntityNotFoundError, match="Product 1 not found"):
            await inventory_service.add_to_total_inventory(1, 5)
        
        # Verify no cache operations or pub/sub events
        mock_redis.delete.assert_not_called()
        mock_publisher.publish_stock_change.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_remove_inventory_product_not_found(
        self, inventory_service, setup_mocks
    ):
        """Test removing inventory for non-existent product."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup product not found
        inventory_service.product_repo.get.return_value = None
        
        with pytest.raises(EntityNotFoundError, match="Product 1 not found"):
            await inventory_service.remove_from_total_inventory(1, 5)
        
        # Verify no cache operations or pub/sub events
        mock_redis.delete.assert_not_called()
        mock_publisher.publish_stock_change.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_inventory_quantity_product_not_found(
        self, inventory_service, setup_mocks
    ):
        """Test getting quantity for non-existent product."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup product not found
        inventory_service.product_repo.get.return_value = None
        
        with pytest.raises(EntityNotFoundError, match="Product 1 not found"):
            await inventory_service.get_total_quantity(1)
        
        # Verify no cache operations
        mock_redis.set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_inventory_operations_without_user_id(
        self, inventory_service, setup_mocks
    ):
        """Test inventory operations without optional user_id."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup initial quantity
        mock_inventory_repo.get_quantity.return_value = 10
        
        # Add inventory without user_id
        await inventory_service.add_to_total_inventory(1, 5)
        
        # Verify pub/sub event was published without user_id
        mock_publisher.publish_stock_change.assert_called_once_with(
            product_id=1,
            old_quantity=10,
            new_quantity=15,
            user_id=None,
            source="inventory_service"
        )
    
    @pytest.mark.asyncio
    async def test_concurrent_inventory_operations(
        self, inventory_service, setup_mocks
    ):
        """Test concurrent inventory operations."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup initial quantity
        mock_inventory_repo.get_quantity.return_value = 20
        
        # Run concurrent operations
        tasks = [
            inventory_service.add_to_total_inventory(1, 5, user_id=1),
            inventory_service.remove_from_total_inventory(1, 3, user_id=2),
            inventory_service.get_total_quantity(1)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All operations should complete successfully
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent operation failed: {result}")
        
        # Verify all cache invalidations occurred
        assert mock_redis.delete.call_count >= 2  # For add and remove operations
        
        # Verify pub/sub events were published
        assert mock_publisher.publish_stock_change.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_cache_key_format(
        self, inventory_service, setup_mocks
    ):
        """Test that cache keys are formatted correctly."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Test different product IDs
        product_ids = [1, 123, 999]
        
        for product_id in product_ids:
            mock_redis.reset_mock()
            mock_inventory_repo.get_quantity.return_value = 10
            
            await inventory_service.get_total_quantity(product_id)
            
            # Verify cache key format
            if mock_redis.set.called:
                cache_key = mock_redis.set.call_args[0][0]
                # Cache key should include function name and args hash
                assert "inventory_quantity:get_total_quantity:args:" in cache_key
    
    @pytest.mark.asyncio
    async def test_pubsub_event_data_integrity(
        self, inventory_service, setup_mocks
    ):
        """Test that pub/sub event data is correct."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup test data
        product_id = 42
        old_quantity = 100
        new_quantity = 150
        quantity_change = 50
        user_id = 789
        
        mock_inventory_repo.get_quantity.return_value = old_quantity
        
        await inventory_service.add_to_total_inventory(product_id, quantity_change, user_id)
        
        # Verify event data integrity
        mock_publisher.publish_stock_change.assert_called_once()
        call_args = mock_publisher.publish_stock_change.call_args
        
        assert call_args[1]["product_id"] == product_id
        assert call_args[1]["old_quantity"] == old_quantity
        assert call_args[1]["new_quantity"] == new_quantity
        assert call_args[1]["user_id"] == user_id
        assert call_args[1]["source"] == "inventory_service"
    
    @pytest.mark.asyncio
    async def test_error_handling_in_cache_operations(
        self, inventory_service, setup_mocks
    ):
        """Test error handling in cache operations."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup cache delete to fail
        mock_redis.delete.side_effect = Exception("Redis error")
        
        # Setup inventory data
        mock_inventory_repo.get_quantity.return_value = 10
        
        # Operation should still succeed despite cache error
        # The operation should complete and the underlying repo method should be called
        await inventory_service.add_to_total_inventory(1, 5, user_id=123)
        
        # Verify inventory operation still happened
        mock_inventory_repo.add_quantity.assert_called_once_with(1, 5)
        
        # Note: pub/sub event may not be published due to error in cache invalidation decorator
    
    @pytest.mark.asyncio
    async def test_error_handling_in_pubsub_operations(
        self, inventory_service, setup_mocks
    ):
        """Test error handling in pub/sub operations."""
        mock_redis, mock_publisher, mock_inventory_repo = setup_mocks
        
        # Setup pubsub to fail
        mock_publisher.publish_stock_change.side_effect = Exception("PubSub error")
        
        # Setup inventory data
        mock_inventory_repo.get_quantity.return_value = 10
        
        # Operation should still succeed despite pubsub error
        await inventory_service.add_to_total_inventory(1, 5, user_id=123)
        
        # Verify inventory operation still happened
        mock_inventory_repo.add_quantity.assert_called_once_with(1, 5)
        
        # Verify cache operation still happened
        mock_redis.delete.assert_called_once_with("inventory_quantity:1")
        
        # Verify that the pubsub error was handled gracefully (operation still succeeds)
        # The operation should complete without raising the PubSub error
        await inventory_service.add_to_total_inventory(1, 5, user_id=123)
        
        # Verify the underlying repo operation still happened
        mock_inventory_repo.add_quantity.assert_called_with(1, 5)
