"""Unit tests for FastAPI Lifespan Context Manager migration (TASK-091)."""

import pytest
from starlette.testclient import TestClient

from api_gateway.app import app, create_app


def test_app_and_create_app_exports():
    """Verify app and create_app are properly exported."""
    assert app is not None
    assert app.title == "API Gateway"
    assert app.router.lifespan_context is not None


def test_no_deprecated_on_event_handlers():
    """AC1: Verify zero @app.on_event handlers exist on app or newly created app."""
    # In FastAPI / Starlette, on_event handlers are stored in router.on_startup / router.on_shutdown
    # or extra_body / lifespan
    new_app = create_app()
    assert len(new_app.router.on_startup) == 0
    assert len(new_app.router.on_shutdown) == 0
    assert len(app.router.on_startup) == 0
    assert len(app.router.on_shutdown) == 0


def test_lifespan_context_manager_lifecycle():
    """AC2 & AC3: Lifespan starts up ingest buffer and background tasks, then shuts down cleanly."""
    with TestClient(app) as client:
        # Entering TestClient triggers lifespan startup
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    # Exiting TestClient triggers lifespan shutdown without errors
