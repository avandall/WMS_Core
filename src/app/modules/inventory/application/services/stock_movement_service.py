from __future__ import annotations

from typing import Any, Optional

from app.shared.core.logging import get_logger
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    InsufficientStockError,
    InvalidQuantityError,
    ValidationError,
)
from app.shared.domain.audit_event_repo import IAuditEventRepo
from app.modules.positions.domain.interfaces.position_repo import IPositionRepo
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo

logger = get_logger(__name__)


class StockMovementService:
    """Position-aware stock movement orchestration."""

    def __init__(
        self,
        *,
        position_repo: IPositionRepo,
        warehouse_repo: IWarehouseRepo,
        session: Any,
        audit_event_repo: Optional[IAuditEventRepo] = None,
    ):
        self.position_repo = position_repo
        self.warehouse_repo = warehouse_repo
        self.session = session
        self.audit_event_repo = audit_event_repo

    def put_away(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        from_position_code: str = "RECEIVING",
        to_position_code: str = "STORAGE",
        user_id: Optional[int] = None,
    ) -> dict:
        return self.move_within_warehouse(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            from_position_code=from_position_code,
            to_position_code=to_position_code,
            user_id=user_id,
            action="PUT_AWAY",
        )

    def pick(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        from_position_code: str = "STORAGE",
        to_position_code: str = "SHIPPING",
        user_id: Optional[int] = None,
    ) -> dict:
        return self.move_within_warehouse(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            from_position_code=from_position_code,
            to_position_code=to_position_code,
            user_id=user_id,
            action="PICK",
        )

    def move_within_warehouse(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        from_position_code: str,
        to_position_code: str,
        user_id: Optional[int] = None,
        action: str = "STOCK_MOVED",
    ) -> dict:
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive")
        if from_position_code.strip().upper() == to_position_code.strip().upper():
            raise BusinessRuleViolationError("from_position and to_position must differ")

        self._ensure_defaults_and_balance(warehouse_id, product_id)

        try:
            self._set_repos_auto_commit(False)

            from_pos = self.position_repo.get_position_model(warehouse_id, from_position_code)
            to_pos = self.position_repo.get_position_model(warehouse_id, to_position_code)

            self.position_repo.adjust_position_stock(
                position_id=from_pos.id, product_id=product_id, delta=-quantity
            )
            self.position_repo.adjust_position_stock(
                position_id=to_pos.id, product_id=product_id, delta=quantity
            )

            if self.audit_event_repo:
                self.audit_event_repo.create_event(
                    action=action,
                    entity_type="position_move",
                    entity_id=f"{warehouse_id}:{product_id}",
                    warehouse_id=warehouse_id,
                    payload={
                        "product_id": product_id,
                        "quantity": quantity,
                        "from_position": from_pos.code,
                        "to_position": to_pos.code,
                    },
                    user_id=user_id,
                )

            self.session.commit()
            return {
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "quantity": quantity,
                "from_position": from_pos.code,
                "to_position": to_pos.code,
            }

        except InsufficientStockError:
            self.session.rollback()
            raise
        except Exception as exc:
            self.session.rollback()
            raise ValidationError(str(exc)) from exc
        finally:
            self._set_repos_auto_commit(True)

    def transfer_between_warehouses(
        self,
        *,
        from_warehouse_id: int,
        to_warehouse_id: int,
        product_id: int,
        quantity: int,
        from_position_code: str = "SHIPPING",
        to_position_code: str = "RECEIVING",
        user_id: Optional[int] = None,
    ) -> dict:
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive")
        if from_warehouse_id == to_warehouse_id:
            raise ValidationError("Cannot transfer within the same warehouse")

        self._ensure_defaults_and_balance(from_warehouse_id, product_id)
        self._ensure_defaults_and_balance(to_warehouse_id, product_id)

        try:
            self._set_repos_auto_commit(False)

            to_pos = self.position_repo.get_position_model(to_warehouse_id, to_position_code)

            preferred = []
            for code in [
                from_position_code,
                "SHIPPING",
                "STAGING",
                "STORAGE",
                "UNASSIGNED",
                "RECEIVING",
            ]:
                norm = code.strip().upper()
                if norm not in preferred:
                    preferred.append(norm)

            allocations = self.position_repo.allocate_and_remove(
                warehouse_id=from_warehouse_id,
                product_id=product_id,
                quantity=quantity,
                preferred_position_codes=preferred,
            )

            self.position_repo.adjust_position_stock(
                position_id=to_pos.id, product_id=product_id, delta=quantity
            )

            self.warehouse_repo.remove_product_from_warehouse(
                from_warehouse_id, product_id, quantity
            )
            self.warehouse_repo.add_product_to_warehouse(
                to_warehouse_id, product_id, quantity
            )

            if self.audit_event_repo:
                self.audit_event_repo.create_event(
                    action="STOCK_TRANSFERRED",
                    entity_type="warehouse_transfer",
                    entity_id=f"{from_warehouse_id}->{to_warehouse_id}:{product_id}",
                    warehouse_id=from_warehouse_id,
                    payload={
                        "product_id": product_id,
                        "quantity": quantity,
                        "from": {
                            "warehouse_id": from_warehouse_id,
                            "preferred_position": from_position_code.strip().upper(),
                            "allocations": [
                                {"position": code, "quantity": qty}
                                for code, qty in allocations
                            ],
                        },
                        "to": {"warehouse_id": to_warehouse_id, "position": to_pos.code},
                    },
                    user_id=user_id,
                )

            self.session.commit()
            return {
                "product_id": product_id,
                "quantity": quantity,
                "from": {
                    "warehouse_id": from_warehouse_id,
                    "allocations": [
                        {"position": code, "quantity": qty} for code, qty in allocations
                    ],
                },
                "to": {"warehouse_id": to_warehouse_id, "position": to_pos.code},
            }

        except InsufficientStockError:
            self.session.rollback()
            raise
        except Exception as exc:
            self.session.rollback()
            raise ValidationError(str(exc)) from exc
        finally:
            self._set_repos_auto_commit(True)

    def _ensure_defaults_and_balance(self, warehouse_id: int, product_id: int) -> None:
        self.position_repo.ensure_default_positions(warehouse_id)

        wh_qty = self._get_warehouse_product_quantity(warehouse_id, product_id)
        pos_total = self.position_repo.get_total_quantity_for_product(
            warehouse_id, product_id
        )
        diff = wh_qty - pos_total
        if diff == 0:
            return

        unassigned = self.position_repo.get_position_model(warehouse_id, "UNASSIGNED")
        if diff > 0:
            self.position_repo.adjust_position_stock(
                position_id=unassigned.id, product_id=product_id, delta=diff
            )
        else:
            try:
                self.position_repo.adjust_position_stock(
                    position_id=unassigned.id, product_id=product_id, delta=diff
                )
            except InsufficientStockError as exc:
                raise ValidationError(
                    f"Position stock exceeds warehouse stock for product {product_id} in warehouse {warehouse_id}"
                ) from exc

        logger.warning(
            f"Reconciled position stock to warehouse totals: warehouse_id={warehouse_id} product_id={product_id} diff={diff}"
        )

    def _get_warehouse_product_quantity(self, warehouse_id: int, product_id: int) -> int:
        items = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
        for row in items:
            if row.product_id == product_id:
                return int(row.quantity)
        return 0

    def _set_repos_auto_commit(self, enabled: bool) -> None:
        for repo in [self.position_repo, self.warehouse_repo, self.audit_event_repo]:
            if repo is None:
                continue
            if hasattr(repo, "set_auto_commit"):
                repo.set_auto_commit(enabled)
