from __future__ import annotations

import socket
import sys
from urllib.request import urlopen

import grpc


def check_http(url: str) -> int:
    with urlopen(url, timeout=2) as response:
        return 0 if 200 <= response.status < 400 else 1


def check_grpc(target: str) -> int:
    channel = grpc.insecure_channel(target)
    try:
        grpc.channel_ready_future(channel).result(timeout=2)
    except (grpc.FutureTimeoutError, socket.error):
        return 1
    finally:
        channel.close()
    return 0


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: docker_healthcheck.py <http|grpc> <target>", file=sys.stderr)
        return 2

    mode = sys.argv[1]
    target = sys.argv[2]

    if mode == "http":
        return check_http(target)
    if mode == "grpc":
        return check_grpc(target)

    print(f"unsupported healthcheck mode: {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
