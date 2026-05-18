"""Centralized logging configuration for the WMS application."""

import logging
import sys
from typing import Optional
from contextvars import ContextVar

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class ContextualFormatter(logging.Formatter):
    def format(self, record):
        request_id = request_id_ctx.get()
        record.request_id = request_id if request_id else "N/A"
        return super().format(record)


def setup_logging(level: str = "INFO") -> None:
    log_format = (
        "%(asctime)s | %(levelname)-8s | [%(request_id)s] | "
        "%(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )
    formatter = ContextualFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_id(request_id: str) -> None:
    request_id_ctx.set(request_id)


def clear_request_id() -> None:
    request_id_ctx.set(None)
