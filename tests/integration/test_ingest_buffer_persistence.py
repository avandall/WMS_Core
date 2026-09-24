"""Integration tests for Persistent Ingestion Buffer with WAL & Dead Letter Queue (TASK-048 / ING-01/02).

Acceptance Criteria:
1. Local Disk WAL / Spool file before confirming 202 Accepted.
2. No silent discard ('except Exception: pass'): failed batches saved to DLQ.
3. Background DLQ Retry Worker with exponential backoff & jitter.
4. Crash Recovery simulation: 1,000 events sent, process killed abruptly, restarted -> 100% recovered to Redis.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
import pytest
from unittest.mock import AsyncMock

from api_gateway.ingest_buffer import IngestBuffer, WalManager, DLQManager


class MockRedisStream:
    """Mock Redis client tracking pushed batches."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.stored_events: list[str] = []
        self.call_count = 0

    async def xadd_batch(self, stream: str, batch: list[str]) -> None:
        self.call_count += 1
        if self.should_fail:
            raise ConnectionError("Redis cluster unreachable or overloaded (simulated)")
        self.stored_events.extend(batch)


@pytest.fixture
def temp_storage():
    """Create isolated temporary directories for WAL and DLQ testing."""
    wal_dir = tempfile.mkdtemp(prefix="test_wal_")
    dlq_dir = tempfile.mkdtemp(prefix="test_dlq_")
    yield wal_dir, dlq_dir
    shutil.rmtree(wal_dir, ignore_errors=True)
    shutil.rmtree(dlq_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_wal_local_persistence_before_flush(temp_storage):
    """Verify that every event is durably written to disk WAL immediately upon add_event."""
    wal_dir, dlq_dir = temp_storage
    mock_redis = MockRedisStream()

    buffer = IngestBuffer(
        batch_size=100,
        flush_interval_seconds=1.0,  # Long window to inspect WAL before worker flushes
        wal_dir=wal_dir,
        dlq_dir=dlq_dir,
        redis_client=mock_redis,
    )
    buffer.start()

    try:
        # Add 5 events
        for i in range(5):
            await buffer.add_event(json.dumps({"event_id": f"evt-{i}", "item": "scanner_read"}))

        # Inspect WAL directory immediately
        wal_files = list(buffer.wal_manager.wal_dir.glob("wal_*.jsonl"))
        assert len(wal_files) >= 1

        # Verify disk contents contain all 5 events
        total_wal_lines = 0
        for wf in wal_files:
            total_wal_lines += len([line for line in wf.read_text().splitlines() if line.strip()])
        assert total_wal_lines == 5

    finally:
        await buffer.stop()


@pytest.mark.asyncio
async def test_crash_recovery_1000_events(temp_storage):
    """
    Simulate sudden Pod crash / OOM kill while 1,000 events are queued in RAM.
    When service restarts, 100% of the 1,000 events must be recovered from WAL
    and delivered to Redis Streams without losing a single event.
    """
    wal_dir, dlq_dir = temp_storage
    mock_redis = MockRedisStream()

    # 1. Pod 1: Receives 1,000 events but is abruptly halted before flushing to Redis
    pod1_buffer = IngestBuffer(
        batch_size=10000,  # High batch size so it doesn't flush immediately
        flush_interval_seconds=10.0,
        wal_dir=wal_dir,
        dlq_dir=dlq_dir,
        redis_client=mock_redis,
    )
    # Note: We do NOT start background worker to simulate crash right after ingest
    pod1_buffer.running = True

    for i in range(1000):
        await pod1_buffer.add_event(
            json.dumps({"seq_num": i, "barcode": f"893123456{i:04d}", "scanner_id": "RF-HANDHELD-01"})
        )

    # Simulate abrupt SIGKILL / Pod crash: No graceful stop, worker killed, memory wiped
    pod1_buffer.wal_manager.close()
    assert len(mock_redis.stored_events) == 0  # Nothing was sent to Redis yet

    # 2. Pod 2 (Restart): IngestBuffer starts up on the same persistent WAL storage
    pod2_buffer = IngestBuffer(
        batch_size=50,
        flush_interval_seconds=0.01,
        wal_dir=wal_dir,
        dlq_dir=dlq_dir,
        redis_client=mock_redis,
    )
    pod2_buffer.start()

    # Wait for micro-batch worker to flush all recovered events
    timeout = 5.0
    start = time.time()
    while len(mock_redis.stored_events) < 1000 and (time.time() - start) < timeout:
        await asyncio.sleep(0.05)

    await pod2_buffer.stop()

    # Acceptance Criteria verification: 100% of 1,000 events recovered
    assert len(mock_redis.stored_events) == 1000, f"Expected 1000 recovered events, got {len(mock_redis.stored_events)}"
    
    # Verify all sequence numbers from 0 to 999 are present
    recovered_seqs = set()
    for raw in mock_redis.stored_events:
        data = json.loads(raw)
        recovered_seqs.add(data["seq_num"])
    assert len(recovered_seqs) == 1000
    assert min(recovered_seqs) == 0
    assert max(recovered_seqs) == 999


@pytest.mark.asyncio
async def test_redis_failure_writes_to_dlq(temp_storage):
    """
    Verify that when Redis fails, the batch is NEVER dropped silently.
    It must be written immediately to storage/dlq/events_failed_*.jsonl.
    """
    wal_dir, dlq_dir = temp_storage
    failing_redis = MockRedisStream(should_fail=True)

    buffer = IngestBuffer(
        batch_size=10,
        flush_interval_seconds=0.01,
        wal_dir=wal_dir,
        dlq_dir=dlq_dir,
        redis_client=failing_redis,
    )
    buffer.start()

    try:
        # Ingest 25 events
        for i in range(25):
            await buffer.add_event(json.dumps({"id": i, "payload": "critical_barcode"}))

        # Wait for flush attempts
        await asyncio.sleep(0.2)

        # Check DLQ directory
        dlq_files = buffer.dlq_manager.list_dlq_files()
        assert len(dlq_files) >= 1, "Expected DLQ files to be created on Redis failure"

        total_dlq_events = 0
        for df in dlq_files:
            events = buffer.dlq_manager.read_dlq_events(df)
            total_dlq_events += len(events)

        assert total_dlq_events == 25, f"Expected all 25 failed events in DLQ, found {total_dlq_events}"

    finally:
        await buffer.stop()


@pytest.mark.asyncio
async def test_dlq_retry_worker_recovers_when_redis_heals(temp_storage):
    """
    Verify that the Background Retry Worker automatically scans DLQ,
    re-dispatches events when Redis recovers, and cleans up DLQ files.
    """
    wal_dir, dlq_dir = temp_storage
    mock_redis = MockRedisStream(should_fail=True)

    buffer = IngestBuffer(
        batch_size=10,
        flush_interval_seconds=0.01,
        dlq_retry_interval=0.05,
        wal_dir=wal_dir,
        dlq_dir=dlq_dir,
        redis_client=mock_redis,
    )
    buffer.start()

    try:
        # 1. Send 15 events while Redis is down
        for i in range(15):
            await buffer.add_event(json.dumps({"order_id": f"ORD-{i}"}))

        await asyncio.sleep(0.2)
        assert len(buffer.dlq_manager.list_dlq_files()) > 0
        assert len(mock_redis.stored_events) == 0

        # 2. Redis recovers!
        mock_redis.should_fail = False

        # Wait for DLQ worker to retry and succeed
        timeout = 5.0
        start = time.time()
        while len(mock_redis.stored_events) < 15 and (time.time() - start) < timeout:
            await asyncio.sleep(0.1)

        # Verify DLQ files have been cleared and all events are now in Redis
        assert len(mock_redis.stored_events) == 15
        remaining_dlq = buffer.dlq_manager.list_dlq_files()
        assert len(remaining_dlq) == 0, f"DLQ files should be removed after recovery, but found: {remaining_dlq}"

    finally:
        await buffer.stop()
