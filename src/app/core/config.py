"""Legacy core configuration helper.

This module exposes the shared settings instance for compatibility
with legacy import paths.
"""

from app.core.settings import settings

__all__ = ["settings"]
