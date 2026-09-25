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
from unittest.mock import AsyncMock, patch
import pytest

from api_gateway.ingest_buffer import (
    IngestBuffer,
    WalManager,
    DLQManager,
    WalThresholdExceededError,
    MAX_WAL_SIZE_MB,
)


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


@pytest.mark.asyncio
async def test_wal_fsync_durability_called(temp_storage):
    """
    Verify TECH-03: WalManager.append() must synchronously invoke os.fsync(fd)
    after handle.flush() to guarantee durable physical write to SSD before sequence commit.
    """
    wal_dir, dlq_dir = temp_storage
    wal_mgr = WalManager(wal_dir=wal_dir)

    try:
        with patch("os.fsync") as mock_fsync:
            seq1 = await wal_mgr.append(json.dumps({"evt": "fsync_test_1"}))
            assert seq1 >= 0
            assert mock_fsync.called
            assert mock_fsync.call_count == 1

            seq2 = await wal_mgr.append(json.dumps({"evt": "fsync_test_2"}))
            assert seq2 == seq1 + 1
            assert mock_fsync.call_count == 2
    finally:
        wal_mgr.close()


@pytest.mark.asyncio
async def test_wal_get_total_size_bytes(temp_storage):
    """
    Verify calculation of total disk bytes across all WAL files in wal_dir.
    """
    wal_dir, dlq_dir = temp_storage
    buffer = IngestBuffer(wal_dir=wal_dir, dlq_dir=dlq_dir)
    try:
        # Initially empty (or just checkpoint)
        initial_size = buffer.get_total_wal_size_bytes()
        assert initial_size >= 0

        # Add events and assert size strictly increases
        for i in range(10):
            await buffer.ingest(json.dumps({"test_id": i, "data": "x" * 200}))

        new_size = buffer.get_total_wal_size_bytes()
        assert new_size > initial_size
        assert buffer.wal_manager.get_total_wal_size_bytes() == new_size
    finally:
        await buffer.stop()


@pytest.mark.asyncio
async def test_circuit_breaker_tripped_on_wal_threshold(temp_storage, caplog):
    """
    Verify MED-09: When WAL size exceeds MAX_WAL_SIZE_MB:
    1. Circuit breaker trips.
    2. Event is rejected with WalThresholdExceededError (or -1 if raise_on_error=False).
    3. Log warning level CRITICAL: 'WAL disk threshold exceeded, circuit breaker tripped'.
    4. Rejected event is immediately diverted to Emergency DLQ to prevent data loss.
    """
    wal_dir, dlq_dir = temp_storage
    mock_redis = MockRedisStream()

    # Configure small max_wal_size_mb (e.g. 1MB = 1024*1024 bytes)
    buffer = IngestBuffer(
        wal_dir=wal_dir,
        dlq_dir=dlq_dir,
        max_wal_size_mb=1,
        redis_client=mock_redis,
    )
    buffer.start()

    try:
        assert not buffer.circuit_breaker_tripped

        # Artificially simulate disk usage exceeding 1MB limit by creating a dummy WAL file
        large_file = buffer.wal_manager.wal_dir / "wal_overflow_dummy.jsonl"
        with open(large_file, "wb") as f:
            f.seek(1024 * 1024 + 10)  # > 1MB
            f.write(b"\0")

        # Now circuit breaker must be tripped
        assert buffer.circuit_breaker_tripped

        # 1. Ingest with raise_on_error=True (default) must raise WalThresholdExceededError
        with pytest.raises(WalThresholdExceededError, match="WAL disk threshold exceeded, circuit breaker tripped"):
            await buffer.ingest(json.dumps({"event": "emergency_payload_1"}))

        # 2. Ingest with raise_on_error=False must return -1
        res = await buffer.ingest(json.dumps({"event": "emergency_payload_2"}), raise_on_error=False)
        assert res == -1

        # 3. Check that CRITICAL log was emitted
        assert any("WAL disk threshold exceeded, circuit breaker tripped" in record.message for record in caplog.records)

        # 4. Check that both emergency events were preserved in Emergency DLQ
        dlq_files = buffer.dlq_manager.list_dlq_files()
        assert len(dlq_files) >= 1
        dlq_events = []
        for df in dlq_files:
            dlq_events.extend(buffer.dlq_manager.read_dlq_events(df))
        assert any("emergency_payload_1" in evt for evt in dlq_events)
        assert any("emergency_payload_2" in evt for evt in dlq_events)

    finally:
        await buffer.stop()


