from __future__ import annotations

import sys
from pathlib import Path

from shared_utils.service_bootstrap import fixtures_service, migrate_service

_src_path = Path(__file__).resolve().parents[1]
while str(_src_path) in sys.path:
    sys.path.remove(str(_src_path))
sys.path.insert(0, str(_src_path))


def migrate() -> None:
    migrate_service("warehouse")


def fixtures() -> None:
    fixtures_service("warehouse")
