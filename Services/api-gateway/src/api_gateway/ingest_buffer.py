import asyncio
import time
import logging
from typing import Any

logger = logging.getLogger("api_gateway.ingest_buffer")

class IngestBuffer:
    def __init__(self, batch_size: int = 100, flush_interval_seconds: float = 0.020, max_queue_size: int = 50000):
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.worker_task = None
        self.running = False

    def start(self):
        if not self.running:
            self.running = True
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("IngestBuffer background worker started.")

    async def stop(self):
        if self.running:
            self.running = False
            logger.info("Stopping IngestBuffer worker and flushing remaining events...")
            if self.worker_task:
                self.worker_task.cancel()
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass
            # Flush any remaining items in the queue
            await self._flush_remaining()
            logger.info("IngestBuffer worker stopped.")

    async def add_event(self, event_json: str):
        # Push event to queue. It is non-blocking if queue is not full.
        # If queue is full under extreme load, block to apply backpressure.
        await self.queue.put(event_json)

    async def _worker(self):
        while self.running:
            try:
                # 1. Block until at least one event is available
                item = await self.queue.get()
                batch = [item]
                self.queue.task_done()
                
                # 2. Yield control to let other requests populate the queue during the window
                await asyncio.sleep(self.flush_interval_seconds)
                
                # 3. Drain all accumulated events from the queue
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
                await asyncio.sleep(0.1) # Prevent hot loop on errors

    async def _flush(self, batch: list[str]):
        if not batch:
            return
        from api_gateway.routes import redis_pool, EVENT_STREAM
        start_time = time.monotonic()
        try:
            await redis_pool.xadd_batch(EVENT_STREAM, batch)
            elapsed = (time.monotonic() - start_time) * 1000.0
            logger.info(f"Flushed batch of {len(batch)} events in {elapsed:.2f} ms")
        except Exception as e:
            logger.error(f"Failed to flush batch of {len(batch)} events to Redis: {e}")
            # Fallback to single publish if batch fails
            try:
                from shared_utils.events import get_publisher
                publisher = get_publisher("api-gateway")
                for payload_str in batch:
                    # Decode to publish if using get_publisher (expects dict)
                    import json
                    try:
                        data = json.loads(payload_str)
                        # Extract payload if it was wrapped or publish it directly
                        publisher.publish(event_type="InventoryIngested", payload=data.get("payload", data))
                    except Exception:
                        pass
            except Exception as fe:
                logger.error(f"Fallback publishing failed: {fe}")

    async def _flush_remaining(self):
        batch = []
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

# Single global instance of IngestBuffer
ingest_buffer = IngestBuffer()
