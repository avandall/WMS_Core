from __future__ import annotations

import argparse
from dataclasses import replace

from shared_utils.events import EventEnvelope, RedisStreamClient


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Redis Stream events with idempotency visibility.")
    parser.add_argument("--event-bus-url", required=True)
    parser.add_argument("--stream", default="wms.events")
    parser.add_argument("--from-id", default="0-0")
    parser.add_argument("--to-id", default="")
    parser.add_argument("--target-stream", default="wms.events.replay")
    parser.add_argument("--event-type", default="")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _in_range(message_id: str, to_id: str) -> bool:
    if not to_id:
        return True
    return tuple(int(part) for part in message_id.split("-")) <= tuple(int(part) for part in to_id.split("-"))


def replay_events(
    *,
    client: RedisStreamClient,
    stream: str,
    from_id: str,
    to_id: str,
    target_stream: str,
    event_type: str,
    count: int,
    dry_run: bool,
) -> dict[str, int]:
    last_id = from_id
    replayed = 0
    skipped = 0
    duplicates = 0
    seen_event_ids: set[str] = set()

    while True:
        rows = client.xread(stream, last_id, block_ms=1, count=count)
        if not rows:
            break
        for message_id, envelope in rows:
            last_id = message_id
            if not _in_range(message_id, to_id):
                return {"replayed": replayed, "skipped": skipped, "duplicates": duplicates}
            if event_type and envelope.type != event_type:
                skipped += 1
                continue
            if envelope.event_id in seen_event_ids:
                duplicates += 1
                skipped += 1
                continue
            seen_event_ids.add(envelope.event_id)
            replay_payload = dict(envelope.payload)
            replay_payload.update(
                {
                    "replay_of_event_id": envelope.event_id,
                    "replay_of_stream": stream,
                    "replay_of_stream_id": message_id,
                }
            )
            replay_envelope = replace(envelope, payload=replay_payload)
            if not dry_run:
                client.xadd(target_stream, replay_envelope)
            replayed += 1

    return {"replayed": replayed, "skipped": skipped, "duplicates": duplicates}


def main() -> None:
    args = _parse_args()
    result = replay_events(
        client=RedisStreamClient(args.event_bus_url),
        stream=args.stream,
        from_id=args.from_id,
        to_id=args.to_id,
        target_stream=args.target_stream,
        event_type=args.event_type,
        count=args.count,
        dry_run=args.dry_run,
    )
    print(result)


if __name__ == "__main__":
    main()
