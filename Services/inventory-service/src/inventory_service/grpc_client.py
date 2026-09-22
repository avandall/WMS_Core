from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from shared_utils.security import configured_grpc_channel
from inventory_service.gen.wms.documents.v1 import documents_pb2_grpc


def get_documents_grpc_addr() -> str:
    return os.getenv("DOCUMENTS_GRPC_ADDR", "localhost:50056")


@contextmanager
def get_documents_stub() -> Iterator[documents_pb2_grpc.DocumentsServiceStub]:
    addr = get_documents_grpc_addr()
    channel = configured_grpc_channel(addr)
    try:
        yield documents_pb2_grpc.DocumentsServiceStub(channel)
    finally:
        channel.close()
