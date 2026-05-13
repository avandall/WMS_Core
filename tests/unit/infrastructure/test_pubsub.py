"""Tests for Redis pub/sub system."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.shared.core.pubsub import (
    PubSubManager, Event, EventType, EventPublisher, pubsub_manager
)


class TestEvent:
    """Test cases for Event dataclass."""
    
    def test_event_creation(self):
        """Test event creation with all fields."""
        event = Event(
            event_type=EventType.STOCK_CHANGE,
            data={"product_id": 1, "quantity": 10},
            timestamp=1234567890.0,
            source="test_service",
            user_id=1,
            warehouse_id=2,
            product_id=1
        )
        
        assert event.event_type == EventType.STOCK_CHANGE
        assert event.data["product_id"] == 1
        assert event.timestamp == 1234567890.0
        assert event.source == "test_service"
        assert event.user_id == 1
        assert event.warehouse_id == 2
        assert event.product_id == 1
    
    def test_event_creation_minimal(self):
        """Test event creation with minimal fields."""
        event = Event(
            event_type=EventType.SYSTEM_ALERT,
            data={"message": "test"},
            timestamp=1234567890.0,
            source="system"
        )
        
        assert event.event_type == EventType.SYSTEM_ALERT
        assert event.data["message"] == "test"
        assert event.user_id is None
        assert event.warehouse_id is None
        assert event.product_id is None


class TestPubSubManager:
    """Test cases for PubSubManager."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock redis manager."""
        mock_manager = AsyncMock()
        mock_pubsub = AsyncMock()
        
        # Create a proper async iterator for listen()
        async def mock_listen():
            # Empty async iterator that yields nothing
            return
            yield  # This makes it an async generator
        
        mock_pubsub.listen = mock_listen
        mock_manager.subscribe.return_value = mock_pubsub
        return mock_manager, mock_pubsub
    
    @pytest.fixture
    def setup_redis_mock(self, mock_redis_manager):
        """Setup redis manager mock."""
        mock_manager, mock_pubsub = mock_redis_manager
        with patch('app.shared.core.pubsub.redis_manager', mock_manager):
            yield mock_manager, mock_pubsub
    
    @pytest.mark.asyncio
    async def test_pubsub_manager_initialize(self, setup_redis_mock):
        """Test PubSubManager initialization."""
        mock_manager, mock_pubsub = setup_redis_mock
        
        manager = PubSubManager()
        await manager.initialize()
        
        assert manager._running is True
        assert manager._pubsub is mock_pubsub
        assert manager._listener_task is not None
        mock_manager.subscribe.assert_called_once_with(
            "wms_events:stock_change",
            "wms_events:inventory_update",
            "wms_events:warehouse_update",
            "wms_events:user_activity",
            "wms_events:document_status",
            "wms_events:system_alert",
            "wms_events:critical_stock_change",
            "wms_events:critical_inventory_update",
            "wms_events:critical_document_status"
        )
    
    @pytest.mark.asyncio
    async def test_pubsub_manager_double_initialize(self, setup_redis_mock):
        """Test that double initialization doesn't create multiple listeners."""
        mock_manager, mock_pubsub = setup_redis_mock
        
        manager = PubSubManager()
        await manager.initialize()
        first_task = manager._listener_task
        
        await manager.initialize()
        
        assert manager._listener_task is first_task
        assert mock_manager.subscribe.call_count == 1
    
    @pytest.mark.asyncio
    async def test_pubsub_manager_shutdown(self, setup_redis_mock):
        """Test PubSubManager shutdown."""
        mock_manager, mock_pubsub = setup_redis_mock
        
        manager = PubSubManager()
        await manager.initialize()
        
        # Call shutdown method to test proper shutdown behavior
        await manager.shutdown()
        
        # Verify shutdown state
        assert manager._running is False
        mock_pubsub.aclose.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_subscribe_to_event_type(self, setup_redis_mock):
        """Test subscribing to specific event type."""
        mock_manager, mock_pubsub = setup_redis_mock
        
        manager = PubSubManager()
        callback = AsyncMock()
        
        manager.subscribe(EventType.STOCK_CHANGE, callback)
        
        expected_channel = "wms_events:stock_change"
        assert expected_channel in manager._subscriptions
        assert callback in manager._subscriptions[expected_channel]
    
    @pytest.mark.asyncio
    async def test_subscribe_multiple_callbacks(self, setup_redis_mock):
        """Test subscribing multiple callbacks to same event type."""
        mock_manager, mock_pubsub = setup_redis_mock
        
        manager = PubSubManager()
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        
        manager.subscribe(EventType.STOCK_CHANGE, callback1)
        manager.subscribe(EventType.STOCK_CHANGE, callback2)
        
        channel = "wms_events:stock_change"
        assert len(manager._subscriptions[channel]) == 2
        assert callback1 in manager._subscriptions[channel]
        assert callback2 in manager._subscriptions[channel]
    
    @pytest.mark.asyncio
    async def test_publish_event_success(self, setup_redis_mock):
        """Test successful event publishing."""
        mock_manager, mock_pubsub = setup_redis_mock
        mock_manager.publish.return_value = 2
        
        manager = PubSubManager()
        event = Event(
            event_type=EventType.STOCK_CHANGE,
            data={"product_id": 1, "quantity": 10},
            timestamp=1234567890.0,
            source="test_service"
        )
        
        await manager.publish(event)
        
        # Check publish was called correctly
        mock_manager.publish.assert_called_once()
        call_args = mock_manager.publish.call_args
        assert call_args[0][0] == "wms_events:stock_change"
        
        # Check message structure
        message = json.loads(call_args[0][1])
        assert message["event_type"] == "stock_change"
        assert message["data"]["product_id"] == 1
        assert message["source"] == "test_service"
    
    @pytest.mark.asyncio
    async def test_publish_event_no_subscribers(self, setup_redis_mock):
        """Test publishing event with no subscribers."""
        mock_manager, mock_pubsub = setup_redis_mock
        mock_manager.publish.return_value = 0
        
        manager = PubSubManager()
        event = Event(
            event_type=EventType.STOCK_CHANGE,
            data={"product_id": 1},
            timestamp=1234567890.0,
            source="test_service"
        )
        
        await manager.publish(event)
        
        # Should still publish but log warning
        mock_manager.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_event_error(self, setup_redis_mock):
        """Test publishing event with error."""
        mock_manager, mock_pubsub = setup_redis_mock
        mock_manager.publish.side_effect = Exception("Redis error")
        
        manager = PubSubManager()
        event = Event(
            event_type=EventType.STOCK_CHANGE,
            data={"product_id": 1},
            timestamp=1234567890.0,
            source="test_service"
        )
        
        # Should not raise exception, just log error
        await manager.publish(event)
        mock_manager.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_critical_event_persists_to_stream(self, setup_redis_mock):
        """Test that critical events also persist to Redis Streams."""
        mock_manager, mock_pubsub = setup_redis_mock
        mock_manager.publish.return_value = 1
        mock_manager.xadd.return_value = "12345-0"
        
        manager = PubSubManager()
        event = Event(
            event_type=EventType.CRITICAL_INVENTORY_UPDATE,
            data={"product_id": 1, "warehouse_id": 2, "quantity": 5, "operation": "transfer"},
            timestamp=1234567890.0,
            source="test_service"
        )
        
        await manager.publish(event)
        mock_manager.publish.assert_called_once()
        mock_manager.xadd.assert_called_once()
        xadd_args = mock_manager.xadd.call_args[0]
        assert xadd_args[0] == "wms_critical_inventory_updates"
        assert isinstance(xadd_args[1], dict)
        assert xadd_args[1]["event_type"] == "critical_inventory_update"
        assert "payload" in xadd_args[1]
        assert isinstance(xadd_args[1]["payload"], str)

    @pytest.mark.asyncio
    async def test_start_critical_stream_consumer_processes_and_acks(self, setup_redis_mock):
        """Test consuming from Redis Streams via consumer group (catch-up mechanism)."""
        mock_manager, _ = setup_redis_mock
        mock_manager.xgroup_create.return_value = True
        mock_manager.xack.return_value = 1

        # One batch of messages, then empty
        mock_manager.xreadgroup.side_effect = [
            [("wms_critical_inventory_updates", [("12345-0", {"event_type": "critical_inventory_update", "payload": "{\"ok\": true}"})])],
            [],
        ]

        manager = PubSubManager()
        manager._running = True  # emulate initialized manager loop

        handler = AsyncMock()
        key = manager.start_critical_stream_consumer(
            EventType.CRITICAL_INVENTORY_UPDATE,
            group_name="test_group",
            consumer_name="test_consumer",
            handler=handler,
            block_ms=1,
        )

        # Let the consumer run at least once
        await asyncio.sleep(0)

        manager._running = False
        await manager.stop_critical_stream_consumer(key)

        mock_manager.xgroup_create.assert_called_once_with(
            "wms_critical_inventory_updates", "test_group", id="0"
        )
        mock_manager.xreadgroup.assert_called()
        handler.assert_called()
        mock_manager.xack.assert_called_with(
            "wms_critical_inventory_updates", "test_group", "12345-0"
        )
    
    @pytest.mark.asyncio
    async def test_handle_message_success(self, setup_redis_mock):
        """Test successful message handling."""
        mock_manager, mock_pubsub = setup_redis_mock
        
        manager = PubSubManager()
        callback = AsyncMock()
        manager.subscribe(EventType.STOCK_CHANGE, callback)
        
        message_data = {
            "event_type": "stock_change",
            "data": {"product_id": 1, "quantity": 10},
            "timestamp": 1234567890.0,
            "source": "test_service"
        }
        
        message = {
            "channel": b"wms_events:stock_change",
            "data": json.dumps(message_data).encode('utf-8')
        }
        
        await manager._handle_message(message)
        
        callback.assert_called_once_with(message_data)
    
    @pytest.mark.asyncio
    async def test_handle_message_no_subscribers(self, setup_redis_mock):
        """Test handling message with no subscribers."""
        mock_manager, mock_pubsub = setup_redis_mock
        
        manager = PubSubManager()
        
        message = {
            "channel": b"wms_events:unknown",
            "data": b'{"test": "data"}'
        }
        
        # Should not raise exception
        await manager._handle_message(message)
    
    @pytest.mark.asyncio
    async def test_handle_message_callback_error(self, setup_redis_mock):
        """Test handling message when callback raises error."""
        mock_manager, mock_pubsub = setup_redis_mock
        
        manager = PubSubManager()
        callback = AsyncMock(side_effect=Exception("Callback error"))
        manager.subscribe(EventType.STOCK_CHANGE, callback)
        
        message_data = {"event_type": "stock_change", "data": {}}
        message = {
            "channel": b"wms_events:stock_change",
            "data": json.dumps(message_data).encode('utf-8')
        }
        
        # Should not raise exception, just log error
        await manager._handle_message(message)
        callback.assert_called_once()


