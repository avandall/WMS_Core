"""Tests for Redis distributed locking."""

import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.shared.core.locking import (
    DistributedLock, LockManager, Semaphore, distributed_lock
)


class TestDistributedLock:
    """Test cases for DistributedLock."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock redis manager."""
        mock_manager = AsyncMock()
        mock_manager.client.set.return_value = True
        mock_manager.delete.return_value = True
        mock_manager.exists.return_value = True
        mock_manager.expire.return_value = True
        mock_manager.client.eval.return_value = 60  # Return TTL value for extend operation
        return mock_manager
    
    @pytest.fixture
    def setup_redis_mock(self, mock_redis_manager):
        """Setup redis manager mock."""
        with patch('app.shared.core.locking.redis_manager', mock_redis_manager):
            yield mock_redis_manager
    
    @pytest.mark.asyncio
    async def test_lock_acquire_success(self, setup_redis_mock):
        """Test successful lock acquisition."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True  # NX EX succeeds
        
        lock = DistributedLock("test_lock", ttl=30)
        result = await lock.acquire()
        
        assert result is True
        assert lock.is_acquired()
        
        # Check Redis SET was called correctly
        mock_manager.client.set.assert_called_once()
        call_args = mock_manager.client.set.call_args
        assert call_args[0][0] == "lock:test_lock"
        assert call_args[0][1] == lock.identifier
        assert call_args[1]["ex"] == 30
        assert call_args[1]["nx"] is True
    
    @pytest.mark.asyncio
    async def test_lock_acquire_failure(self, setup_redis_mock):
        """Test lock acquisition failure."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = False  # NX EX fails
        
        lock = DistributedLock("test_lock", ttl=30, max_retries=3, retry_delay=0.01)
        result = await lock.acquire()
        
        assert result is False
        assert not lock.is_acquired()
        
        # Should have tried multiple times
        assert mock_manager.client.set.call_count == 3
    
    @pytest.mark.asyncio
    async def test_lock_release_success(self, setup_redis_mock):
        """Test successful lock release."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True
        mock_manager.client.eval.return_value = 1  # Lua script succeeds
        
        lock = DistributedLock("test_lock", ttl=30)
        await lock.acquire()
        
        result = await lock.release()
        
        assert result is True
        assert not lock.is_acquired()
        
        # Check Lua script was called
        mock_manager.client.eval.assert_called_once()
        call_args = mock_manager.client.eval.call_args
        assert call_args[0][1] == 1  # KEYS count
        assert call_args[0][2] == "lock:test_lock"  # KEY
        assert call_args[0][3] == lock.identifier  # ARGV
    
    @pytest.mark.asyncio
    async def test_lock_release_not_owner(self, setup_redis_mock):
        """Test lock release when not owner."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True
        mock_manager.client.eval.return_value = 0  # Lua script fails
        
        lock = DistributedLock("test_lock", ttl=30)
        await lock.acquire()
        
        result = await lock.release()
        
        assert result is False
        assert lock.is_acquired()  # Still thinks it owns the lock
    
    @pytest.mark.asyncio
    async def test_lock_release_not_acquired(self, setup_redis_mock):
        """Test releasing lock that wasn't acquired."""
        lock = DistributedLock("test_lock", ttl=30)
        
        result = await lock.release()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_lock_extend_success(self, setup_redis_mock):
        """Test successful lock extension."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True
        mock_manager.client.eval.return_value = 60  # Return TTL value for extend operation
        
        lock = DistributedLock("test_lock", ttl=30)
        await lock.acquire()
        
        result = await lock.extend(60)
        
        assert result is True
        
        # Check Lua script was called
        mock_manager.client.eval.assert_called_once()
        call_args = mock_manager.client.eval.call_args
        assert call_args[0][4] == 60  # New TTL
    
    @pytest.mark.asyncio
    async def test_lock_extend_not_owner(self, setup_redis_mock):
        """Test lock extension when not owner."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True
        mock_manager.client.eval.return_value = 0  # Lua script fails
        
        lock = DistributedLock("test_lock", ttl=30)
        await lock.acquire()
        
        result = await lock.extend(60)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_lock_extend_not_acquired(self, setup_redis_mock):
        """Test extending lock that wasn't acquired."""
        lock = DistributedLock("test_lock", ttl=30)
        
        result = await lock.extend(60)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_lock_context_manager_success(self, setup_redis_mock):
        """Test lock as context manager - success."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True
        mock_manager.client.eval.return_value = 1
        
        lock = DistributedLock("test_lock", ttl=30)
        
        async with lock:
            assert lock.is_acquired()
        
        # Lock should be released after context
        assert not lock.is_acquired()
        mock_manager.client.eval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lock_context_manager_failure(self, setup_redis_mock):
        """Test lock as context manager - acquisition failure."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = False
        
        lock = DistributedLock("test_lock", ttl=30, max_retries=1)
        
        with pytest.raises(RuntimeError, match="Failed to acquire lock"):
            async with lock:
                pass  # Should not reach here
    
    @pytest.mark.asyncio
    async def test_lock_identifier_unique(self, setup_redis_mock):
        """Test that lock identifiers are unique."""
        lock1 = DistributedLock("test_lock", ttl=30)
        lock2 = DistributedLock("test_lock", ttl=30)
        
        assert lock1.identifier != lock2.identifier
        assert str(lock1.identifier) != str(lock2.identifier)


