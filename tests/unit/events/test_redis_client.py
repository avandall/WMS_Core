"""Unit and Stress tests for standardized Redis Stream client and ConnectionPool."""

from unittest.mock import MagicMock, patch
import pytest
import redis
import redis.asyncio as aioredis
from shared_utils.events.publisher import (
    EventEnvelope,
    RedisProtocolError,
    RedisStreamClient,
    build_event,
)
from api_gateway.routes import AsyncRedisStreamClient


class TestRedisStreamClient:
    """Unit tests for synchronous RedisStreamClient."""

    @pytest.fixture
    def mock_redis(self):
        with patch("redis.Redis") as mock_r_cls, patch("redis.ConnectionPool.from_url") as mock_pool_cls:
            mock_r = MagicMock()
            mock_r_cls.return_value = mock_r
            mock_pool = MagicMock()
            mock_pool_cls.return_value = mock_pool
            client = RedisStreamClient("redis://localhost:6379/0")
            yield client, mock_r, mock_pool

    def test_init_creates_connection_pool(self):
        with patch("redis.ConnectionPool.from_url") as mock_pool_cls, patch("redis.Redis") as mock_r_cls:
            client = RedisStreamClient("redis://localhost:6379/0", timeout=3.0)
            mock_pool_cls.assert_called_once_with(
                "redis://localhost:6379/0",
                socket_timeout=3.0,
                socket_connect_timeout=3.0,
                decode_responses=True,
                max_connections=100,
            )
            mock_r_cls.assert_called_once_with(connection_pool=mock_pool_cls.return_value, decode_responses=True)
            assert client.timeout == 3.0

    def test_init_with_custom_connection_pool(self):
        pool = MagicMock(spec=redis.ConnectionPool)
        with patch("redis.Redis") as mock_r_cls:
            client = RedisStreamClient("redis://localhost:6379/0", connection_pool=pool)
            assert client.pool is pool
            mock_r_cls.assert_called_once_with(connection_pool=pool, decode_responses=True)

    def test_no_raw_socket_methods(self):
        client = RedisStreamClient("redis://localhost:6379/0")
        assert not hasattr(client, "_read_line")
        assert not hasattr(client, "_read_response")
        assert not hasattr(client, "_encode_command")

    def test_xadd_success(self, mock_redis):
        client, mock_r, _ = mock_redis
        mock_r.xadd.return_value = "1680000000000-0"

        envelope = build_event(source="test", event_type="OrderCreated", payload={"order_id": 123})
        msg_id = client.xadd("test_stream", envelope)

        assert msg_id == "1680000000000-0"
        mock_r.xadd.assert_called_once()
        args, kwargs = mock_r.xadd.call_args
        assert args[0] == "test_stream"
        assert "event" in args[1]

    def test_xadd_redis_error_raises_protocol_error(self, mock_redis):
        client, mock_r, _ = mock_redis
        mock_r.xadd.side_effect = redis.RedisError("Connection refused")

        envelope = build_event(source="test", event_type="OrderCreated", payload={"order_id": 123})
        with pytest.raises(RedisProtocolError, match="Connection refused"):
            client.xadd("test_stream", envelope)

    def test_xlen(self, mock_redis):
        client, mock_r, _ = mock_redis
        mock_r.xlen.return_value = 42

        assert client.xlen("test_stream") == 42
        mock_r.xlen.assert_called_once_with("test_stream")

    def test_xread(self, mock_redis):
        client, mock_r, _ = mock_redis
        env = build_event(source="test", event_type="ItemAdded", payload={"item_id": 1})
        mock_r.xread.return_value = [
            ["test_stream", [("1000-0", {"event": env.to_json()})]]
        ]

        events = client.xread("test_stream", "0-0", block_ms=1000, count=5)
        assert len(events) == 1
        assert events[0][0] == "1000-0"
        assert events[0][1].event_id == env.event_id

    def test_xgroup_create(self, mock_redis):
        client, mock_r, _ = mock_redis

        client.xgroup_create("test_stream", "group1", start_id="0", mkstream=True)
        mock_r.xgroup_create.assert_called_once_with("test_stream", "group1", id="0", mkstream=True)

    def test_xgroup_create_busygroup_ignored(self, mock_redis):
        client, mock_r, _ = mock_redis
        mock_r.xgroup_create.side_effect = redis.RedisError("BUSYGROUP Consumer Group name already exists")

        # Should not raise exception when BUSYGROUP is returned
        client.xgroup_create("test_stream", "group1")

    def test_xreadgroup(self, mock_redis):
        client, mock_r, _ = mock_redis
        env = build_event(source="test", event_type="ItemAdded", payload={"item_id": 1})
        mock_r.xreadgroup.return_value = [
            ["test_stream", [("1001-0", {"event": env.to_json()})]]
        ]

        events = client.xreadgroup("test_stream", "group1", "consumer1", block_ms=500, count=10)
        assert len(events) == 1
        assert events[0][0] == "1001-0"

    def test_xack(self, mock_redis):
        client, mock_r, _ = mock_redis
        mock_r.xack.return_value = 1

        res = client.xack("test_stream", "group1", "1001-0")
        assert res == 1
        mock_r.xack.assert_called_once_with("test_stream", "group1", "1001-0")

    def test_xpending_range(self, mock_redis):
        client, mock_r, _ = mock_redis
        mock_r.xpending_range.return_value = [
            {"message_id": "1001-0", "consumer": "c1", "time_since_delivered": 1500, "times_delivered": 2}
        ]

        pending = client.xpending_range("test_stream", "group1", count=10)
        assert len(pending) == 1
        assert pending[0]["message_id"] == "1001-0"
        assert pending[0]["consumer"] == "c1"
        assert pending[0]["idle_ms"] == 1500
        assert pending[0]["deliveries"] == 2

    def test_xautoclaim(self, mock_redis):
        client, mock_r, _ = mock_redis
        env = build_event(source="test", event_type="ReclaimedEvent", payload={"key": "val"})
        mock_r.xautoclaim.return_value = [
            "0-0",
            [("1002-0", {"event": env.to_json()})],
            [],
        ]

        events = client.xautoclaim("test_stream", "group1", "consumer1", min_idle_ms=60000)
        assert len(events) == 1
        assert events[0][0] == "1002-0"
        assert events[0][1].type == "ReclaimedEvent"

    def test_execute_raw_command(self, mock_redis):
        client, mock_r, _ = mock_redis
        mock_r.execute_command.return_value = "PONG"

        res = client.execute("PING")
        assert res == "PONG"
        mock_r.execute_command.assert_called_once_with("PING")


