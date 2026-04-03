"""
Test to verify database isolation between integration tests.
Run this when PostgreSQL is available to check if data persists between tests.
"""

import pytest


def test_create_product_1(client):
    """First test creates a product with ID 999."""
    response = client.post(
        "/api/products/",
        json={
            "product_id": 999,
            "name": "Test Product 1",
            "price": 100.0,
            "description": "First test product",
        },
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )


def test_check_product_persists(client):
    """Second test checks if product 999 from previous test still exists."""
    response = client.get("/api/products/999")

    if response.status_code == 200:
        pytest.fail(
            "PROBLEM: Product 999 persists from previous test! Tests are NOT isolated."
        )
    else:
        # Good - product does not exist, tests are isolated
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


def test_create_product_2(client):
    """Third test creates same product again to verify isolation."""
    response = client.post(
        "/api/products/",
        json={
            "product_id": 999,
            "name": "Test Product 2",
            "price": 200.0,
            "description": "Second test product",
        },
    )

    if response.status_code == 409:  # Conflict - already exists
        pytest.fail("PROBLEM: Product 999 already exists! Tests share database state.")
    else:
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
