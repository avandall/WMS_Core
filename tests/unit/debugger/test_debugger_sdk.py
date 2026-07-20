from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest

from shared_utils.debugger import DebuggerSettings, mask_payload, grpc_payload_debugger_interceptor


def test_debugger_settings_defaults():
    # Test default settings
    with patch.dict(os.environ, {}, clear=True):
        settings = DebuggerSettings.load_from_env()
        assert settings.enabled is False
        assert settings.exporter == "console"
        assert settings.collector_url == "http://otel-collector:4317"
        assert "password" in settings.mask_fields
        assert "token" in settings.mask_fields


def test_debugger_settings_from_env():
    # Test setting values via environment variables
    env = {
        "WMS_DEBUG_ENABLED": "true",
        "WMS_DEBUG_EXPORTER": "otlp",
        "WMS_DEBUG_COLLECTOR_URL": "http://localhost:5555",
        "WMS_DEBUG_MASK_FIELDS": "secret_key, api_key, authorization",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = DebuggerSettings.load_from_env()
        assert settings.enabled is True
        assert settings.exporter == "otlp"
        assert settings.collector_url == "http://localhost:5555"
        assert "secret_key" in settings.mask_fields
        assert "api_key" in settings.mask_fields
        assert "authorization" in settings.mask_fields
        assert "password" not in settings.mask_fields


def test_mask_payload_basic():
    # Test basic payload masking
    mask_fields = ["password", "token"]
    payload = {
        "username": "avandall",
        "password": "my_super_secret_password",
        "token": "secret_token_123",
        "data": {
            "nested_token": "another_token"
        }
    }
    masked = mask_payload(payload, mask_fields)
    assert masked["username"] == "avandall"
    assert masked["password"] == "[MASKED]"
    assert masked["token"] == "[MASKED]"
    # Nested token should not be masked unless explicitly added to mask_fields,
    # but let's test if nested fields with matched names are masked.
    payload_with_nested = {
        "username": "avandall",
        "nested": {
            "password": "nested_password",
            "token": "nested_token"
        }
    }
    masked_nested = mask_payload(payload_with_nested, mask_fields)
    assert masked_nested["nested"]["password"] == "[MASKED]"
    assert masked_nested["nested"]["token"] == "[MASKED]"


def test_mask_payload_case_insensitive():
    # Test case insensitivity in masking
    mask_fields = ["Password"]
    payload = {
        "PASSWORD": "123",
        "password": "456",
        "PassWord": "789",
    }
    masked = mask_payload(payload, mask_fields)
    assert masked["PASSWORD"] == "[MASKED]"
    assert masked["password"] == "[MASKED]"
    assert masked["PassWord"] == "[MASKED]"


def test_mask_payload_list():
    # Test list payloads masking
    mask_fields = ["password"]
    payload = [
        {"username": "user1", "password": "pwd"},
        {"username": "user2", "password": "pwd"}
    ]
    masked = mask_payload(payload, mask_fields)
    assert masked[0]["password"] == "[MASKED]"
    assert masked[1]["password"] == "[MASKED]"


@patch("shared_utils.debugger.grpc_interceptor.MessageToDict")
@patch("shared_utils.debugger.grpc_interceptor.debug_log")
@patch("shared_utils.debugger.grpc_interceptor.settings")
def test_grpc_payload_debugger_interceptor(mock_settings, mock_json_log, mock_msg_to_dict):
    # Set settings to enabled
    mock_settings.enabled = True
    mock_settings.mask_fields = ["password"]

    # Interceptor setup
    interceptor = grpc_payload_debugger_interceptor(service="test-service")

    # Mocks for continuation and handlers
    mock_continuation = MagicMock()
    mock_handler = MagicMock()
    mock_continuation.return_value = mock_handler

    # Mock the handler_call_details
    mock_handler_call_details = MagicMock()
    mock_handler_call_details.method = "/wms.inventory.InventoryService/CheckStock"

    # Mock message serialization
    mock_msg_to_dict.side_effect = lambda msg, **kwargs: msg

    # Set up request/response mock payloads
    req_payload = {"sku": "LAP-001", "password": "secret-password"}
    resp_payload = {"available": True, "password": "another-secret-password"}

    # Mock the unary_unary function of the handler
    mock_handler.unary_unary.return_value = resp_payload

    # Intercept
    intercepted_handler = interceptor.intercept_service(mock_continuation, mock_handler_call_details)
    assert intercepted_handler is not None

    # Call unary_unary on the intercepted handler
    mock_context = MagicMock()
    result = intercepted_handler.unary_unary(req_payload, mock_context)

    # Check that handler's unary_unary was called
    mock_handler.unary_unary.assert_called_once_with(req_payload, mock_context)
    assert result == resp_payload

    # Check json_log calls (one for request payload, one for response payload)
    assert mock_json_log.call_count == 2

    # Verify masked payloads in log calls
    first_call_args = mock_json_log.call_args_list[0][1]
    assert first_call_args["message"] == "grpc_debug_request_payload"
    assert first_call_args["payload"]["password"] == "[MASKED]"

    second_call_args = mock_json_log.call_args_list[1][1]
    assert second_call_args["message"] == "grpc_debug_response_payload"
    assert second_call_args["payload"]["password"] == "[MASKED]"


def test_event_envelope_traceparent_serialization():
    from shared_utils.events import EventEnvelope

    envelope = EventEnvelope(
        event_id="evt-123",
        schema_version=1,
        occurred_at="2026-07-14T08:15:00Z",
        source="test-service",
        type="TestEvent",
        payload={"data": "test"},
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )

    # Serialize to JSON
    raw = envelope.to_json()
    assert "traceparent" in raw
    assert "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" in raw

    # Deserialize from JSON
    deserialized = EventEnvelope.from_json(raw)
    assert deserialized.traceparent == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def test_build_event_captures_trace_context():
    from shared_utils.events import build_event
    from shared_utils.observability.trace import TraceContext, set_trace_context

    mock_trace_ctx = TraceContext(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        sampled=True,
    )
    set_trace_context(mock_trace_ctx)

    try:
        envelope = build_event(source="test-source", event_type="TestEvent", payload={"data": "test"})
        assert envelope.traceparent == mock_trace_ctx.traceparent
    finally:
        set_trace_context(None)


def test_durable_consumer_propagates_trace_context():
    from shared_utils.events import EventEnvelope, DurableRedisStreamConsumer
    from shared_utils.observability.trace import current_trace_context

    trace_parent_val = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    envelope = EventEnvelope(
        event_id="evt-123",
        schema_version=1,
        occurred_at="2026-07-14T08:15:00Z",
        source="test-service",
        type="TestEvent",
        payload={"data": "test"},
        traceparent=trace_parent_val,
    )

    captured_ctx = None

    def dummy_handler(msg_id, env):
        nonlocal captured_ctx
        captured_ctx = current_trace_context()

    # Setup consumer with mocks
    mock_client = MagicMock()
    consumer = DurableRedisStreamConsumer(
        client=mock_client,
        stream="test.stream",
        group="test.group",
        consumer="test.consumer",
        handler=dummy_handler,
        dlq_stream="test.dlq",
    )

    # Invoke _handle
    consumer._handle("msg-1", envelope)

    # Check context was set inside handler
    assert captured_ctx is not None
    assert captured_ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert captured_ctx.span_id != "00f067aa0ba902b7"  # Should be child span_id!
    assert captured_ctx.sampled is True

    # Check context is cleaned up after handle completes
    assert current_trace_context() is None


def test_calculate_state_diff():
    from shared_utils.debugger.langgraph_debugger import calculate_state_diff

    before = {
        "user": "avandall",
        "messages": ["hello", "world"],
        "metadata": {"key": "val"},
        "to_delete": 123
    }
    after = {
        "user": "avandall",
        "messages": ["hello", "world", "extra"],
        "metadata": {"key": "new_val"},
        "added_field": "new"
    }

    diff = calculate_state_diff(before, after)
    assert diff["added_field"] == {"status": "added", "value": "new"}
    assert diff["to_delete"] == {"status": "removed"}
    assert diff["metadata"] == {
        "status": "modified",
        "diff": {"key": {"status": "modified", "before": "val", "after": "new_val"}}
    }
    assert diff["messages"] == {
        "status": "appended",
        "new_count": 1,
        "items": ["extra"]
    }


@patch("shared_utils.debugger.langgraph_debugger.debug_log")
@patch("shared_utils.debugger.langgraph_debugger.settings")
def test_langgraph_debugger_callback(mock_settings, mock_json_log):
    from shared_utils.debugger import WMSLangGraphDebuggerCallback

    mock_settings.enabled = True
    mock_settings.mask_fields = ["password"]

    cb = WMSLangGraphDebuggerCallback(service="test-ai")

    # test chain callbacks
    run_id = "run-1"
    cb.on_chain_start({"name": "TestGraph"}, {"input": "hi", "password": "123"}, run_id=run_id)
    assert mock_json_log.call_count == 1
    args = mock_json_log.call_args_list[0][1]
    assert args["message"] == "langgraph_debug_chain_start"
    assert args["inputs"]["password"] == "[MASKED]"

    cb.on_chain_end({"output": "bye", "password": "123"}, run_id=run_id)
    assert mock_json_log.call_count == 2
    args = mock_json_log.call_args_list[1][1]
    assert args["message"] == "langgraph_debug_chain_end"
    assert args["outputs"]["password"] == "[MASKED]"

    # test tool callbacks
    cb.on_tool_start({"name": "db_tool"}, "input_str", run_id=run_id)
    assert mock_json_log.call_count == 3
    cb.on_tool_end("output_str", run_id=run_id)
    assert mock_json_log.call_count == 4


@patch("shared_utils.debugger.cli.console")
def test_cli_log_line_processing(mock_console):
    from shared_utils.debugger.cli import process_log_line

    # Test raw line
    process_log_line("hello world plain text")
    mock_console.print.assert_called_with("hello world plain text", style="dim")

    # Test JSON logs
    grpc_req_line = '{"service": "test", "level": "debug", "ts": 1720935595.123, "msg": "grpc_debug_request_payload", "method": "GetStock", "payload": {"sku": "LAP-001"}}'
    process_log_line(grpc_req_line)
    # Check that print was called with rich Console components (it should have printed the Panel)
    assert mock_console.print.call_count > 1


def test_debug_log_writes_to_file(tmp_path):
    from shared_utils.debugger import settings, debug_log
    import json

    temp_log_file = str(tmp_path / "wms_debug.log")
    
    # Set settings to enable file logging
    settings.write_file = True
    settings.file_path = temp_log_file

    try:
        debug_log(service="test-service", level="info", message="test_log_entry", key="val")
        
        # Verify file contents
        with open(temp_log_file, "r") as f:
            lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["service"] == "test-service"
        assert entry["level"] == "info"
        assert entry["msg"] == "test_log_entry"
        assert entry["key"] == "val"
    finally:
        # Reset settings
        settings.write_file = False


@pytest.mark.anyio
async def test_mcp_view_debugger_logs(tmp_path):
    import sys
    from pathlib import Path
    
    # Make sure WMS_MCP_Server is in path to import ViewDebuggerLogs
    mcp_path = str(Path(__file__).resolve().parents[4] / "WMS_MCP_Server")
    if mcp_path not in sys.path:
        sys.path.insert(0, mcp_path)

    # Mock asyncpg and aio_pika to prevent database/queue client load failures in test context
    from unittest.mock import MagicMock
    sys.modules['asyncpg'] = MagicMock()
    sys.modules['aio_pika'] = MagicMock()

    from app.tools.monitoring.view_debugger_logs import ViewDebuggerLogs
    import json

    temp_log_file = str(tmp_path / "wms_debug.log")
    
    # Pre-write some mock logs
    mock_records = [
        {"ts": 123.0, "service": "service-a", "level": "info", "msg": "first log", "trace_id": "trace-1"},
        {"ts": 124.0, "service": "service-b", "level": "error", "msg": "second log", "trace_id": "trace-2"},
        {"ts": 125.0, "service": "service-a", "level": "debug", "msg": "third log", "trace_id": "trace-1"},
    ]
    with open(temp_log_file, "w") as f:
        for r in mock_records:
            f.write(json.dumps(r) + "\n")

    # Mock environment variable for the tool
    with patch.dict(os.environ, {"WMS_DEBUG_FILE_PATH": temp_log_file}):
        tool = ViewDebuggerLogs()
        
        # Test no filter
        result = await tool.execute(limit=10)
        assert result.success is True
        assert result.data["total_returned"] == 3
        
        # Test filter by service
        result = await tool.execute(limit=10, service="service-a")
        assert result.success is True
        assert result.data["total_returned"] == 2
        assert result.data["logs"][0]["msg"] == "first log"
        assert result.data["logs"][1]["msg"] == "third log"
        
        # Test filter by trace_id
        result = await tool.execute(limit=10, trace_id="trace-2")
        assert result.success is True
        assert result.data["total_returned"] == 1
        assert result.data["logs"][0]["msg"] == "second log"



