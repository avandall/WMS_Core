"""Persistent Ingestion Buffer with Write-Ahead Logging (WAL) and Dead Letter Queue (DLQ).

Architectural Highlights (Twelve-Factor App & Clean Architecture):
- Attached Resources: Decoupled durability from Redis Streams availability.
- Stateless & Disposable: Survives sudden Pod crashes / OOM kills without data loss via Local Disk WAL.
- Dead Letter Queue: Eliminates silent failure anti-patterns ('except Exception: pass').
- Exponential Backoff & Jitter: Background retry worker gracefully re-injects failed batches when Redis recovers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("api_gateway.ingest_buffer")


class WalManager:
    """Manages local append-only Write-Ahead Logging (WAL) and checkpointing for ingest durability."""

    def __init__(self, wal_dir: Optional[str] = None):
        configured_dir = wal_dir or os.getenv("INGEST_WAL_DIR", "storage/wal")
        self.wal_dir = Path(configured_dir)
        self.wal_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.wal_dir / "wal.checkpoint"
        self._session_id = uuid.uuid4().hex[:8]
        self._current_seq = -1
        self._committed_seq = self._load_checkpoint()
        self._active_file_path = self.wal_dir / f"wal_{int(time.time())}_{self._session_id}.jsonl"
        self._file_handle = None
        self._lock = asyncio.Lock()
        self._init_current_seq()

    def _load_checkpoint(self) -> int:
        """Load the highest sequence number successfully flushed or transferred to DLQ."""
        if self.checkpoint_file.exists():
            try:
                data = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
                return int(data.get("committed_seq", -1))
            except Exception as e:
                logger.warning(f"Failed to read WAL checkpoint, defaulting to -1: {e}")
        return -1

    def _init_current_seq(self):
        """Initialize current_seq based on checkpoint and existing log entries."""
        max_seen = self._committed_seq
        for log_file in sorted(self.wal_dir.glob("wal_*.jsonl")):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            seq = int(record.get("seq", -1))
                            if seq > max_seen:
                                max_seen = seq
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.warning(f"Error scanning WAL file {log_file}: {e}")
        self._current_seq = max_seen

    def _get_file_handle(self):
        if self._file_handle is None or self._file_handle.closed:
            self._file_handle = open(self._active_file_path, "a", encoding="utf-8")
        return self._file_handle

    async def append(self, event_json: str) -> int:
        """Append an event to WAL file on disk synchronously flushed before returning."""
        async with self._lock:
            self._current_seq += 1
            seq = self._current_seq
            record = {"seq": seq, "data": event_json}
            line = json.dumps(record) + "\n"
            handle = self._get_file_handle()
            handle.write(line)
            handle.flush()
            return seq

    def commit(self, seq: int) -> None:
        """Atomically persist committed_seq checkpoint."""
        if seq <= self._committed_seq:
            return
        self._committed_seq = seq
        temp_file = self.wal_dir / f"checkpoint_{uuid.uuid4().hex}.tmp"
        try:
            temp_file.write_text(json.dumps({"committed_seq": self._committed_seq}), encoding="utf-8")
            temp_file.replace(self.checkpoint_file)
        except Exception as e:
            logger.error(f"Failed to write WAL checkpoint: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def recover_uncommitted(self) -> list[tuple[int, str]]:
        """Scan all WAL files and return all events with seq > committed_seq in sequential order."""
        uncommitted = {}
        for log_file in sorted(self.wal_dir.glob("wal_*.jsonl")):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            seq = int(record.get("seq", -1))
                            data = record.get("data", "")
                            if seq > self._committed_seq:
                                uncommitted[seq] = data
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.warning(f"Error reading WAL file {log_file} during recovery: {e}")

        # Return sorted by sequence number
        return [(seq, uncommitted[seq]) for seq in sorted(uncommitted.keys())]

    def cleanup_committed_files(self) -> None:
        """Remove WAL segment files whose records are all strictly <= committed_seq."""
        for log_file in sorted(self.wal_dir.glob("wal_*.jsonl")):
            # Don't delete the currently open active segment
            if log_file == self._active_file_path:
                continue
            try:
                all_committed = True
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            seq = int(record.get("seq", -1))
                            if seq > self._committed_seq:
                                all_committed = False
                                break
                        except json.JSONDecodeError:
                            continue
                if all_committed:
                    log_file.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup old WAL file {log_file}: {e}")

    def close(self):
        if self._file_handle and not self._file_handle.closed:
            try:
                self._file_handle.flush()
                self._file_handle.close()
            except Exception:
                pass


class DLQManager:
    """Manages Dead Letter Queue (DLQ) persistent storage on disk for failed event batches."""

    def __init__(self, dlq_dir: Optional[str] = None):
        configured_dir = dlq_dir or os.getenv("INGEST_DLQ_DIR", "storage/dlq")
        self.dlq_dir = Path(configured_dir)
        self.dlq_dir.mkdir(parents=True, exist_ok=True)

    def write_failed_batch(self, batch: list[str], error_message: str = "") -> str:
        """Write failed events immediately to a new DLQ file on disk."""
        if not batch:
            return ""
        timestamp_ms = int(time.time() * 1000)
        file_name = f"events_failed_{timestamp_ms}_{uuid.uuid4().hex[:8]}.jsonl"
        target_path = self.dlq_dir / file_name
        temp_path = self.dlq_dir / f"{file_name}.tmp"

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                for event_payload in batch:
                    entry = {
                        "failed_at": timestamp_ms,
                        "error": error_message,
                        "event": event_payload,
                    }
                    f.write(json.dumps(entry) + "\n")
                f.flush()
            temp_path.replace(target_path)
            logger.warning(f"DLQ: Preserved {len(batch)} failed events to {target_path}")
            return str(target_path)
        except Exception as e:
            logger.critical(f"FATAL: Failed to write DLQ file {target_path}: {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise

    def list_dlq_files(self) -> list[Path]:
        """List all pending failed event files sorted chronologically."""
        return sorted(self.dlq_dir.glob("events_failed_*.jsonl"))

    def read_dlq_events(self, file_path: Path) -> list[str]:
        """Read original event strings from a DLQ file."""
        events = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    events.append(data.get("event", ""))
                except json.JSONDecodeError:
                    continue
        return events

    def remove_dlq_file(self, file_path: Path) -> None:
        """Remove a DLQ file once its events are successfully re-dispatched."""
        try:
            file_path.unlink(missing_ok=True)
            logger.info(f"DLQ: Successfully replayed and purged {file_path.name}")
        except Exception as e:
            logger.warning(f"Failed to remove DLQ file {file_path}: {e}")


class IngestBuffer:
    """High-throughput Ingestion Buffer with local WAL durability and DLQ replay worker."""

    def __init__(
        self,
        batch_size: Optional[int] = None,
        flush_interval_seconds: Optional[float] = None,
        max_queue_size: Optional[int] = None,
        wal_dir: Optional[str] = None,
        dlq_dir: Optional[str] = None,
        redis_client: Optional[Any] = None,
        dlq_retry_interval: Optional[float] = None,
    ):
        self.batch_size = batch_size or int(os.getenv("INGEST_BATCH_SIZE", "100"))
        self.flush_interval_seconds = (
            flush_interval_seconds if flush_interval_seconds is not None else float(os.getenv("INGEST_FLUSH_INTERVAL", "0.020"))
        )
        queue_size = max_queue_size or int(os.getenv("INGEST_MAX_QUEUE_SIZE", "50000"))
        self.queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue(maxsize=queue_size)
        self.wal_manager = WalManager(wal_dir=wal_dir)
        self.dlq_manager = DLQManager(dlq_dir=dlq_dir)
        self.redis_client = redis_client
        self.dlq_retry_interval = (
            dlq_retry_interval if dlq_retry_interval is not None else float(os.getenv("INGEST_DLQ_RETRY_INTERVAL", "2.0"))
        )
        self.max_backoff = float(os.getenv("INGEST_MAX_BACKOFF", "60.0"))

        self.worker_task: Optional[asyncio.Task] = None
        self.dlq_task: Optional[asyncio.Task] = None
        self.running = False

    def _get_redis(self):
        if self.redis_client is not None:
            return self.redis_client
        from api_gateway.routes import redis_pool
        return redis_pool

    def _get_stream(self) -> str:
        return os.getenv("EVENT_STREAM", "wms.events")

    def start(self):
        """Start micro-batch worker, DLQ retry worker, and perform Crash Recovery."""
        if not self.running:
            self.running = True
            # 1. Crash Recovery: Replay uncommitted WAL events
            self._recover_from_wal()
            # 2. Start background workers
            self.worker_task = asyncio.create_task(self._worker())
            self.dlq_task = asyncio.create_task(self._dlq_retry_worker())
            logger.info("IngestBuffer started with WAL & DLQ workers active.")

    def _recover_from_wal(self):
        """Synchronously load any uncommitted events from WAL and enqueue them for immediate processing."""
        uncommitted = self.wal_manager.recover_uncommitted()
        if uncommitted:
            logger.warning(f"Crash Recovery: Found {len(uncommitted)} uncommitted events in WAL. Restoring...")
            for seq, event_json in uncommitted:
                try:
                    self.queue.put_nowait((seq, event_json))
                except asyncio.QueueFull:
                    # If memory queue is full, process directly via DLQ or block
                    logger.critical("Memory queue full during WAL recovery, transferring batch to DLQ.")
                    self.dlq_manager.write_failed_batch([e for _, e in uncommitted], "Queue full on crash recovery")
                    self.wal_manager.commit(uncommitted[-1][0])
                    return
            logger.info(f"Crash Recovery: 100% of {len(uncommitted)} events restored into IngestBuffer.")

    async def stop(self):
        """Gracefully stop workers, flush remaining in-memory events, and close WAL handles."""
        if self.running:
            self.running = False
            logger.info("Stopping IngestBuffer worker and flushing remaining events...")
            if self.worker_task:
                self.worker_task.cancel()
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass
            if self.dlq_task:
                self.dlq_task.cancel()
                try:
                    await self.dlq_task
                except asyncio.CancelledError:
                    pass

            # Flush any remaining items in the queue
            await self._flush_remaining()
            self.wal_manager.close()
            logger.info("IngestBuffer worker stopped.")

    async def add_event(self, event_json: str) -> int:
        """Persist event to local disk WAL first, then place in memory buffer for micro-batching.
        
        Guarantees durability before returning 202 Accepted.
        """
        if isinstance(event_json, dict):
            event_json = json.dumps(event_json)

        # 1. Append to local disk WAL (Crash durability)
        seq = await self.wal_manager.append(event_json)

        # 2. Put into in-memory queue for high-throughput batching
        await self.queue.put((seq, event_json))
        return seq

    async def _worker(self):
        while self.running:
            try:
                # 1. Block until at least one event is available
                item = await self.queue.get()
                batch = [item]
                self.queue.task_done()

                # 2. Yield control to let other requests populate the queue during the window
                await asyncio.sleep(self.flush_interval_seconds)

                # 3. Drain all accumulated events from the queue up to batch_size
                while len(batch) < self.batch_size:
                    try:
                        item = self.queue.get_nowait()
                        batch.append(item)
                        self.queue.task_done()
                    except asyncio.QueueEmpty:
                        break

                # 4. Flush the batch
                await self._flush(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in IngestBuffer worker: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _flush(self, batch: list[tuple[int, str]]):
        if not batch:
            return
        payloads = [item[1] for item in batch]
        max_seq = max(item[0] for item in batch)
        redis_client = self._get_redis()
        stream_name = self._get_stream()

        start_time = time.monotonic()
        try:
            await redis_client.xadd_batch(stream_name, payloads)
            elapsed = (time.monotonic() - start_time) * 1000.0
            logger.info(f"Flushed batch of {len(payloads)} events to Redis in {elapsed:.2f} ms")
            # Commit checkpoint on disk WAL
            self.wal_manager.commit(max_seq)
            self.wal_manager.cleanup_committed_files()
        except Exception as e:
            logger.error(f"Failed to flush batch of {len(payloads)} events to Redis: {e}")
            # CRITICAL FIX [ING-02]: Never use except Exception: pass!
            # Persist batch immediately to Dead Letter Queue (DLQ)
            try:
                self.dlq_manager.write_failed_batch(payloads, error_message=str(e))
                # Now that DLQ has taken custody, advance WAL checkpoint
                self.wal_manager.commit(max_seq)
            except Exception as write_err:
                logger.critical(f"FATAL: Both Redis flush and DLQ write failed: {write_err}")

    async def _flush_remaining(self):
        batch: list[tuple[int, str]] = []
        while not self.queue.empty():
            try:
                item = self.queue.get_nowait()
                batch.append(item)
                self.queue.task_done()
                if len(batch) >= self.batch_size:
                    await self._flush(batch)
                    batch = []
            except asyncio.QueueEmpty:
                break
        if batch:
            await self._flush(batch)

    async def _dlq_retry_worker(self):
        """Background worker that continuously scans DLQ and retries Redis delivery with Exponential Backoff + Jitter."""
        consecutive_failures = 0
        base_interval = self.dlq_retry_interval

        while self.running:
            try:
                dlq_files = self.dlq_manager.list_dlq_files()
                if not dlq_files:
                    consecutive_failures = 0
                    await asyncio.sleep(base_interval)
                    continue

                redis_client = self._get_redis()
                stream_name = self._get_stream()

                for dlq_file in dlq_files:
                    if not self.running:
                        break
                    events = self.dlq_manager.read_dlq_events(dlq_file)
                    if not events:
                        self.dlq_manager.remove_dlq_file(dlq_file)
                        continue

                    try:
                        # Attempt to push to Redis
                        await redis_client.xadd_batch(stream_name, events)
                        # On success, delete DLQ file and reset failure counter
                        self.dlq_manager.remove_dlq_file(dlq_file)
                        consecutive_failures = 0
                        logger.info(f"DLQ Worker: Recovered {len(events)} events from {dlq_file.name}")
                    except Exception as exc:
                        consecutive_failures += 1
                        # Exponential backoff + Jitter calculation
                        delay = min(self.max_backoff, base_interval * (2 ** min(consecutive_failures, 6)))
                        jitter = random.uniform(0.1, 1.0)
                        backoff_time = delay + jitter
                        logger.warning(
                            f"DLQ Worker: Redis retry failed ({exc}). Backing off for {backoff_time:.2f}s "
                            f"(attempt #{consecutive_failures})"
                        )
                        await asyncio.sleep(backoff_time)
                        break  # Stop processing further files until Redis recovers

                await asyncio.sleep(base_interval)

            except asyncio.CancelledError:
                break
            except Exception as worker_err:
                logger.error(f"Unexpected error in DLQ retry worker: {worker_err}", exc_info=True)
                await asyncio.sleep(base_interval)


# Single global instance of IngestBuffer
ingest_buffer = IngestBuffer()
