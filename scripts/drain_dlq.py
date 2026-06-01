from __future__ import annotations

import argparse
from dataclasses import replace

from shared_utils.events import RedisStreamClient


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drain a service DLQ stream into a replay stream.")
    parser.add_argument("--event-bus-url", required=True)
    parser.add_argument("--dlq-stream", required=True)
    parser.add_argument("--target-stream", default="wms.events.replay")
    parser.add_argument("--from-id", default="0-0")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def drain_dlq(
    *,
    client: RedisStreamClient,
    dlq_stream: str,
    target_stream: str,
    from_id: str,
    count: int,
    dry_run: bool,
) -> dict[str, int]:
    drained = 0
    last_id = from_id

    while True:
        rows = client.xread(dlq_stream, last_id, block_ms=1, count=count)
        if not rows:
            break
        for message_id, envelope in rows:
            last_id = message_id
            payload = dict(envelope.payload)
            payload.update(
                {
                    "replay_of_event_id": envelope.event_id,
                    "replay_of_dlq_stream": dlq_stream,
                    "replay_of_dlq_stream_id": message_id,
                }
            )
            if not dry_run:
                client.xadd(target_stream, replace(envelope, payload=payload))
            drained += 1

    return {"drained": drained}


def main() -> None:
    args = _parse_args()
    result = drain_dlq(
        client=RedisStreamClient(args.event_bus_url),
        dlq_stream=args.dlq_stream,
        target_stream=args.target_stream,
        from_id=args.from_id,
        count=args.count,
        dry_run=args.dry_run,
    )
    print(result)


if __name__ == "__main__":
    main()
