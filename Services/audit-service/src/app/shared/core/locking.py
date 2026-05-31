"""Redis-based distributed locking for concurrent operations."""

import asyncio
import functools
import uuid
from typing import Optional, Any, Callable
from contextlib import asynccontextmanager

from app.shared.core.redis import redis_manager
from app.shared.core.logging import get_logger

logger = get_logger(__name__)


class DistributedLock:
    """Redis-based distributed lock for coordinating concurrent operations."""
    
    def __init__(self, key: str, ttl: int = 30, retry_delay: float = 0.1, max_retries: int = 30):
        self.key = f"lock:{key}"
        self.ttl = ttl
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.identifier = str(uuid.uuid4())
        self._acquired = False
    
    async def acquire(self) -> bool:
        """Acquire the lock."""
        for attempt in range(self.max_retries):
            # Try to acquire lock using SET NX EX
            success = await redis_manager.client.set(
                self.key, 
                self.identifier, 
                ex=self.ttl, 
                nx=True
            )
            
            if success:
                self._acquired = True
                logger.debug(f"Acquired lock {self.key} (identifier: {self.identifier[:8]})")
                return True
            
            # Lock not acquired, wait and retry
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay)
        
        logger.warning(f"Failed to acquire lock {self.key} after {self.max_retries} attempts")
        return False
    
    async def release(self) -> bool:
        """Release the lock if we own it."""
        if not self._acquired:
            return False
        
        # Use Lua script for atomic release
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        
        try:
            result = await redis_manager.client.eval(lua_script, 1, self.key, self.identifier)
            if result:
                self._acquired = False
                logger.debug(f"Released lock {self.key}")
                return True
            else:
                logger.warning(f"Failed to release lock {self.key} - not owner")
                return False
        except Exception as e:
            logger.error(f"Error releasing lock {self.key}: {e}")
            return False
    
    async def extend(self, additional_ttl: Optional[int] = None) -> bool:
        """Extend lock TTL if we still own it."""
        if not self._acquired:
            return False
        
        extension = additional_ttl or self.ttl
        
        # Use Lua script for atomic extension with remaining TTL calculation
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            local remaining = redis.call("TTL", KEYS[1])
            if remaining < 0 then
                -- Key has no expiry or doesn't exist, set to extension amount
                redis.call("EXPIRE", KEYS[1], ARGV[2])
                return ARGV[2]
            else
                -- Add extension to remaining TTL
                local new_ttl = remaining + tonumber(ARGV[2])
                redis.call("EXPIRE", KEYS[1], new_ttl)
                return new_ttl
            end
        else
            return 0
        end
        """
        
        try:
            result = await redis_manager.client.eval(lua_script, 1, self.key, self.identifier, extension)
            if result:
                logger.debug(f"Extended lock {self.key} by {extension} seconds (new TTL: {result})")
                return True
            else:
                logger.warning(f"Failed to extend lock {self.key} - not owner")
                return False
        except Exception as e:
            logger.error(f"Error extending lock {self.key}: {e}")
            return False
    
    def is_acquired(self) -> bool:
        """Check if lock is acquired."""
        return self._acquired
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not await self.acquire():
            raise RuntimeError(f"Failed to acquire lock: {self.key}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.release()


class LockManager:
    """Manages distributed locks with different strategies."""
    
    @staticmethod
    @asynccontextmanager
    async def lock_inventory_update(product_id: int, warehouse_id: Optional[int] = None):
        """Lock for inventory updates to prevent race conditions."""
        lock_key = f"inventory_update:{product_id}"
        if warehouse_id:
            lock_key += f":{warehouse_id}"
        
        lock = DistributedLock(lock_key, ttl=30)
        async with lock:
            yield lock
    
    @staticmethod
    @asynccontextmanager
    async def lock_product_update(product_id: int):
        """Lock for product updates to prevent concurrent modifications."""
        lock_key = f"product_update:{product_id}"
        lock = DistributedLock(lock_key, ttl=15)
        async with lock:
            yield lock
    
    @staticmethod
    @asynccontextmanager
    async def lock_user_update(user_id: int):
        """Lock for user updates to prevent concurrent modifications."""
        lock_key = f"user_update:{user_id}"
        lock = DistributedLock(lock_key, ttl=10)
        async with lock:
            yield lock
    
    @staticmethod
    @asynccontextmanager
    async def lock_warehouse_operation(warehouse_id: int):
        """Lock for warehouse operations to prevent conflicts."""
        lock_key = f"warehouse_ops:{warehouse_id}"
        lock = DistributedLock(lock_key, ttl=20)
        async with lock:
            yield lock
    
    @staticmethod
    @asynccontextmanager
    async def lock_document_processing(document_id: int):
        """Lock for document processing to prevent duplicate processing."""
        lock_key = f"document_processing:{document_id}"
        lock = DistributedLock(lock_key, ttl=300)  # 5 minutes for document processing
        async with lock:
            yield lock
    
    @staticmethod
    @asynccontextmanager
    async def lock_bulk_operation(operation_id: str, ttl: int = 600):
        """Lock for bulk operations that take longer."""
        lock_key = f"bulk_operation:{operation_id}"
        lock = DistributedLock(lock_key, ttl=ttl)
        async with lock:
            yield lock


class Semaphore:
    """Redis-based semaphore for limiting concurrent operations."""
    
    def __init__(self, key: str, max_concurrent: int, ttl: int = 3600):
        self.key = f"semaphore:{key}"
        self.max_concurrent = max_concurrent
        self.ttl = ttl
        self.identifier = str(uuid.uuid4())
        self._acquired = False
    
    async def acquire(self) -> bool:
        """Acquire a semaphore slot with per-token ownership."""
        # Use Lua script with sorted set for per-token permits
        lua_script = """
        local now = tonumber(ARGV[1])
        local ttl = tonumber(ARGV[2])
        local max_concurrent = tonumber(ARGV[3])
        local identifier = ARGV[4]
        
        -- Remove expired tokens
        redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - 1)
        
        -- Check current active permits
        local current = redis.call('ZCARD', KEYS[1])
        
        if current < max_concurrent then
            -- Add new permit with expiry timestamp
            redis.call('ZADD', KEYS[1], now + ttl, identifier)
            return 1
        else
            return 0
        end
        """
        
        try:
            import time
            now = int(time.time())
            result = await redis_manager.client.eval(
                lua_script, 1, self.key, now, self.ttl, self.max_concurrent, self.identifier
            )
            
            if result:
                self._acquired = True
                logger.debug(f"Acquired semaphore slot {self.key} (identifier: {self.identifier[:8]})")
                return True
            else:
                logger.debug(f"Semaphore {self.key} is full")
                return False
        except Exception as e:
            logger.error(f"Error acquiring semaphore {self.key}: {e}")
            return False
    
    async def release(self) -> bool:
        """Release a semaphore slot by removing specific identifier token."""
        if not self._acquired:
            return False
        
        # Use Lua script to atomically remove specific identifier
        lua_script = """
        local identifier = ARGV[1]
        local removed = redis.call('ZREM', KEYS[1], identifier)
        return removed
        """
        
        try:
            result = await redis_manager.client.eval(lua_script, 1, self.key, self.identifier)
            if result:
                self._acquired = False
                logger.debug(f"Released semaphore slot {self.key} (identifier: {self.identifier[:8]})")
                return True
            else:
                logger.warning(f"Failed to release semaphore slot {self.key} - identifier not found or already expired")
                return False
        except Exception as e:
            logger.error(f"Error releasing semaphore {self.key}: {e}")
            return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not await self.acquire():
            raise RuntimeError(f"Failed to acquire semaphore: {self.key}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.release()


# Decorator for automatic locking
def distributed_lock(key_pattern: str, ttl: int = 30):
    """Decorator to automatically apply distributed lock to function."""
    def decorator(func: Callable) -> Callable:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("@distributed_lock decorator only supports async functions")
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate lock key from pattern and arguments
            try:
                lock_key = key_pattern.format(*args, **kwargs)
            except (IndexError, KeyError):
                # Fallback to function name if pattern fails
                lock_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            lock = DistributedLock(lock_key, ttl=ttl)
            async with lock:
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator
