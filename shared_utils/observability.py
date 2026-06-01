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
