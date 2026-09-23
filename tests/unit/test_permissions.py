"""
Unit tests for RBAC permissions module.
Verifies role-based access control rules, specifically Segregation of Duties rules
such as sales role forbidden from creating import documents (TASK-027 / BIZ-19).
"""

import pytest
from api_gateway.permissions import (
    Permission as GatewayPermission,
    ROLE_PERMISSIONS as GATEWAY_ROLE_PERMISSIONS,
    role_has_permissions as gateway_role_has_permissions,
)
from app.shared.core.permissions import (
    Permission as ServicePermission,
    ROLE_PERMISSIONS as SERVICE_ROLE_PERMISSIONS,
    role_has_permissions as service_role_has_permissions,
)


def test_sales_cannot_create_import_document():
    """
    [BIZ-19 / TASK-027] Acceptance Criteria:
    - Sales role MUST NOT have DOC_CREATE_IMPORT permission.
    - role_has_permissions("sales", {DOC_CREATE_IMPORT}) MUST return False.
    """
    # 1. Check API Gateway permissions
    assert GatewayPermission.DOC_CREATE_IMPORT not in GATEWAY_ROLE_PERMISSIONS["sales"]
    assert not gateway_role_has_permissions("sales", {GatewayPermission.DOC_CREATE_IMPORT})

    # 2. Check Service core permissions
    assert ServicePermission.DOC_CREATE_IMPORT not in SERVICE_ROLE_PERMISSIONS["sales"]
    assert not service_role_has_permissions("sales", {ServicePermission.DOC_CREATE_IMPORT})


def test_sales_allowed_permissions():
    """
    Verify sales role retains valid allowed permissions.
    """
    # Sales allowed permissions in Gateway
    assert gateway_role_has_permissions("sales", {GatewayPermission.VIEW_CUSTOMERS})
    assert gateway_role_has_permissions("sales", {GatewayPermission.MANAGE_CUSTOMERS})
    assert gateway_role_has_permissions("sales", {GatewayPermission.VIEW_PRODUCTS})
    assert gateway_role_has_permissions("sales", {GatewayPermission.VIEW_INVENTORY})
    assert gateway_role_has_permissions("sales", {GatewayPermission.VIEW_REPORTS})

    # Sales allowed permissions in Service core
    assert service_role_has_permissions("sales", {ServicePermission.VIEW_PRODUCTS})
    assert service_role_has_permissions("sales", {ServicePermission.VIEW_INVENTORY})
    assert service_role_has_permissions("sales", {ServicePermission.VIEW_REPORTS})


def test_sales_forbidden_admin_permissions():
    """
    Verify sales role cannot perform administrative operations.
    """
    assert not gateway_role_has_permissions("sales", {GatewayPermission.MANAGE_USERS})
    assert not gateway_role_has_permissions("sales", {GatewayPermission.MANAGE_WAREHOUSES})
    assert not gateway_role_has_permissions("sales", {GatewayPermission.EDIT_PRICES})
    assert not service_role_has_permissions("sales", {ServicePermission.MANAGE_USERS})


def test_admin_has_full_permissions():
    """
    Verify admin role has all permissions.
    """
    for perm in GatewayPermission:
        assert gateway_role_has_permissions("admin", {perm})

    for perm in ServicePermission:
        assert service_role_has_permissions("admin", {perm})
