"""Redis connection manager for caching and pub/sub functionality."""

import json
from typing import Any, Optional, Union, Dict, List
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.exceptions import ResponseError
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from app.shared.core.settings import settings
from app.shared.core.logging import get_logger

logger = get_logger(__name__)


class RedisManager:
    """Async Redis connection manager with connection pooling."""
    
    _instance: Optional["RedisManager"] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls) -> "RedisManager":
        """Singleton pattern for Redis manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self) -> None:
        """Initialize Redis connection pool."""
        if self._client is not None:
            return
            
        try:
            # Ensure redis_url has decode_responses=True
            redis_url = settings.redis_url
            parsed = urlparse(redis_url)
            query_params = parse_qs(parsed.query or '')
            
            if "decode_responses" not in query_params:
                query_params["decode_responses"] = ["True"]
                new_query = urlencode(query_params, doseq=True)
                redis_url = urlunparse(parsed._replace(query=new_query))
            
            # Create connection pool with health check
            self._pool = ConnectionPool.from_url(
                redis_url,
                max_connections=settings.redis_max_connections,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,  # Check connection health every 30 seconds
            )
            
            # Create Redis client
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._client.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close(self) -> None:
        """Close Redis connections."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._client = None
        self._pool = None
        logger.info("Redis connections closed")
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client (raises if not initialized)."""
        if self._client is None:
            raise RuntimeError("Redis manager not initialized. Call initialize() first.")
        return self._client
    
    async def get(self, key: str) -> Optional[Union[str, bytes]]:
        """Get value from Redis."""
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Union[str, bytes, dict, list], 
        ex: Optional[int] = None
    ) -> bool:
        """Set value in Redis with optional expiration."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            elif not isinstance(value, (str, bytes)):
                value = str(value)
                
            return await self._client.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"Redis SET error for key '{key}': {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            return bool(await self._client.delete(key))
        except Exception as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            return bool(await self._client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS error for key '{key}': {e}")
            return False
    
    async def publish(self, channel: str, message: Union[str, dict, list]) -> int:
        """Publish message to Redis channel."""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, default=str)
            elif not isinstance(message, str):
                message = str(message)
                
            return await self._client.publish(channel, message)
        except Exception as e:
            logger.error(f"Redis PUBLISH error for channel '{channel}': {e}")
            return 0
    
    async def subscribe(self, *channels: str):
        """Subscribe to Redis channels."""
        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(*channels)
            return pubsub
        except Exception as e:
            logger.error(f"Redis SUBSCRIBE error for channels {channels}: {e}")
            raise
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter in Redis."""
        try:
            return await self._client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis INCREMENT error for key '{key}': {e}")
            return None
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key."""
        try:
            return bool(await self._client.expire(key, seconds))
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key '{key}': {e}")
            return False
    
    def pipeline(self):
        """Get Redis pipeline for batch operations."""
        if self._client is None:
            raise RuntimeError("Redis manager not initialized. Call initialize() first.")
        return self._client.pipeline()

    async def execute_pipeline(self, pipeline):
        """Execute Redis pipeline."""
        try:
            return await pipeline.execute()
        except Exception as e:
            logger.error(f"Redis pipeline execution error: {e}")
            raise
    
    async def xadd(self, stream: str, fields: Dict[str, Any], maxlen: Optional[int] = None) -> str:
        """Add message to Redis Stream."""
        try:
            if maxlen:
                return await self._client.xadd(stream, fields, maxlen=maxlen)
            else:
                return await self._client.xadd(stream, fields)
        except Exception as e:
            logger.error(f"Redis XADD error for stream '{stream}': {e}")
            raise
    
    async def xread(self, streams: Dict[str, str], count: Optional[int] = None, block: Optional[int] = None):
        """Read from Redis Streams."""
        try:
            return await self._client.xread(streams, count=count, block=block)
        except Exception as e:
            logger.error(f"Redis XREAD error: {e}")
            raise
    
    async def xreadgroup(self, group: str, consumer: str, streams: Dict[str, str], count: Optional[int] = None, block: Optional[int] = None):
        """Read from Redis Streams with consumer groups."""
        try:
            return await self._client.xreadgroup(group, consumer, streams, count=count, block=block)
        except Exception as e:
            logger.error(f"Redis XREADGROUP error: {e}")
            raise

    async def xrange(
        self,
        stream: str,
        min: str = "-",
        max: str = "+",
        count: Optional[int] = None,
    ):
        """Read a range of entries from a Redis Stream."""
        try:
            return await self._client.xrange(stream, min=min, max=max, count=count)
        except Exception as e:
            logger.error(f"Redis XRANGE error for stream '{stream}': {e}")
            raise

    async def xpending(self, stream: str, group: str):
        """Get pending message summary for a consumer group."""
        try:
            return await self._client.xpending(stream, group)
        except Exception as e:
            logger.error(f"Redis XPENDING error for stream '{stream}', group '{group}': {e}")
            raise

    async def xpending_range(
        self,
        stream: str,
        group: str,
        min: str = "-",
        max: str = "+",
        count: int = 10,
        consumername: Optional[str] = None,
    ):
        """Get pending message details for a consumer group."""
        try:
            return await self._client.xpending_range(
                stream, group, min=min, max=max, count=count, consumername=consumername
            )
        except Exception as e:
            logger.error(f"Redis XPENDING RANGE error for stream '{stream}', group '{group}': {e}")
            raise

    async def xclaim(
        self,
        stream: str,
        group: str,
        consumer: str,
        min_idle_time: int,
        message_ids: List[str],
    ):
        """Claim pending messages that have been idle for at least min_idle_time (ms)."""
        try:
            return await self._client.xclaim(
                stream, group, consumer, min_idle_time, message_ids
            )
        except Exception as e:
            logger.error(f"Redis XCLAIM error for stream '{stream}', group '{group}': {e}")
            raise
    
    async def xgroup_create(self, stream: str, group: str, id: str = "$", mkstream: bool = True) -> bool:
        """Create consumer group for Redis Stream."""
        try:
            await self._client.xgroup_create(stream, group, id=id, mkstream=mkstream)
            return True
        except ResponseError as e:
            message = str(e)
            if "BUSYGROUP" in message:
                logger.info(f"Redis XGROUP CREATE group already exists for stream '{stream}'")
                return True
            logger.error(f"Redis XGROUP CREATE error for stream '{stream}': {e}")
            return False
        except Exception as e:
            logger.error(f"Redis XGROUP CREATE error for stream '{stream}': {e}")
            return False
    
    async def xack(self, stream: str, group: str, *ids: str) -> int:
        """Acknowledge messages in Redis Stream consumer group."""
        try:
            return await self._client.xack(stream, group, *ids)
        except Exception as e:
            logger.error(f"Redis XACK error for stream '{stream}': {e}")
            return 0
    
    async def info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get Redis INFO statistics."""
        try:
            return await self._client.info(section=section)
        except Exception as e:
            logger.error(f"Redis INFO error: {e}")
            return {}
    
    async def get_memory_usage(self) -> Dict[str, Any]:
        """Get Redis memory usage statistics."""
        try:
            info = await self.info("memory")
            return {
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "used_memory_peak": info.get("used_memory_peak"),
                "used_memory_peak_human": info.get("used_memory_peak_human"),
                "total_system_memory": info.get("total_system_memory"),
                "total_system_memory_human": info.get("total_system_memory_human"),
                "mem_fragmentation_ratio": info.get("mem_fragmentation_ratio"),
                "allocator_allocated": info.get("allocator_allocated"),
                "allocator_active": info.get("allocator_active"),
                "allocator_resident": info.get("allocator_resident"),
            }
        except Exception as e:
            logger.error(f"Failed to get Redis memory stats: {e}")
            return {}
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get Redis performance statistics."""
        try:
            info = await self.info("stats")
            return {
                "total_connections_received": info.get("total_connections_received"),
                "total_commands_processed": info.get("total_commands_processed"),
                "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec"),
                "total_net_input_bytes": info.get("total_net_input_bytes"),
                "total_net_output_bytes": info.get("total_net_output_bytes"),
                "rejected_connections": info.get("rejected_connections"),
                "expired_keys": info.get("expired_keys"),
                "evicted_keys": info.get("evicted_keys"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
            }
        except Exception as e:
            logger.error(f"Failed to get Redis performance stats: {e}")
            return {}
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive Redis health status."""
        try:
            # Test connection
            ping_result = await self._client.ping()
            
            # Get basic info
            info = await self.info()
            
            # Get memory stats
            memory = await self.get_memory_usage()
            
            # Get performance stats
            performance = await self.get_performance_stats()
            
            # Calculate health score (0-100)
            health_score = 100
            issues = []
            
            # Check memory usage (>80% is concerning)
            if memory.get("mem_fragmentation_ratio"):
                frag_ratio = float(memory["mem_fragmentation_ratio"])
                if frag_ratio > 2.0 or frag_ratio < 1.0:
                    health_score -= 20
                    issues.append(f"Memory fragmentation ratio: {frag_ratio}")
            
            # Check connection issues
            if info.get("rejected_connections", 0) > 0:
                health_score -= 10
                issues.append(f"Rejected connections: {info['rejected_connections']}")
            
            # Check eviction (memory pressure)
            if performance.get("evicted_keys", 0) > 1000:
                health_score -= 15
                issues.append(f"High eviction rate: {performance['evicted_keys']} keys")
            
            return {
                "healthy": ping_result == "PONG",
                "health_score": max(0, health_score),
                "issues": issues,
                "uptime_seconds": info.get("uptime_in_seconds"),
                "version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "memory": memory,
                "performance": performance,
            }
            
        except Exception as e:
            logger.error(f"Failed to get Redis health status: {e}")
            return {
                "healthy": False,
                "health_score": 0,
                "issues": [str(e)],
                "memory": {},
                "performance": {},
            }
    
    async def bulk_set(self, key_value_pairs: Dict[str, Any], ttl: Optional[int] = None) -> List[bool]:
        """Bulk set multiple key-value pairs using pipeline for optimal performance."""
        if not key_value_pairs:
            return []
        
        try:
            pipeline = self.pipeline()
            
            for key, value in key_value_pairs.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, default=str)
                elif not isinstance(value, (str, bytes)):
                    value = str(value)
                
                pipeline.set(key, value, ex=ttl)
            
            results = await self.execute_pipeline(pipeline)
            
            # Convert results to boolean list
            return [bool(result) for result in results]
            
        except Exception as e:
            logger.error(f"Redis bulk set error: {e}")
            return [False] * len(key_value_pairs)
    
    async def bulk_get(self, keys: List[str]) -> Dict[str, Any]:
        """Bulk get multiple keys using pipeline for optimal performance."""
        if not keys:
            return {}
        
        try:
            pipeline = self.pipeline()
            
            for key in keys:
                pipeline.get(key)
            
            results = await self.execute_pipeline(pipeline)
            
            # Build result dictionary
            result_dict = {}
            for key, value in zip(keys, results):
                if value is not None:
                    # Try to parse JSON, fallback to string
                    try:
                        result_dict[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result_dict[key] = value
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Redis bulk get error: {e}")
            return {}
    
    async def bulk_delete(self, keys: List[str]) -> int:
        """Bulk delete multiple keys using pipeline for optimal performance."""
        if not keys:
            return 0
        
        try:
            pipeline = self.pipeline()
            
            for key in keys:
                pipeline.delete(key)
            
            results = await self.execute_pipeline(pipeline)
            
            # Count successful deletions
            return sum(1 for result in results if result)
            
        except Exception as e:
            logger.error(f"Redis bulk delete error: {e}")
            return 0


# Global Redis manager instance
redis_manager = RedisManager()
