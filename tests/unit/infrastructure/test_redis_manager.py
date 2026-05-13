"""Tests for Redis connection manager."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import redis.asyncio as redis

from app.shared.core.redis import RedisManager
from app.shared.core.settings import settings


class TestRedisManager:
    """Test cases for RedisManager."""
    
    @pytest.fixture
    def redis_manager(self):
        """Create RedisManager instance for testing."""
        # Reset singleton for testing
        original_instance = RedisManager._instance
        original_pool = RedisManager._pool
        original_client = RedisManager._client
        
        RedisManager._instance = None
        RedisManager._pool = None
        RedisManager._client = None
        manager = RedisManager()
        
        yield manager
        
        # Restore original state
        RedisManager._instance = original_instance
        RedisManager._pool = original_pool
        RedisManager._client = original_client
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        client = AsyncMock(spec=redis.Redis)
        client.ping = AsyncMock(return_value=True)
        client.get = AsyncMock(return_value=None)
        client.set = AsyncMock(return_value=True)
        client.delete = AsyncMock(return_value=1)
        client.exists = AsyncMock(return_value=1)
        client.expire = AsyncMock(return_value=1)
        client.incrby = AsyncMock(return_value=5)
        client.publish = AsyncMock(return_value=2)
        client.close = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_connection_pool(self, mock_redis_client):
        """Mock connection pool."""
        pool = AsyncMock(spec=redis.ConnectionPool)
        pool.from_url = AsyncMock(return_value=pool)
        pool.disconnect = AsyncMock()
        return pool
    
    @pytest.mark.asyncio
    async def test_singleton_pattern(self, redis_manager):
        """Test that RedisManager follows singleton pattern."""
        manager1 = RedisManager()
        manager2 = RedisManager()
        assert manager1 is manager2
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, redis_manager, mock_connection_pool, mock_redis_client):
        """Test successful Redis initialization."""
        with patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_connection_pool):
            with patch('redis.asyncio.Redis', return_value=mock_redis_client):
                await redis_manager.initialize()
                
                assert redis_manager._client is not None
                assert redis_manager._pool is not None
                mock_redis_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_with_decode_responses(self, redis_manager, mock_connection_pool, mock_redis_client):
        """Test that decode_responses=True is added to URL if not present."""
        original_url = settings.redis_url
        try:
            settings.redis_url = "redis://localhost:6379/0"
            
            with patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_connection_pool) as mock_from_url:
                with patch('redis.asyncio.Redis', return_value=mock_redis_client):
                    await redis_manager.initialize()
                    
                    # Check that decode_responses=True was added
                    called_url = mock_from_url.call_args[0][0]
                    assert "decode_responses=True" in called_url
        finally:
            settings.redis_url = original_url
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self, redis_manager):
        """Test Redis initialization failure."""
        with patch('redis.asyncio.ConnectionPool.from_url', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception):
                await redis_manager.initialize()
    
    @pytest.mark.asyncio
    async def test_get_success(self, redis_manager, mock_redis_client):
        """Test successful get operation."""
        redis_manager._client = mock_redis_client
        mock_redis_client.get.return_value = "test_value"
        
        result = await redis_manager.get("test_key")
        assert result == "test_value"
        mock_redis_client.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_get_not_found(self, redis_manager, mock_redis_client):
        """Test get operation when key doesn't exist."""
        redis_manager._client = mock_redis_client
        mock_redis_client.get.return_value = None
        
        result = await redis_manager.get("nonexistent_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_success(self, redis_manager, mock_redis_client):
        """Test successful set operation."""
        redis_manager._client = mock_redis_client
        mock_redis_client.set.return_value = True
        
        result = await redis_manager.set("test_key", "test_value", ex=300)
        assert result is True
        mock_redis_client.set.assert_called_once_with("test_key", "test_value", ex=300)
    
    @pytest.mark.asyncio
    async def test_set_with_dict(self, redis_manager, mock_redis_client):
        """Test set operation with dictionary value."""
        redis_manager._client = mock_redis_client
        mock_redis_client.set.return_value = True
        
        test_dict = {"key": "value", "number": 42}
        result = await redis_manager.set("test_key", test_dict)
        
        assert result is True
        # Check that dict was converted to JSON string
        call_args = mock_redis_client.set.call_args
        assert isinstance(call_args[0][1], str)
    
    @pytest.mark.asyncio
    async def test_delete_success(self, redis_manager, mock_redis_client):
        """Test successful delete operation."""
        redis_manager._client = mock_redis_client
        mock_redis_client.delete.return_value = 1
        
        result = await redis_manager.delete("test_key")
        assert result is True
        mock_redis_client.delete.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_delete_not_found(self, redis_manager, mock_redis_client):
        """Test delete operation when key doesn't exist."""
        redis_manager._client = mock_redis_client
        mock_redis_client.delete.return_value = 0
        
        result = await redis_manager.delete("nonexistent_key")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_exists_true(self, redis_manager, mock_redis_client):
        """Test exists operation when key exists."""
        redis_manager._client = mock_redis_client
        mock_redis_client.exists.return_value = 1
        
        result = await redis_manager.exists("test_key")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_exists_false(self, redis_manager, mock_redis_client):
        """Test exists operation when key doesn't exist."""
        redis_manager._client = mock_redis_client
        mock_redis_client.exists.return_value = 0
        
        result = await redis_manager.exists("test_key")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_success(self, redis_manager, mock_redis_client):
        """Test successful publish operation."""
        redis_manager._client = mock_redis_client
        mock_redis_client.publish.return_value = 2
        
        result = await redis_manager.publish("test_channel", "test_message")
        assert result == 2
        mock_redis_client.publish.assert_called_once_with("test_channel", "test_message")
    
    @pytest.mark.asyncio
    async def test_publish_with_dict(self, redis_manager, mock_redis_client):
        """Test publish operation with dictionary message."""
        redis_manager._client = mock_redis_client
        mock_redis_client.publish.return_value = 1
        
        test_dict = {"event": "test", "data": {"value": 42}}
        result = await redis_manager.publish("test_channel", test_dict)
        
        assert result == 1
        # Check that dict was converted to JSON string
        call_args = mock_redis_client.publish.call_args
        assert isinstance(call_args[0][1], str)
    
    @pytest.mark.asyncio
    async def test_increment_success(self, redis_manager, mock_redis_client):
        """Test successful increment operation."""
        redis_manager._client = mock_redis_client
        mock_redis_client.incrby.return_value = 5
        
        result = await redis_manager.increment("counter", 3)
        assert result == 5
        mock_redis_client.incrby.assert_called_once_with("counter", 3)
    
    @pytest.mark.asyncio
    async def test_expire_success(self, redis_manager, mock_redis_client):
        """Test successful expire operation."""
        redis_manager._client = mock_redis_client
        mock_redis_client.expire.return_value = 1
        
        result = await redis_manager.expire("test_key", 300)
        assert result is True
        mock_redis_client.expire.assert_called_once_with("test_key", 300)
    
    @pytest.mark.asyncio
    async def test_close(self, redis_manager, mock_redis_client, mock_connection_pool):
        """Test closing Redis connections."""
        redis_manager._client = mock_redis_client
        redis_manager._pool = mock_connection_pool
        
        await redis_manager.close()
        
        mock_redis_client.close.assert_called_once()
        mock_connection_pool.disconnect.assert_called_once()
        assert redis_manager._client is None
        assert redis_manager._pool is None
    
    @pytest.mark.asyncio
    async def test_client_property_not_initialized(self, redis_manager):
        """Test that client property raises error when not initialized."""
        with pytest.raises(RuntimeError, match="Redis manager not initialized"):
            _ = redis_manager.client
    
    @pytest.mark.asyncio
    async def test_client_property_initialized(self, redis_manager, mock_redis_client):
        """Test that client property returns client when initialized."""
        redis_manager._client = mock_redis_client
        
        client = redis_manager.client
        assert client is mock_redis_client
    
    @pytest.mark.asyncio
    async def test_double_initialize(self, redis_manager, mock_connection_pool, mock_redis_client):
        """Test that initialize doesn't create multiple connections."""
        with patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_connection_pool):
            with patch('redis.asyncio.Redis', return_value=mock_redis_client):
                await redis_manager.initialize()
                first_client = redis_manager._client
                
                # Second initialize should not create new client
                await redis_manager.initialize()
                assert redis_manager._client is first_client