class TestLockManager:
    """Test cases for LockManager."""
    
    @pytest.fixture
    def mock_distributed_lock(self):
        """Mock DistributedLock."""
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=mock_lock)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        return mock_lock
    
    @pytest.fixture
    def setup_lock_mock(self, mock_distributed_lock):
        """Setup lock mock."""
        with patch('app.shared.core.locking.DistributedLock') as mock_class:
            mock_class.return_value = mock_distributed_lock
            yield mock_class
    
    @pytest.mark.asyncio
    async def test_lock_inventory_update(self, setup_lock_mock):
        """Test inventory update lock."""
        mock_lock = setup_lock_mock
        
        async with LockManager.lock_inventory_update(1, warehouse_id=2) as lock:
            pass
        
        # Check lock was created with correct key
        mock_lock.assert_called_once()
        call_args = mock_lock.call_args
        assert call_args[0][0] == "inventory_update:1:2"
        assert call_args[1]["ttl"] == 30
    
    @pytest.mark.asyncio
    async def test_lock_inventory_update_no_warehouse(self, setup_lock_mock):
        """Test inventory update lock without warehouse."""
        mock_lock = setup_lock_mock
        
        async with LockManager.lock_inventory_update(1) as lock:
            pass
        
        call_args = mock_lock.call_args
        assert call_args[0][0] == "inventory_update:1"
    
    @pytest.mark.asyncio
    async def test_lock_product_update(self, setup_lock_mock):
        """Test product update lock."""
        mock_lock = setup_lock_mock
        
        async with LockManager.lock_product_update(123) as lock:
            pass
        
        call_args = mock_lock.call_args
        assert call_args[0][0] == "product_update:123"
        assert call_args[1]["ttl"] == 15
    
    @pytest.mark.asyncio
    async def test_lock_user_update(self, setup_lock_mock):
        """Test user update lock."""
        mock_lock = setup_lock_mock
        
        async with LockManager.lock_user_update(456) as lock:
            pass
        
        call_args = mock_lock.call_args
        assert call_args[0][0] == "user_update:456"
        assert call_args[1]["ttl"] == 10
    
    @pytest.mark.asyncio
    async def test_lock_warehouse_operation(self, setup_lock_mock):
        """Test warehouse operation lock."""
        mock_lock = setup_lock_mock
        
        async with LockManager.lock_warehouse_operation(789) as lock:
            pass
        
        call_args = mock_lock.call_args
        assert call_args[0][0] == "warehouse_ops:789"
        assert call_args[1]["ttl"] == 20
    
    @pytest.mark.asyncio
    async def test_lock_document_processing(self, setup_lock_mock):
        """Test document processing lock."""
        mock_lock = setup_lock_mock
        
        async with LockManager.lock_document_processing(101) as lock:
            pass
        
        call_args = mock_lock.call_args
        assert call_args[0][0] == "document_processing:101"
        assert call_args[1]["ttl"] == 300
    
    @pytest.mark.asyncio
    async def test_lock_bulk_operation(self, setup_lock_mock):
        """Test bulk operation lock."""
        mock_lock = setup_lock_mock
        
        async with LockManager.lock_bulk_operation("bulk_import_123", ttl=600) as lock:
            pass
        
        call_args = mock_lock.call_args
        assert call_args[0][0] == "bulk_operation:bulk_import_123"
        assert call_args[1]["ttl"] == 600


