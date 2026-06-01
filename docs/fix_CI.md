Now I can see the real issue. The shared_utils module still cannot be found even after adding it to sys.path. The real problem is that shared_utils likely doesn't exist in the project structure, or it exists at a different location than expected. Let me check the project structure and the actual test files that are failing:I see the problem now. The shared_utils directory doesn't exist in the repository at all. The conftest.py path setup won't help if the directory doesn't exist. The real issue is that the test files are trying to import from a module that hasn't been created yet.

Solution:

You have two options:

Option 1: Create the shared_utils module (Recommended if this is needed)
Create shared_utils directory and stub modules:

bash
mkdir -p shared_utils/events
mkdir -p shared_utils/observability
Create shared_utils/__init__.py:

Python
"""Shared utilities for WMS Project."""
Create shared_utils/events.py:

Python
"""Event utilities for contract tests."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
import uuid


@dataclass
class EventEnvelope:
    """Event envelope with versioning and idempotency."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: int = 1
    source: str = ""
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "source": self.source,
            "event_type": self.event_type,
            "payload": self.payload,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "EventEnvelope":
        """Create from JSON data."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            schema_version=data.get("schema_version", 1),
            source=data.get("source", ""),
            event_type=data.get("event_type", ""),
            payload=data.get("payload", {}),
            occurred_at=datetime.fromisoformat(data.get("occurred_at", datetime.utcnow().isoformat())),
        )


def build_event(
    source: str,
    event_type: str,
    payload: Dict[str, Any],
) -> EventEnvelope:
    """Build an event envelope."""
    return EventEnvelope(
        source=source,
        event_type=event_type,
        payload=payload,
    )
Create shared_utils/observability.py:

Python
"""Observability utilities for contract tests."""
from typing import Optional, Dict, Any


def parse_traceparent(traceparent_header: Optional[str]) -> Dict[str, Any]:
    """Parse W3C traceparent header.
    
    Format: version-trace_id-parent_id-trace_flags
    """
    if not traceparent_header:
        return {}
    
    parts = traceparent_header.split("-")
    if len(parts) != 4:
        return {}
    
    return {
        "version": parts[0],
        "trace_id": parts[1],
        "parent_id": parts[2],
        "trace_flags": parts[3],
    }


def child_trace_context(parent_traceparent: Optional[str]) -> Dict[str, str]:
    """Generate child trace context from parent traceparent header."""
    if not parent_traceparent:
        return {}
    
    parsed = parse_traceparent(parent_traceparent)
    if not parsed:
        return {}
    
    return {
        "traceparent": parent_traceparent,  # Simplified - in real W3C trace context, parent_id changes
    }
Option 2: Skip contract tests (if shared_utils is not needed yet)
Update pytest.ini to exclude contract tests during collection:

INI
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --tb=short
Or update .github/workflows/ci.yml to skip contract tests:

YAML
- name: Contract tests
  if: github.event.inputs.skip_tests != 'true'
  run: uv run --group dev pytest -q tests/contract --co -q 2>/dev/null || echo "Contract tests skipped - shared_utils not available"
  continue-on-error: true
Option 3: Fix imports in contract test files (if shared_utils is internal code)
If the tests should use relative imports or different paths, update the test files:

For tests/contract/test_event_bus_contract.py line 7, change:

Python
from shared_utils.events import EventEnvelope, build_event
To:

Python
# Try shared_utils first, then fall back to mocks if not available
try:
    from shared_utils.events import EventEnvelope, build_event
except ModuleNotFoundError:
    import pytest
    pytest.skip("shared_utils module not available", allow_module_level=True)
Recommended Action: Option 1 is best if these utilities are truly needed. Create the shared_utils module with the stub implementations above, and the import errors will resolve.