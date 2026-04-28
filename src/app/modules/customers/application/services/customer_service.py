from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.shared.domain.customer_repo import ICustomerRepo


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class CustomerService:
    def __init__(self, customer_repo: ICustomerRepo):
        self.customer_repo = customer_repo

    def create(self, data: dict):
        return self.customer_repo.create(data)

    def list(self) -> List[Dict[str, Any]]:
        customers = self.customer_repo.get_all()
        result: list[dict] = []
        for c in customers:
            customer_id = _get_field(c, "customer_id")
            purchase_stats = self._purchase_stats(customer_id)
            result.append(
                {
                    "customer_id": customer_id,
                    "name": _get_field(c, "name"),
                    "email": _get_field(c, "email"),
                    "phone": _get_field(c, "phone"),
                    "address": _get_field(c, "address"),
                    "debt_balance": _get_field(c, "debt_balance", 0.0) or 0.0,
                    "created_at": _get_field(c, "created_at"),
                    **purchase_stats,
                }
            )
        return result

    def get(self, customer_id: int) -> Optional[Dict[str, Any]]:
        c = self.customer_repo.get(customer_id)
        if not c:
            return None
        purchases = self.customer_repo.list_purchases(customer_id)
        stats = self._purchase_stats(customer_id)
        return {
            "customer_id": _get_field(c, "customer_id"),
            "name": _get_field(c, "name"),
            "email": _get_field(c, "email"),
            "phone": _get_field(c, "phone"),
            "address": _get_field(c, "address"),
            "debt_balance": _get_field(c, "debt_balance", 0.0) or 0.0,
            "created_at": _get_field(c, "created_at"),
            "purchases": purchases,
            **stats,
        }

    def update_debt(self, customer_id: int, delta: float) -> None:
        self.customer_repo.update_debt(customer_id, delta)

    def update(self, customer_id: int, data: dict) -> None:
        self.customer_repo.update(customer_id, data)

    def record_purchase(self, customer_id: int, document_id: int, total_value: float) -> None:
        self.customer_repo.record_purchase(customer_id, document_id, total_value)

    def purchases(self, customer_id: int):
        return self.customer_repo.list_purchases(customer_id)

    def _purchase_stats(self, customer_id: int) -> Dict[str, Any]:
        purchases = self.customer_repo.list_purchases(customer_id)
        total = sum(p.get("total_value", 0) for p in purchases)
        return {"purchase_count": len(purchases), "total_purchased": total}

