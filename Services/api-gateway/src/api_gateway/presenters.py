from __future__ import annotations

import json
from typing import Any


def customer_to_dict(customer: Any) -> dict[str, Any]:
    return {
        "customer_id": int(customer.customer_id),
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
        "debt_balance": float(customer.debt_balance),
        "created_at": customer.created_at,
    }


def product_to_dict(product: Any) -> dict[str, Any]:
    return {
        "product_id": int(product.product_id),
        "name": product.name,
        "price": float(product.price),
        "description": product.description,
    }


def warehouse_to_dict(warehouse: Any) -> dict[str, Any]:
    return {
        "warehouse_id": int(warehouse.warehouse_id),
        "name": warehouse.location,
        "location": warehouse.location,
        "inventory": [
            {"product_id": int(item.product_id), "quantity": int(item.quantity)}
            for item in warehouse.inventory
        ],
    }


def document_to_dict(document: Any) -> dict[str, Any]:
    return {
        "document_id": int(document.document_id),
        "doc_type": document.doc_type,
        "status": document.status,
        "created_by": document.created_by,
        "approved_by": getattr(document, "approved_by", None),
        "note": getattr(document, "note", None),
        "created_at": getattr(document, "created_at", None),
        "posted_at": getattr(document, "posted_at", None),
        "from_warehouse_id": getattr(document, "from_warehouse_id", None),
        "to_warehouse_id": getattr(document, "to_warehouse_id", None),
        "customer_id": getattr(document, "customer_id", None),
        "items": [
            {
                "product_id": int(item.product_id),
                "quantity": int(item.quantity),
                "unit_price": float(item.unit_price),
            }
            for item in document.items
        ],
    }


def audit_event_to_dict(event: Any) -> dict[str, Any]:
    return {
        "id": int(event.id),
        "request_id": event.request_id,
        "user_id": int(event.user_id),
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "warehouse_id": int(event.warehouse_id),
        "payload": parse_json(event.payload_json),
        "created_at": event.created_at,
    }


def parse_json(value: str):
    try:
        return json.loads(value) if value else value
    except Exception:
        return value
