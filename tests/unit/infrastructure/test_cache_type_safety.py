"""Tests for cache type safety and domain object reconstruction."""

import pytest
from unittest.mock import AsyncMock, patch

from app.shared.core.cache import cached, register_serializer, get_serializer
from app.modules.products.domain.entities.product import Product
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.modules.inventory.domain.entities.inventory import InventoryItem


class TestCacheTypeSafety:
    """Test cases for cache type safety."""

    @pytest.fixture
    def mock_redis_manager(self):
        """Mock redis manager."""
        mock_manager = AsyncMock()
        mock_manager.get.return_value = None
        mock_manager.set.return_value = True
        mock_manager.delete.return_value = True
        mock_manager.exists.return_value = True
        mock_manager.expire.return_value = True
        return mock_manager

    @pytest.fixture
    def setup_redis_mock(self, mock_redis_manager):
        """Setup redis manager mock."""
        with patch('app.shared.core.cache.redis_manager', mock_redis_manager):
            yield mock_redis_manager

    @pytest.mark.asyncio
    async def test_product_cache_returns_correct_type(self, setup_redis_mock):
        """Test that cached Product objects return as Product instances."""
        mock_manager = setup_redis_mock
        
        # Create a product
        product = Product(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )
        
        # Mock cache behavior: first call misses, second call hits
        import json
        cache_miss_return = None
        cache_hit_return = json.dumps({
            '__cached_type__': 'Product',
            '__cached_value__': {
                'product_id': 1,
                'name': 'Test Product',
                'description': 'Test Description',
                'price': 99.99
            }
        })
        
        call_count = 0
        def mock_get(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return cache_miss_return
            else:
                return cache_hit_return
        
        mock_manager.get.side_effect = mock_get
        
        @cached(prefix="test_product", ttl=3600)
        async def get_product_cached(product_id: int) -> Product:
            return product
        
        # First call - cache miss
        result1 = await get_product_cached(1)
        assert isinstance(result1, Product)
        assert result1.product_id == 1
        assert result1.name == "Test Product"
        
        # Second call - cache hit
        result2 = await get_product_cached(1)
        assert isinstance(result2, Product)
        assert result2.product_id == 1
        assert result2.name == "Test Product"
        assert result2.description == "Test Description"
        assert result2.price == 99.99
        
        # Verify cache was used
        assert mock_manager.get.call_count == 2
        assert mock_manager.set.call_count == 1

    @pytest.mark.asyncio
    async def test_warehouse_cache_returns_correct_type(self, setup_redis_mock):
        """Test that cached Warehouse objects return as Warehouse instances."""
        mock_manager = setup_redis_mock
        
        # Create a warehouse with inventory
        inventory = [InventoryItem(product_id=1, quantity=10)]
        warehouse = Warehouse(
            warehouse_id=1,
            location="Test Location",
            inventory=inventory
        )
        
        # Mock cache behavior
        import json
        cache_miss_return = None
        cache_hit_return = json.dumps({
            '__cached_type__': 'Warehouse',
            '__cached_value__': {
                'warehouse_id': 1,
                'location': 'Test Location',
                'inventory': [
                    {
                        'product_id': 1,
                        'quantity': 10
                    }
                ]
            }
        })
        
        call_count = 0
        def mock_get(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return cache_miss_return
            else:
                return cache_hit_return
        
        mock_manager.get.side_effect = mock_get
        
        @cached(prefix="test_warehouse", ttl=1800)
        async def get_warehouse_cached(warehouse_id: int) -> Warehouse:
            return warehouse
        
        # First call - cache miss
        result1 = await get_warehouse_cached(1)
        assert isinstance(result1, Warehouse)
        assert result1.warehouse_id == 1
        assert result1.location == "Test Location"
        assert len(result1.inventory) == 1
        
        # Second call - cache hit
        result2 = await get_warehouse_cached(1)
        assert isinstance(result2, Warehouse)
        assert result2.warehouse_id == 1
        assert result2.location == "Test Location"
        assert len(result2.inventory) == 1
        assert result2.inventory[0].product_id == 1
        assert result2.inventory[0].quantity == 10
        
        # Verify cache was used
        assert mock_manager.get.call_count == 2
        assert mock_manager.set.call_count == 1

    @pytest.mark.asyncio
    async def test_domain_object_without_serializer_not_cached(self, setup_redis_mock):
        """Test that domain objects without serializers are not cached."""
        mock_manager = setup_redis_mock
        
        class UncachedDomainObject:
            def __init__(self, id: int, name: str):
                self.id = id
                self.name = name
        
        obj = UncachedDomainObject(1, "test")
        
        @cached(prefix="test_uncached", ttl=3600)
        async def get_uncached_object(id: int) -> UncachedDomainObject:
            return obj
        
        # Call the function
        result = await get_uncached_object(1)
        assert isinstance(result, UncachedDomainObject)
        assert result.id == 1
        assert result.name == "test"
        
        # Verify it was not cached (no set call)
        mock_manager.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_without_serializer_returns_none(self, setup_redis_mock):
        """Test that un-reconstructable cached types are treated as cache miss."""
        mock_manager = setup_redis_mock
        
        # Mock cache hit for unregistered type
        import json
        cache_hit_return = json.dumps({
            '__cached_type__': 'UnregisteredType',
            '__cached_value__': {'id': 1, 'name': 'test'}
        })
        mock_manager.get.return_value = cache_hit_return
        
        @cached(prefix="test_unregistered", ttl=3600)
        async def get_unregistered_object(id: int):
            return {"id": id, "name": "test"}  # Return simple dict
        
        # Call the function - should treat as cache miss and return fresh result
        result = await get_unregistered_object(1)
        assert result == {"id": 1, "name": "test"}
        mock_manager.set.assert_called_once()

    def test_serializer_registration(self):
        """Test that serializers are properly registered."""
        # Check that Product serializer is registered
        product_serializer = get_serializer('Product')
        assert product_serializer is not None
        assert callable(product_serializer)
        
        # Check that Warehouse serializer is registered
        warehouse_serializer = get_serializer('Warehouse')
        assert warehouse_serializer is not None
        assert callable(warehouse_serializer)
        
        # Test Product reconstruction
        product_data = {
            'product_id': 1,
            'name': 'Test Product',
            'description': 'Test Description',
            'price': 99.99
        }
        product = product_serializer(product_data)
        assert isinstance(product, Product)
        assert product.product_id == 1
        assert product.name == "Test Product"
        
        # Test Warehouse reconstruction
        warehouse_data = {
            'warehouse_id': 1,
            'location': 'Test Location',
            'inventory': [
                {'product_id': 1, 'quantity': 10}
            ]
        }
        warehouse = warehouse_serializer(warehouse_data)
        assert isinstance(warehouse, Warehouse)
        assert warehouse.warehouse_id == 1
        assert warehouse.location == "Test Location"
        assert len(warehouse.inventory) == 1
        assert warehouse.inventory[0].product_id == 1
        assert warehouse.inventory[0].quantity == 10

    @pytest.mark.asyncio
    async def test_primitive_types_work_without_serializers(self, setup_redis_mock):
        """Test that primitive types work without needing serializers."""
        mock_manager = setup_redis_mock
        
        @cached(prefix="test_primitive", ttl=3600)
        async def get_primitive_data() -> dict:
            return {"key": "value", "number": 42}
        
        # Mock cache behavior
        import json
        cache_hit_return = json.dumps({
            '__cached_type__': 'dict',
            '__cached_value__': {"key": "value", "number": 42}
        })
        mock_manager.get.return_value = cache_hit_return
        
        # Call the function
        result = await get_primitive_data()
        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["number"] == 42
        
        # Verify cache was used (cache hit, so no set call)
        mock_manager.get.assert_called_once()
        mock_manager.set.assert_not_called()  # Cache hit, no need to set
