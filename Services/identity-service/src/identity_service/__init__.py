from __future__ import annotations

import sys
from pathlib import Path

_gen_path = Path(__file__).resolve().parent / "gen"
if str(_gen_path) not in sys.path:
    sys.path.insert(0, str(_gen_path))

__all__ = ["create_app"]

from .app import create_app
