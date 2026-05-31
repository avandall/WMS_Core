"""Cache decorators and utilities for Redis caching."""

import functools
import hashlib
import json
from typing import Any, Callable, Optional, Union
import asyncio
import inspect

from app.shared.core.redis import redis_manager
from app.shared.core.logging import get_logger

logger = get_logger(__name__)

# Serializer registry for generic object reconstruction
_serializer_registry = {}

def register_serializer(type_name: str, from_dict_callable: Callable) -> None:
    """Register a serializer for reconstructing objects from cached dictionaries."""
    _serializer_registry[type_name] = from_dict_callable
    logger.debug(f"Registered serializer for type: {type_name}")

def get_serializer(type_name: str) -> Optional[Callable]:
    """Get registered serializer for a type name."""
    return _serializer_registry.get(type_name)


def _product_from_dict(data: dict):
    """Reconstruct Product from dict."""
    from app.modules.products.domain.entities.product import Product
    return Product(
        product_id=data['product_id'],
        name=data['name'],
        description=data.get('description'),
        price=data['price']
    )


def _warehouse_from_dict(data: dict):
    """Reconstruct Warehouse from dict."""
    from app.modules.warehouses.domain.entities.warehouse import Warehouse
    from app.modules.inventory.domain.entities.inventory import InventoryItem
    
    # Reconstruct inventory items if present
    inventory = []
    if 'inventory' in data and data['inventory']:
        for item_data in data['inventory']:
            inventory.append(InventoryItem(
                product_id=item_data['product_id'],
                quantity=item_data['quantity']
            ))
    
    return Warehouse(
        warehouse_id=data['warehouse_id'],
        location=data['location'],
        inventory=inventory
    )


# Register serializers for domain entities
def _register_domain_serializers():
    """Register serializers for domain entities."""
    register_serializer('Product', _product_from_dict)
    register_serializer('Warehouse', _warehouse_from_dict)


# Auto-register serializers when module is imported
_register_domain_serializers()


def cache_key_builder(
    prefix: str,
    func_name: str,
    args: tuple,
    kwargs: dict,
    include_args: bool = True,
    include_kwargs: bool = True
) -> str:
    """Build cache key from function name and arguments."""
    key_parts = [prefix, func_name]
    
    if include_args and args:
        # Skip first argument if it's 'self' (instance method)
        # Check if first argument looks like an instance (has __class__ but not a basic type)
        if args and len(args) > 0:
            first_arg = args[0]
            # Check if first argument is likely 'self' (instance method)
            # Basic types like int, str, bool, etc. are not 'self'
            basic_types = (int, str, bool, float, type(None))
            if hasattr(first_arg, '__class__') and not isinstance(first_arg, basic_types):
                # This looks like an instance method, skip 'self'
                args_to_hash = args[1:]
            else:
                # This looks like a regular function call, include all args
                args_to_hash = args
        else:
            args_to_hash = args
            
        if args_to_hash:
            args_str = json.dumps(args_to_hash, default=str, sort_keys=True)
            args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
            key_parts.append(f"args:{args_hash}")
    
    if include_kwargs and kwargs:
        kwargs_str = json.dumps(kwargs, default=str, sort_keys=True)
        kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
        key_parts.append(f"kwargs:{kwargs_hash}")
    
    return ":".join(key_parts)