class TestSemaphore:
    """Test cases for Semaphore."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock redis manager."""
        mock_manager = AsyncMock()
        mock_manager.client.eval.return_value = 1
        return mock_manager
    
    @pytest.fixture
    def setup_redis_mock(self, mock_redis_manager):
        """Setup redis manager mock."""
        with patch('app.shared.core.locking.redis_manager', mock_redis_manager):
            yield mock_redis_manager
    
    @pytest.mark.asyncio
    async def test_semaphore_acquire_success(self, setup_redis_mock):
        """Test successful semaphore acquisition."""
        mock_manager = setup_redis_mock
        mock_manager.client.eval.return_value = 1  # Lua script succeeds
        
        semaphore = Semaphore("test_semaphore", max_concurrent=5)
        result = await semaphore.acquire()
        
        assert result is True
        assert semaphore._acquired
        
        # Check Lua script was called
        mock_manager.client.eval.assert_called_once()
        call_args = mock_manager.client.eval.call_args
        assert call_args[0][1] == 1  # KEYS count
        assert call_args[0][2] == "semaphore:test_semaphore"  # KEY
        # Arguments: now, ttl, max_concurrent, identifier
        assert len(call_args[0]) >= 6  # Should have at least 6 arguments
        assert call_args[0][3] > 0  # now (timestamp)
        assert call_args[0][4] == 3600  # TTL
        assert call_args[0][5] == 5  # max_concurrent
    
    @pytest.mark.asyncio
    async def test_semaphore_acquire_full(self, setup_redis_mock):
        """Test semaphore acquisition when full."""
        mock_manager = setup_redis_mock
        mock_manager.client.eval.return_value = 0  # Lua script fails
        
        semaphore = Semaphore("test_semaphore", max_concurrent=5)
        result = await semaphore.acquire()
        
        assert result is False
        assert not semaphore._acquired
    
    @pytest.mark.asyncio
    async def test_semaphore_release_success(self, setup_redis_mock):
        """Test successful semaphore release."""
        mock_manager = setup_redis_mock
        mock_manager.client.eval.return_value = 1  # Both calls succeed
        
        semaphore = Semaphore("test_semaphore", max_concurrent=5)
        await semaphore.acquire()
        
        result = await semaphore.release()
        
        assert result is True
        assert not semaphore._acquired
        
        # Should have called eval twice (acquire + release)
        assert mock_manager.client.eval.call_count == 2
    
    @pytest.mark.asyncio
    async def test_semaphore_release_not_acquired(self, setup_redis_mock):
        """Test semaphore release when not acquired."""
        semaphore = Semaphore("test_semaphore", max_concurrent=5)
        
        result = await semaphore.release()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_semaphore_context_manager_success(self, setup_redis_mock):
        """Test semaphore as context manager."""
        mock_manager = setup_redis_mock
        mock_manager.client.eval.return_value = 1
        
        semaphore = Semaphore("test_semaphore", max_concurrent=5)
        
        async with semaphore:
            assert semaphore._acquired
        
        # Should be released after context
        assert not semaphore._acquired
        assert mock_manager.client.eval.call_count == 2
    
    @pytest.mark.asyncio
    async def test_semaphore_context_manager_failure(self, setup_redis_mock):
        """Test semaphore context manager - acquisition failure."""
        mock_manager = setup_redis_mock
        mock_manager.client.eval.return_value = 0
        
        semaphore = Semaphore("test_semaphore", max_concurrent=5)
        
        with pytest.raises(RuntimeError, match="Failed to acquire semaphore"):
            async with semaphore:
                pass  # Should not reach here


class TestDistributedLockDecorator:
    """Test cases for distributed_lock decorator."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock redis manager."""
        mock_manager = AsyncMock()
        return mock_manager
    
    @pytest.fixture
    def setup_redis_mock(self, mock_redis_manager):
        """Setup redis manager mock."""
        with patch('app.shared.core.locking.redis_manager', mock_redis_manager):
            yield mock_redis_manager
    
    @pytest.mark.asyncio
    async def test_distributed_lock_decorator_success(self, setup_redis_mock):
        """Test distributed lock decorator with successful execution."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True
        mock_manager.client.eval.return_value = 1
        
        with patch('app.shared.core.locking.DistributedLock') as mock_lock_class:
            mock_lock_instance = AsyncMock()
            mock_lock_instance.__aenter__ = AsyncMock(return_value=mock_lock_instance)
            mock_lock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_lock_class.return_value = mock_lock_instance
            
            call_count = 0
            
            @distributed_lock("test_lock_{0}", ttl=30)
            async def test_function(arg1, arg2):
                nonlocal call_count
                call_count += 1
                return f"result_{arg1}_{arg2}"
            
            result = await test_function("abc", "def")
            
            assert result == "result_abc_def"
            assert call_count == 1
            
            # Check lock was created and used
            mock_lock_class.assert_called_once()
            call_args = mock_lock_class.call_args
            assert call_args[0][0] == "test_lock_abc"
            assert call_args[1]["ttl"] == 30
    
    @pytest.mark.asyncio
    async def test_distributed_lock_decorator_with_kwargs(self, setup_redis_mock):
        """Test distributed lock decorator with keyword arguments."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True
        mock_manager.client.eval.return_value = 1
        
        with patch('app.shared.core.locking.DistributedLock') as mock_lock_class:
            mock_lock_instance = AsyncMock()
            mock_lock_instance.__aenter__ = AsyncMock(return_value=mock_lock_instance)
            mock_lock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_lock_class.return_value = mock_lock_instance
            
            @distributed_lock("test_lock_{product_id}", ttl=15)
            async def test_function(product_id, quantity):
                return f"processed_{product_id}_{quantity}"
            
            result = await test_function(product_id=123, quantity=10)
            
            assert result == "processed_123_10"
            
            call_args = mock_lock_class.call_args
            assert call_args[0][0] == "test_lock_123"
    
    @pytest.mark.asyncio
    async def test_distributed_lock_decorator_sync_function(self):
        """Test that decorator raises error for sync functions."""
        with pytest.raises(TypeError, match="only supports async functions"):
            @distributed_lock("test_lock")
            def sync_function():
                return "result"
    
    @pytest.mark.asyncio
    async def test_distributed_lock_decorator_pattern_failure(self, setup_redis_mock):
        """Test decorator when key pattern fails."""
        mock_manager = setup_redis_mock
        mock_manager.client.set.return_value = True
        mock_manager.client.eval.return_value = 1
        
        with patch('app.shared.core.locking.DistributedLock') as mock_lock_class:
            mock_lock_instance = AsyncMock()
            mock_lock_instance.__aenter__ = AsyncMock(return_value=mock_lock_instance)
            mock_lock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_lock_class.return_value = mock_lock_instance
            
            @distributed_lock("invalid_{missing}", ttl=30)
            async def test_function(arg1):
                return f"result_{arg1}"
            
            result = await test_function("abc")
            
            assert result == "result_abc"
            
            # Should fallback to hash-based key
            call_args = mock_lock_class.call_args
            assert "test_function" in call_args[0][0]