@pytest.mark.asyncio
async def test_high_load_durability_bounded_retention(temp_storage):
    """
    Simulate high load (1,500 events) under abrupt shutdown and verify bounded storage & full recovery.
    """
    wal_dir, dlq_dir = temp_storage
    mock_redis = MockRedisStream()

    # Stage 1: Send 1,500 events without flushing
    pod1 = IngestBuffer(
        batch_size=5000,
        flush_interval_seconds=10.0,
        wal_dir=wal_dir,
        dlq_dir=dlq_dir,
        redis_client=mock_redis,
    )
    pod1.running = True

    for i in range(1500):
        await pod1.ingest(json.dumps({"load_id": i, "scanner": "HANDHELD-Z9"}))

    # Crash pod abruptly
    pod1.wal_manager.close()
    assert len(mock_redis.stored_events) == 0

    # Stage 2: Restart pod on the same WAL directory
    pod2 = IngestBuffer(
        batch_size=100,
        flush_interval_seconds=0.01,
        wal_dir=wal_dir,
        dlq_dir=dlq_dir,
        redis_client=mock_redis,
    )
    pod2.start()

    timeout = 8.0
    start = time.time()
    while len(mock_redis.stored_events) < 1500 and (time.time() - start) < timeout:
        await asyncio.sleep(0.05)

    await pod2.stop()

    # Verify 100% of 1,500 events recovered
    assert len(mock_redis.stored_events) == 1500
    recovered_ids = {json.loads(e)["load_id"] for e in mock_redis.stored_events}
    assert len(recovered_ids) == 1500


def test_cross_platform_wal_file_lock_contention(temp_storage, caplog):
    """
    TASK-071 (TECH-01): Verify that when a WAL segment is locked by another process
    (e.g., Windows WinError 32 PermissionError), cleanup_committed_files() gracefully
    handles the error without crashing, logs a warning, and retries/cleans up on the next cycle.
    """
    wal_dir, _ = temp_storage
    wal_mgr = WalManager(wal_dir=wal_dir)

    # 1. Create an old WAL segment file with committed events
    old_wal = wal_mgr.wal_dir / "wal_20260101_000000_old.jsonl"
    with open(old_wal, "w", encoding="utf-8") as f:
        f.write(json.dumps({"seq": 1, "data": '{"test": 1}'}) + "\n")
        f.write(json.dumps({"seq": 2, "data": '{"test": 2}'}) + "\n")

    # Set checkpoint committed_seq to 10 (> 2) so old_wal is eligible for cleanup
    wal_mgr.commit(10)
    assert old_wal.exists()

    # 2. Simulate Windows file lock contention (PermissionError: [WinError 32])
    with patch("pathlib.Path.unlink", side_effect=PermissionError("[WinError 32] The process cannot access the file")):
        import logging
        with caplog.at_level(logging.WARNING):
            # Must NOT raise PermissionError or crash
            wal_mgr.cleanup_committed_files()

        # Check warning log was emitted
        assert any(
            "Cross-platform file lock contention on WAL segment" in record.message
            for record in caplog.records
        )
        # File still exists because unlink failed gracefully
        assert old_wal.exists()

    # 3. Next cycle without lock contention: segment is successfully cleaned up
    wal_mgr.cleanup_committed_files()
    assert not old_wal.exists()

