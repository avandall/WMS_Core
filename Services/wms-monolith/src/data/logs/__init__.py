"""
Data layer for WMS application.

Contains seed data and log management functionality.
"""

from .log_manager import LogManager, setup_logging_with_cleanup

__all__ = [
    "LogManager",
    "setup_logging_with_cleanup",
]
