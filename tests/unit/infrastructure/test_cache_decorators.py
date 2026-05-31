"""Tests for cache decorators."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.shared.core.cache import (
    cached, invalidate_cache_pattern, invalidate_cache_key,
    cache_key_builder, CacheHelper
)
from app.shared.core.redis import redis_manager


class TestCacheDecorators:
    """Test cases for cache decorators."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock redis manager."""
        mock_manager = AsyncMock()
        mock_manager.get.return_value = None
        mock_manager.set.return_value = True
        mock_manager.delete.return_value = True
        mock_manager.exists.return_value = False
        return mock_manager
    
    @pytest.fixture
    def setup_redis_mock(self, mock_redis_manager):
        """Setup redis manager mock."""
        with patch('app.shared.core.cache.redis_manager', mock_redis_manager):
            yield mock_redis_manager
    
    @pytest.mark.asyncio
    async def test_cached_decorator_success(self, setup_redis_mock):
        """Test successful caching with decorator."""
        call_count = 0
        
        @cached(prefix="test", ttl=300)
        async def test_function(x, y):
            nonlocal call_count
            call_count += 1
            return f"result_{x}_{y}"
        
        # First call should execute function and cache result
        result1 = await test_function(1, 2)
        assert result1 == "result_1_2"
        assert call_count == 1
        
        # Check that result was cached
        setup_redis_mock.set.assert_called_once()
        cache_key = setup_redis_mock.set.call_args[0][0]
        assert "test" in cache_key
        assert "test_function" in cache_key
        
        # Second call should return cached result
        setup_redis_mock.get.return_value = "result_1_2"
        result2 = await test_function(1, 2)
        assert result2 == "result_1_2"
        assert call_count == 1  # Function not called again
