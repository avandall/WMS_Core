from __future__ import annotations

import json
import os
import socket
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlparse


class EventPublisher(Protocol):
    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None: ...


@dataclass(slots=True)
class EventEnvelope:
    event_id: str
    schema_version: int
    occurred_at: str
    source: str
    type: str
    payload: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> "EventEnvelope":
        data = json.loads(raw)
        return cls(
            event_id=str(data["event_id"]),
            schema_version=int(data["schema_version"]),
            occurred_at=str(data["occurred_at"]),
            source=str(data["source"]),
            type=str(data["type"]),
            payload=dict(data.get("payload") or {}),
        )


def build_event(*, source: str, event_type: str, payload: dict[str, Any]) -> EventEnvelope:
    return EventEnvelope(
        event_id=str(payload.get("event_id") or uuid.uuid4()),
        schema_version=1,
        occurred_at=datetime.now(tz=timezone.utc).isoformat(),
        source=source,
        type=event_type,
        payload=payload,
    )


class NoopEventPublisher:
    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        return None


@dataclass(slots=True)
class StdoutEventPublisher:
    service: str

    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        print(build_event(source=self.service, event_type=event_type, payload=payload).to_json())


class RedisProtocolError(RuntimeError):
    pass


class RedisStreamClient:
    def __init__(self, url: str, *, timeout: float = 2.0):
        parsed = urlparse(url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.db = int((parsed.path or "/0").lstrip("/") or "0")
        self.timeout = timeout

    @staticmethod
    def _encode_command(*parts: object) -> bytes:
        encoded = [str(part).encode("utf-8") for part in parts]
        chunks = [f"*{len(encoded)}\r\n".encode("ascii")]
        for item in encoded:
            chunks.append(f"${len(item)}\r\n".encode("ascii"))
            chunks.append(item)
            chunks.append(b"\r\n")
        return b"".join(chunks)

    def execute(self, *parts: object) -> Any:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            if self.db:
                sock.sendall(self._encode_command("SELECT", self.db))
                self._read_response(sock)
            sock.sendall(self._encode_command(*parts))
            return self._read_response(sock)

    def xadd(self, stream: str, envelope: EventEnvelope) -> str:
        result = self.execute("XADD", stream, "*", "event", envelope.to_json())
        return str(result)

    def xlen(self, stream: str) -> int:
        result = self.execute("XLEN", stream)
        return int(result or 0)

    def xread(self, stream: str, last_id: str, *, block_ms: int, count: int) -> list[tuple[str, EventEnvelope]]:
        result = self.execute("XREAD", "COUNT", count, "BLOCK", block_ms, "STREAMS", stream, last_id)
        if result is None:
            return []

        events: list[tuple[str, EventEnvelope]] = []
        for stream_rows in result:
            if not stream_rows or len(stream_rows) < 2:
                continue
            for row in stream_rows[1]:
                message_id = str(row[0])
                fields = row[1]
                field_map = {
                    str(fields[i]): str(fields[i + 1])
                    for i in range(0, len(fields), 2)
                    if i + 1 < len(fields)
                }
                raw_event = field_map.get("event")
                if raw_event:
                    events.append((message_id, EventEnvelope.from_json(raw_event)))
        return events

    def _read_line(self, sock: socket.socket) -> bytes:
        data = bytearray()
        while not data.endswith(b"\r\n"):
            chunk = sock.recv(1)
            if not chunk:
                raise RedisProtocolError("Unexpected Redis connection close")
            data.extend(chunk)
        return bytes(data[:-2])

    def _read_response(self, sock: socket.socket) -> Any:
        prefix = sock.recv(1)
        if not prefix:
            raise RedisProtocolError("Empty Redis response")
        if prefix == b"+":
            return self._read_line(sock).decode("utf-8")
        if prefix == b"-":
            raise RedisProtocolError(self._read_line(sock).decode("utf-8"))
        if prefix == b":":
            return int(self._read_line(sock))
        if prefix == b"$":
            length = int(self._read_line(sock))
            if length == -1:
                return None
            data = bytearray()
            while len(data) < length:
                data.extend(sock.recv(length - len(data)))
            trailer = sock.recv(2)
            if trailer != b"\r\n":
                raise RedisProtocolError("Invalid bulk string terminator")
            return bytes(data).decode("utf-8")
        if prefix == b"*":
            length = int(self._read_line(sock))
            if length == -1:
                return None
            return [self._read_response(sock) for _ in range(length)]
        raise RedisProtocolError(f"Unknown Redis response prefix: {prefix!r}")


@dataclass(slots=True)
class RedisStreamEventPublisher:
    service: str
    stream: str
    client: RedisStreamClient
    fallback: EventPublisher

    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        envelope = build_event(source=self.service, event_type=event_type, payload=payload)
        try:
            self.client.xadd(self.stream, envelope)
        except Exception:
            self.fallback.publish(event_type=event_type, payload=payload)


def get_publisher(service: str) -> EventPublisher:
    if os.getenv("EVENTS_ENABLED", "1") != "1":
        return NoopEventPublisher()

    event_bus_url = os.getenv("EVENT_BUS_URL", "")
    stream = os.getenv("EVENT_STREAM", "wms.events")
    stdout = StdoutEventPublisher(service=service)
    if not event_bus_url:
        return stdout
    return RedisStreamEventPublisher(
        service=service,
        stream=stream,
        client=RedisStreamClient(event_bus_url),
        fallback=stdout,
    )