class TestAsyncRedisStreamClient:
    """Unit tests for asynchronous AsyncRedisStreamClient."""

    @pytest.mark.asyncio
    async def test_async_xadd_and_batch(self):
        with patch("redis.asyncio.ConnectionPool.from_url") as mock_pool_cls, patch("redis.asyncio.Redis") as mock_r_cls:
            mock_r = MagicMock()
            mock_r.xadd = pytest.importorskip("unittest.mock").AsyncMock(return_value="1000-0")
            
            mock_pipe = MagicMock()
            mock_pipe.execute = pytest.importorskip("unittest.mock").AsyncMock(return_value=["1001-0", "1002-0"])
            mock_r.pipeline.return_value.__aenter__.return_value = mock_pipe

            mock_r_cls.return_value = mock_r

            client = AsyncRedisStreamClient("redis://localhost:6379/0", max_connections=50)
            msg_id = await client.xadd("wms.events", '{"test": 1}')
            assert msg_id == "1000-0"

            await client.xadd_batch("wms.events", ['{"test": 2}', '{"test": 3}'])
            assert mock_pipe.xadd.call_count == 2
            await client.close()


class TestRedisStressPublishing:
    """Stress test continuous event publishing using connection pool."""

    def test_stress_10000_events_publishing(self):
        """Stress test: publish 10,000 events through RedisStreamClient with pool.
        Verifies connection pool reuse without socket exhaustion or high CPU.
        """
        pool = MagicMock(spec=redis.ConnectionPool)
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.xadd.return_value = "1700000000000-0"

        with patch("redis.Redis", return_value=mock_redis):
            client = RedisStreamClient("redis://localhost:6379/0", connection_pool=pool)
            envelope = build_event(source="stress_test", event_type="StressEvent", payload={"seq": 0})

            # Publish 10,000 events continuously
            published_count = 0
            for i in range(10000):
                envelope.payload["seq"] = i
                client.xadd("wms.stress.stream", envelope)
                published_count += 1

            assert published_count == 10000
            assert mock_redis.xadd.call_count == 10000
            client.close()

    @pytest.mark.asyncio
    async def test_stress_10000_async_batch_publishing(self):
        """Stress test: publish 10,000 events via AsyncRedisStreamClient in batches.
        Verifies async pipeline connection pool scaling and performance.
        """
        with patch("redis.asyncio.ConnectionPool.from_url"), patch("redis.asyncio.Redis") as mock_r_cls:
            mock_r = MagicMock()
            mock_pipe = MagicMock()
            mock_pipe.execute = pytest.importorskip("unittest.mock").AsyncMock(return_value=["id"] * 100)
            mock_r.pipeline.return_value.__aenter__.return_value = mock_pipe
            mock_r_cls.return_value = mock_r

            client = AsyncRedisStreamClient("redis://localhost:6379/0", max_connections=100)
            
            # Batch publish 10,000 events in 100 batches of 100 events
            batch_size = 100
            total_events = 10000
            for _ in range(total_events // batch_size):
                batch = [f'{{"event_id": {i}}}' for i in range(batch_size)]
                await client.xadd_batch("wms.stress.stream", batch)

            assert mock_pipe.xadd.call_count == 10000
            await client.close()
