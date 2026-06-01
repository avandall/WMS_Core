from __future__ import annotations

import json
from pathlib import Path

from shared_utils.events import EventEnvelope, build_event


ROOT_DIR = Path(__file__).resolve().parents[2]
FIXTURES = ROOT_DIR / "tests/fixtures/event_contracts.json"


def _event_contracts() -> dict:
    return json.loads(FIXTURES.read_text())


def _published_events_from_docs() -> set[str]:
    events = set()
    in_section = False
    for line in (ROOT_DIR / "docs/events.md").read_text().splitlines():
        if line == "## Published Events":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- `"):
            events.add(line.split("`", 2)[1])
    return events


def test_event_fixtures_cover_every_published_event() -> None:
    contracts = _event_contracts()

    assert set(contracts) == _published_events_from_docs()


def test_event_fixtures_have_required_envelope_and_payload_fields() -> None:
    for event_type, contract in _event_contracts().items():
        payload = dict(contract["fixture_payload"])
        envelope = build_event(
            source=contract["source"],
            event_type=event_type,
            payload=payload,
        )

        assert envelope.event_id == payload["event_id"]
        assert envelope.schema_version == 1
        assert envelope.source == contract["source"]
        assert envelope.type == event_type
        for field in contract["required_payload"]:
            assert field in envelope.payload, f"{event_type} missing {field}"


def test_event_envelope_tolerates_additive_fields_and_older_schema_versions() -> None:
    raw = json.dumps(
        {
            "event_id": "fixture:older-event",
            "schema_version": 0,
            "occurred_at": "2026-05-26T00:00:00+00:00",
            "source": "documents-service",
            "type": "DocumentUploaded",
            "payload": {
                "entity_type": "document",
                "entity_id": 1,
                "document_id": 1,
                "doc_type": "IMPORT",
                "status": "DRAFT",
                "items": [],
                "new_optional_field": "safe-to-ignore",
            },
            "new_top_level_field": "safe-to-ignore",
        }
    )

    envelope = EventEnvelope.from_json(raw)

    assert envelope.schema_version == 0
    assert envelope.payload["new_optional_field"] == "safe-to-ignore"


def test_consumers_encode_duplicate_event_id_and_replay_tolerance() -> None:
    audit_model = (
        ROOT_DIR / "Services/audit-service/src/app/modules/audit/infrastructure/models/audit_event.py"
    ).read_text()
    audit_repo = (
        ROOT_DIR
        / "Services/audit-service/src/app/modules/audit/infrastructure/repositories/audit_event_repo.py"
    ).read_text()
    audit_consumer = (ROOT_DIR / "Services/audit-service/src/audit_service/event_consumer.py").read_text()
    reporting_repo = (
        ROOT_DIR
        / "Services/reporting-service/src/app/modules/reporting/infrastructure/repositories/read_model_repo.py"
    ).read_text()
    replay_tool = (ROOT_DIR / "scripts/replay_events.py").read_text()

    assert "event_id = Column" in audit_model
    assert "unique=True" in audit_model
    assert "def get_by_event_id" in audit_repo
    assert "Skipping duplicate audit event" in audit_repo
    assert "event_id=envelope.event_id" in audit_consumer
    assert "ReportingReadModelEvent.event_id == envelope.event_id" in reporting_repo
    assert "return False" in reporting_repo
    assert "replay_of_event_id" in replay_tool
    assert "seen_event_ids" in replay_tool


def test_event_docs_define_breaking_change_policy() -> None:
    docs = (ROOT_DIR / "docs/events.md").read_text()

    assert "Breaking Change Policy" in docs
    assert "Additive fields" in docs
    assert "new event type" in docs
    assert "schema_version" in docs
