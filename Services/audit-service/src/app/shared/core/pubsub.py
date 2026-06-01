"""Redis pub/sub system for real-time notifications and events."""

import json
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import time

from app.shared.core.redis import redis_manager
from app.shared.core.logging import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Event types for pub/sub system."""
    STOCK_CHANGE = "stock_change"
    INVENTORY_UPDATE = "inventory_update"
    WAREHOUSE_UPDATE = "warehouse_update"
    USER_ACTIVITY = "user_activity"
    DOCUMENT_STATUS = "document_status"
    SYSTEM_ALERT = "system_alert"
    # Critical operations that need persistence
    CRITICAL_STOCK_CHANGE = "critical_stock_change"
    CRITICAL_INVENTORY_UPDATE = "critical_inventory_update"
    CRITICAL_DOCUMENT_STATUS = "critical_document_status"


@dataclass
class Event:
    """Event data structure."""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: float
    source: str
    user_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    product_id: Optional[int] = None


class PubSubManager:
    """Manages Redis pub/sub subscriptions and publishing."""
    
    def __init__(self):
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._pubsub = None
        self._listener_task: Optional[asyncio.Task] = None
        self._stream_listener_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        # Redis Streams for critical operations
        self._critical_streams = {
            EventType.CRITICAL_STOCK_CHANGE: "wms_critical_stock_changes",
            EventType.CRITICAL_INVENTORY_UPDATE: "wms_critical_inventory_updates",
            EventType.CRITICAL_DOCUMENT_STATUS: "wms_critical_document_status"
        }
    
    async def initialize(self) -> None:
        """Initialize pub/sub manager."""
        if self._running:
            return
        
        self._running = True

        # Subscribe to all event type channels
        event_channels = [f"wms_events:{event_type.value}" for event_type in EventType]
        self._pubsub = await redis_manager.subscribe(*event_channels)
        self._listener_task = asyncio.create_task(self._listen_for_messages())
        logger.info("PubSub manager initialized")
    
    async def shutdown(self) -> None:
        """Shutdown pub/sub manager."""
        self._running = False
        
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        
        if self._pubsub:
            await self._pubsub.aclose()

        # Cancel any explicitly started stream listeners
        for task in self._stream_listener_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info("PubSub manager shutdown")
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe to specific event type."""
        channel = f"wms_events:{event_type.value}"
        if channel not in self._subscriptions:
            self._subscriptions[channel] = []
        self._subscriptions[channel].append(callback)
        logger.info(f"Subscribed to {channel}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from specific event type."""
        channel = f"wms_events:{event_type.value}"
        if channel in self._subscriptions:
            try:
                self._subscriptions[channel].remove(callback)
                logger.info(f"Unsubscribed from {channel}")
                # Clean up empty subscription lists
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]
            except ValueError:
                logger.warning(f"Callback not found in subscriptions for {channel}")
        else:
            logger.warning(f"No subscriptions found for {channel}")
    
    async def publish(self, event: Event) -> None:
        """Publish event to Redis."""
        try:
            channel = f"wms_events:{event.event_type.value}"
            message = {
                "event_type": event.event_type.value,
                "data": event.data,
                "timestamp": event.timestamp,
                "source": event.source,
                "user_id": event.user_id,
                "warehouse_id": event.warehouse_id,
                "product_id": event.product_id,
            }
            
            published = await redis_manager.publish(channel, json.dumps(message, default=str))
            if published > 0:
                logger.debug(f"Published event to {channel}, {published} subscribers")
            else:
                logger.warning(f"No subscribers for {channel}")
            
            # For critical events, also publish to Redis Streams for persistence
            if event.event_type in self._critical_streams:
                stream_name = self._critical_streams[event.event_type]
                try:
                    payload = json.dumps(message, default=str)
                    # Add to stream with maxlen to prevent unbounded growth
                    stream_id = await redis_manager.xadd(
                        stream_name,
                        {
                            "event_type": event.event_type.value,
                            "payload": payload,
                            "timestamp": str(event.timestamp),
                            "source": event.source,
                        },
                        maxlen=10000  # Keep last 10k messages
                    )
                    logger.debug(f"Published critical event to stream {stream_name}: {stream_id}")
                except Exception as e:
                    logger.error(f"Failed to publish to critical stream {stream_name}: {e}")
                
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")

    def get_critical_stream_name(self, event_type: EventType) -> Optional[str]:
        """Get Redis Stream name for a critical event type."""
        return self._critical_streams.get(event_type)

    async def ensure_critical_consumer_group(
        self,
        event_type: EventType,
        group_name: str,
        start_id: str = "0",
    ) -> bool:
        """Create consumer group for a critical stream (idempotent)."""
        stream_name = self.get_critical_stream_name(event_type)
        if not stream_name:
            raise ValueError(f"Event type {event_type} is not configured as a critical stream")
        return await redis_manager.xgroup_create(stream_name, group_name, id=start_id)

    async def read_critical_history(
        self,
        event_type: EventType,
        start_id: str = "-",
        end_id: str = "+",
        count: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Read historical critical events from Redis Streams (no consumer group)."""
        stream_name = self.get_critical_stream_name(event_type)
        if not stream_name:
            raise ValueError(f"Event type {event_type} is not configured as a critical stream")

        entries = await redis_manager.xrange(stream_name, min=start_id, max=end_id, count=count)
        decoded: List[Dict[str, Any]] = []
        for entry_id, fields in entries:
            decoded.append(self._decode_stream_entry(entry_id, fields))
        return decoded

    def start_critical_stream_consumer(
        self,
        event_type: EventType,
        group_name: str,
        consumer_name: str,
        handler: Callable[[Dict[str, Any]], Any],
        *,
        count: int = 10,
        block_ms: int = 5000,
        claim_idle_ms: Optional[int] = None,
        claim_batch: int = 10,
    ) -> str:
        """
        Start a background consumer-group loop for a critical stream.

        - Ensures the consumer group exists (start_id='0' so the group can read history if desired).
        - First optionally claims old pending messages (if claim_idle_ms is provided), then reads new messages via '>'.
        - Calls handler(message_dict) and XACKs only on success.
        """
        stream_name = self.get_critical_stream_name(event_type)
        if not stream_name:
            raise ValueError(f"Event type {event_type} is not configured as a critical stream")

        key = f"{stream_name}:{group_name}:{consumer_name}"
        if key in self._stream_listener_tasks and not self._stream_listener_tasks[key].done():
            return key

        async def _runner():
            await self.ensure_critical_consumer_group(event_type, group_name, start_id="0")
            while self._running:
                try:
                    if claim_idle_ms is not None:
                        await self._claim_and_process_pending(
                            stream_name,
                            group_name,
                            consumer_name,
                            handler,
                            min_idle_ms=claim_idle_ms,
                            batch=claim_batch,
                        )

                    messages = await redis_manager.xreadgroup(
                        group_name,
                        consumer_name,
                        {stream_name: ">"},
                        count=count,
                        block=block_ms,
                    )
                    if not messages:
                        continue

                    for _stream, entries in messages:
                        for entry_id, fields in entries:
                            await self._process_stream_entry(
                                stream_name, group_name, entry_id, fields, handler
                            )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    if self._running:
                        logger.error(f"Critical stream consumer error for {stream_name}: {e}")
                        await asyncio.sleep(1)

        self._stream_listener_tasks[key] = asyncio.create_task(_runner())
        return key

    async def stop_critical_stream_consumer(self, consumer_key: str) -> None:
        """Stop a previously started critical stream consumer loop."""
        task = self._stream_listener_tasks.get(consumer_key)
        if not task:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _claim_and_process_pending(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        handler: Callable[[Dict[str, Any]], Any],
        *,
        min_idle_ms: int,
        batch: int,
    ) -> None:
        pending = await redis_manager.xpending_range(
            stream_name, group_name, min="-", max="+", count=batch
        )
        if not pending:
            return

        stale_ids = []
        for p in pending:
            message_id = None
            idle_ms = 0
            try:
                if hasattr(p, "message_id"):
                    message_id = getattr(p, "message_id", None)
                elif isinstance(p, dict):
                    message_id = p.get("message_id") or p.get("id")
                elif isinstance(p, (list, tuple)) and p:
                    message_id = p[0]

                if hasattr(p, "idle"):
                    idle_ms = int(getattr(p, "idle", 0))
                elif hasattr(p, "time_since_delivered"):
                    idle_ms = int(getattr(p, "time_since_delivered", 0))
                elif isinstance(p, dict):
                    idle_ms = int(p.get("idle", 0) or p.get("time_since_delivered", 0))
                elif isinstance(p, (list, tuple)) and len(p) > 2:
                    idle_ms = int(p[2] or 0)
            except Exception:
                message_id = message_id
                idle_ms = idle_ms
            if message_id and idle_ms >= min_idle_ms:
                stale_ids.append(message_id)

        if not stale_ids:
            return

        claimed = await redis_manager.xclaim(
            stream_name, group_name, consumer_name, min_idle_ms, stale_ids
        )
        for entry_id, fields in claimed:
            await self._process_stream_entry(
                stream_name, group_name, entry_id, fields, handler
            )

    async def _process_stream_entry(
        self,
        stream_name: str,
        group_name: str,
        entry_id: str,
        fields: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        message = self._decode_stream_entry(entry_id, fields)
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
            await redis_manager.xack(stream_name, group_name, entry_id)
        except Exception as e:
            logger.error(f"Error handling critical stream entry {entry_id} ({stream_name}): {e}")

    def _decode_stream_entry(self, entry_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        def _decode(v: Any) -> Any:
            if isinstance(v, bytes):
                return v.decode("utf-8")
            return v

        decoded_fields = {str(_decode(k)): _decode(v) for k, v in (fields or {}).items()}
        payload = decoded_fields.get("payload")
        data = None
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except Exception:
                data = payload

        return {
            "id": entry_id,
            "event_type": decoded_fields.get("event_type"),
            "payload": data,
            "raw": decoded_fields,
        }
    
    async def _listen_for_messages(self) -> None:
        """Listen for pub/sub messages."""
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    await self._handle_message(message)
        except Exception as e:
            if self._running:
                logger.error(f"Error in pub/sub listener: {e}")
    
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming pub/sub message."""
        try:
            # Handle both string and bytes channel names
            channel = message["channel"]
            if isinstance(channel, bytes):
                channel = channel.decode("utf-8")
            
            # Handle both string and bytes data
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            data = json.loads(data)
            
            # Find callbacks for this channel
            await self._dispatch_channel(channel, data)
                    
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def _dispatch_channel(self, channel: str, data: Dict[str, Any]) -> None:
        callbacks = self._subscriptions.get(channel, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in callback for {channel}: {e}")

    async def dispatch_critical_stream_message(self, event_type: EventType, decoded: Dict[str, Any]) -> None:
        """
        Dispatch a decoded stream message to subscribers of the corresponding critical channel.

        The stream payload contains the same JSON shape as Pub/Sub publishes, so downstream handlers stay unchanged.
        """
        stream_payload = decoded.get("payload")
        if not isinstance(stream_payload, dict):
            return
        channel = f"wms_events:{event_type.value}"
        await self._dispatch_channel(channel, stream_payload)


class EventPublisher:
    """Helper class for publishing events."""
    
    @staticmethod
    async def publish_stock_change(
        product_id: int,
        old_quantity: int,
        new_quantity: int,
        warehouse_id: Optional[int] = None,
        user_id: Optional[int] = None,
        source: str = "inventory_service",
        critical: bool = False,
    ) -> None:
        """Publish stock change event."""
        event_type = EventType.CRITICAL_STOCK_CHANGE if critical else EventType.STOCK_CHANGE
        event = Event(
            event_type=event_type,
            data={
                "product_id": product_id,
                "old_quantity": old_quantity,
                "new_quantity": new_quantity,
                "change": new_quantity - old_quantity,
                "warehouse_id": warehouse_id,
            },
            timestamp=time.time(),
            source=source,
            user_id=user_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
        )
        await pubsub_manager.publish(event)
    
    @staticmethod
    async def publish_inventory_update(
        product_id: int,
        warehouse_id: int,
        quantity: int,
        operation: str,  # "add", "remove", "transfer"
        user_id: Optional[int] = None,
        source: str = "inventory_service",
        critical: bool = False  # Mark as critical for warehouse transfers
    ) -> None:
        """Publish inventory update event."""
        event_type = EventType.CRITICAL_INVENTORY_UPDATE if critical else EventType.INVENTORY_UPDATE
        event = Event(
            event_type=event_type,
            data={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity": quantity,
                "operation": operation,
            },
            timestamp=time.time(),
            source=source,
            user_id=user_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
        )
        await pubsub_manager.publish(event)
    
    @staticmethod
    async def publish_document_status(
        document_id: int,
        status: str,
        user_id: Optional[int] = None,
        source: str = "document_service"
    ) -> None:
        """Publish document status change event."""
        event = Event(
            event_type=EventType.DOCUMENT_STATUS,
            data={
                "document_id": document_id,
                "status": status,
            },
            timestamp=time.time(),
            source=source,
            user_id=user_id,
        )
        await pubsub_manager.publish(event)
    
    @staticmethod
    async def publish_system_alert(
        message: str,
        level: str = "info",  # "info", "warning", "error", "critical"
        source: str = "system"
    ) -> None:
        """Publish system alert event."""
        event = Event(
            event_type=EventType.SYSTEM_ALERT,
            data={
                "message": message,
                "level": level,
            },
            timestamp=time.time(),
            source=source,
        )
        await pubsub_manager.publish(event)


# Global pub/sub manager instance
pubsub_manager = PubSubManager()