class TestEventPublisher:
    """Test cases for EventPublisher."""
    
    @pytest.fixture
    def mock_pubsub_manager(self):
        """Mock pubsub manager."""
        mock_manager = AsyncMock()
        return mock_manager
    
    @pytest.fixture
    def setup_pubsub_mock(self, mock_pubsub_manager):
        """Setup pubsub manager mock."""
        with patch('app.shared.core.pubsub.pubsub_manager', mock_pubsub_manager):
            yield mock_pubsub_manager
    
    @pytest.mark.asyncio
    async def test_publish_stock_change(self, setup_pubsub_mock):
        """Test publishing stock change event."""
        mock_manager = setup_pubsub_mock
        
        await EventPublisher.publish_stock_change(
            product_id=1,
            old_quantity=10,
            new_quantity=15,
            warehouse_id=2,
            user_id=3,
            source="inventory_service"
        )
        
        # Check publish was called
        mock_manager.publish.assert_called_once()
        call_args = mock_manager.publish.call_args
        event = call_args[0][0]
        
        assert event.event_type == EventType.STOCK_CHANGE
        assert event.data["product_id"] == 1
        assert event.data["old_quantity"] == 10
        assert event.data["new_quantity"] == 15
        assert event.data["change"] == 5
        assert event.data["warehouse_id"] == 2
        assert event.user_id == 3
        assert event.warehouse_id == 2
        assert event.product_id == 1
        assert event.source == "inventory_service"
    
    @pytest.mark.asyncio
    async def test_publish_stock_change_minimal(self, setup_pubsub_mock):
        """Test publishing stock change with minimal parameters."""
        mock_manager = setup_pubsub_mock
        
        await EventPublisher.publish_stock_change(
            product_id=1,
            old_quantity=10,
            new_quantity=15
        )
        
        event = mock_manager.publish.call_args[0][0]
        assert event.event_type == EventType.STOCK_CHANGE
        assert event.user_id is None
        assert event.warehouse_id is None
        assert event.source == "inventory_service"
    
    @pytest.mark.asyncio
    async def test_publish_inventory_update(self, setup_pubsub_mock):
        """Test publishing inventory update event."""
        mock_manager = setup_pubsub_mock
        
        await EventPublisher.publish_inventory_update(
            product_id=1,
            warehouse_id=2,
            quantity=5,
            operation="add",
            user_id=3,
            source="test_service"
        )
        
        event = mock_manager.publish.call_args[0][0]
        assert event.event_type == EventType.INVENTORY_UPDATE
        assert event.data["product_id"] == 1
        assert event.data["warehouse_id"] == 2
        assert event.data["quantity"] == 5
        assert event.data["operation"] == "add"
        assert event.user_id == 3
        assert event.source == "test_service"
    
    @pytest.mark.asyncio
    async def test_publish_document_status(self, setup_pubsub_mock):
        """Test publishing document status event."""
        mock_manager = setup_pubsub_mock
        
        await EventPublisher.publish_document_status(
            document_id=123,
            status="completed",
            user_id=1,
            source="document_service"
        )
        
        event = mock_manager.publish.call_args[0][0]
        assert event.event_type == EventType.DOCUMENT_STATUS
        assert event.data["document_id"] == 123
        assert event.data["status"] == "completed"
        assert event.user_id == 1
        assert event.source == "document_service"
    
    @pytest.mark.asyncio
    async def test_publish_system_alert(self, setup_pubsub_mock):
        """Test publishing system alert event."""
        mock_manager = setup_pubsub_mock
        
        await EventPublisher.publish_system_alert(
            message="System maintenance scheduled",
            level="warning",
            source="system"
        )
        
        event = mock_manager.publish.call_args[0][0]
        assert event.event_type == EventType.SYSTEM_ALERT
        assert event.data["message"] == "System maintenance scheduled"
        assert event.data["level"] == "warning"
        assert event.user_id is None
        assert event.source == "system"
    
    @pytest.mark.asyncio
    async def test_publish_system_alert_default_level(self, setup_pubsub_mock):
        """Test publishing system alert with default level."""
        mock_manager = setup_pubsub_mock
        
        await EventPublisher.publish_system_alert(
            message="Info message"
        )
        
        event = mock_manager.publish.call_args[0][0]
        assert event.data["level"] == "info"
        assert event.source == "system"


class TestEventType:
    """Test cases for EventType enum."""
    
    def test_event_type_values(self):
        """Test that EventType has correct values."""
        assert EventType.STOCK_CHANGE.value == "stock_change"
        assert EventType.INVENTORY_UPDATE.value == "inventory_update"
        assert EventType.WAREHOUSE_UPDATE.value == "warehouse_update"
        assert EventType.USER_ACTIVITY.value == "user_activity"
        assert EventType.DOCUMENT_STATUS.value == "document_status"
        assert EventType.SYSTEM_ALERT.value == "system_alert"