def cached(
    prefix: str = "cache",
    ttl: Optional[int] = None,
    include_args: bool = True,
    include_kwargs: bool = True,
    key_builder: Optional[Callable] = None
):
    """Decorator to cache async function results in Redis."""
    
    def decorator(func: Callable) -> Callable:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("@cached decorator only supports async functions in FastAPI applications")
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(func.__name__, args, kwargs)
            else:
                cache_key = cache_key_builder(
                    prefix, func.__name__, args, kwargs, include_args, include_kwargs
                )
            
            # Try to get from cache
            cached_result = await redis_manager.get(cache_key)
            if cached_result is not None:
                try:
                    cached_value = None

                    # Handle both string and bytes responses
                    if isinstance(cached_result, bytes):
                        cached_result = cached_result.decode('utf-8')
                    
                    # Try to parse as JSON (our cached format)
                    if isinstance(cached_result, str) and cached_result.startswith(('{', '[')):
                        parsed = json.loads(cached_result)
                        # Check if this is our typed cache format
                        if isinstance(parsed, dict) and '__cached_type__' in parsed and '__cached_value__' in parsed:
                            cached_type = parsed['__cached_type__']
                            cached_value = parsed['__cached_value__']
                            
                            # Restore original type
                            if cached_type == 'int':
                                cached_value = int(cached_value)
                            elif cached_type == 'float':
                                cached_value = float(cached_value)
                            elif cached_type == 'bool':
                                cached_value = cached_value.lower() == 'true'
                            elif cached_type == 'str':
                                cached_value = str(cached_value)
                            elif cached_type == 'dict':
                                cached_value = cached_value
                            elif cached_type == 'list':
                                cached_value = cached_value
                            else:
                                # For domain objects, require explicit serializers
                                try:
                                    # Check if we have a registered serializer for this type
                                    serializer = get_serializer(cached_type)
                                    if serializer:
                                        cached_value = serializer(cached_value)
                                    else:
                                        # No serializer registered - this is a configuration error
                                        # We should not cache domain objects without explicit serializers
                                        logger.error(
                                            f"No serializer registered for domain type {cached_type}. "
                                            f"Domain objects require explicit serializers to be cached. "
                                            f"Register a serializer using register_serializer('{cached_type}', from_dict_callable)"
                                        )
                                        cached_value = None  # Treat as cache miss
                                    
                                except Exception as e:
                                    logger.error(f"Failed to reconstruct cached object of type {cached_type}: {e}")
                                    cached_value = None  # Treat as cache miss
                        else:
                            # Legacy format or regular JSON
                            cached_value = parsed
                    else:
                        # Handle primitive types stored directly (legacy)
                        try:
                            # Try to convert to int if possible
                            if isinstance(cached_result, str) and cached_result.isdigit():
                                cached_value = int(cached_result)
                            # Try to convert to float if possible
                            elif isinstance(cached_result, str):
                                try:
                                    cached_value = float(cached_result)
                                except ValueError:
                                    cached_value = cached_result
                            else:
                                cached_value = cached_result
                        except (ValueError, AttributeError):
                            cached_value = cached_result

                    if cached_value is not None:
                        return cached_value
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return cached_result
            
            # Execute function and cache result
            try:
                result = await func(*args, **kwargs)
                
                # Prepare cache value with type information
                cache_value = result
                if isinstance(result, (dict, list)):
                    # For dict/list, store as JSON with type info
                    cache_value = {
                        '__cached_type__': type(result).__name__,
                        '__cached_value__': result
                    }
                elif isinstance(result, (int, float, bool, str)):
                    # For primitives, store with type info
                    cache_value = {
                        '__cached_type__': type(result).__name__,
                        '__cached_value__': str(result)
                    }
                else:
                    # For domain objects, require explicit serializers
                    result_type = type(result).__name__
                    serializer = get_serializer(result_type)
                    
                    if serializer:
                        # Use registered serializer to convert to dict
                        try:
                            serialized_value = result.__dict__ if hasattr(result, '__dict__') else str(result)
                            cache_value = {
                                '__cached_type__': result_type,
                                '__cached_value__': serialized_value
                            }
                        except Exception as e:
                            logger.error(f"Failed to serialize {result_type} for caching: {e}")
                            # Don't cache if serialization fails
                            cache_value = None
                    else:
                        # No serializer registered - don't cache domain objects
                        logger.error(f"Cannot cache {result_type}: no serializer registered. "
                                   f"Domain objects require explicit serializers to be cached. "
                                   f"Register a serializer using register_serializer('{result_type}', from_dict_callable)")
                        # Don't cache domain objects without serializers
                        cache_value = None
                
                # Cache the result only if we have a valid cache_value
                if cache_value is not None:
                    success = await redis_manager.set(cache_key, cache_value, ex=ttl)
                    if success:
                        logger.debug(f"Cached result for key: {cache_key}")
                    else:
                        logger.warning(f"Failed to cache result for key: {cache_key}")
                else:
                    logger.debug(f"Skipping cache for key: {cache_key} (no serializer available)")
                
                return result
                
            except Exception as e:
                logger.error(f"Error executing cached function {func.__name__}: {e}")
                raise
        
        return async_wrapper
    
    return decorator


def invalidate_cache_pattern(pattern: str) -> Callable:
    """Decorator to invalidate cache keys matching pattern after function execution."""
    
    def decorator(func: Callable) -> Callable:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("@invalidate_cache_pattern decorator only supports async functions in FastAPI applications")
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Invalidate cache keys matching pattern using SCAN (non-blocking)
                try:
                    deleted_count = 0
                    cursor = 0
                    scan_pattern = f"*{pattern}*"
                    
                    while True:
                        cursor, keys = await redis_manager.client.scan(
                            cursor, match=scan_pattern, count=100
                        )
                        if keys:
                            deleted_count += await redis_manager.client.delete(*keys)
                        
                        # Exit when cursor returns to 0
                        if cursor == 0:
                            break
                    
                    if deleted_count > 0:
                        logger.debug(f"Invalidated {deleted_count} cache keys matching pattern: {pattern}")
                        
                except Exception as e:
                    logger.error(f"Error invalidating cache pattern '{pattern}': {e}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error executing cache invalidation function {func.__name__}: {e}")
                raise
        
        return async_wrapper
    
    return decorator


def invalidate_cache_key(key: str) -> Callable:
    """Decorator to invalidate specific cache key after function execution."""
    
    def decorator(func: Callable) -> Callable:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("@invalidate_cache_key decorator only supports async functions in FastAPI applications")
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Invalidate specific cache key
                success = await redis_manager.delete(key)
                if success:
                    logger.debug(f"Invalidated cache key: {key}")
                else:
                    logger.debug(f"Cache key not found for invalidation: {key}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error executing cache invalidation function {func.__name__}: {e}")
                raise
        
        return async_wrapper
    
    return decorator


class CacheHelper:
    """Helper class for manual cache operations."""
    
    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """Get value from cache."""
        return await redis_manager.get(key)
    
    @staticmethod
    async def set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        return await redis_manager.set(key, value, ex=ttl)
    
    @staticmethod
    async def delete(key: str) -> bool:
        """Delete key from cache."""
        return await redis_manager.delete(key)
    
    @staticmethod
    async def exists(key: str) -> bool:
        """Check if key exists in cache."""
        return await redis_manager.exists(key)
    
    @staticmethod
    async def invalidate_pattern(pattern: str) -> int:
        """Delete all keys matching pattern using SCAN (non-blocking)."""
        try:
            deleted_count = 0
            cursor = 0
            scan_pattern = f"*{pattern}*"
            
            while True:
                cursor, keys = await redis_manager.client.scan(
                    cursor, match=scan_pattern, count=100
                )
                if keys:
                    deleted_count += await redis_manager.client.delete(*keys)
                
                # Exit when cursor returns to 0
                if cursor == 0:
                    break
            
            return deleted_count
        except Exception as e:
            logger.error(f"Error invalidating cache pattern '{pattern}': {e}")
            return 0
