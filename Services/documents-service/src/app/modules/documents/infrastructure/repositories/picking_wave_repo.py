from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.documents.application.services.wave_service import (
    BatchPickingTask,
    OrderItem,
    OutboundOrder,
    PickingWave,
    WaveStatus,
)
from app.modules.documents.infrastructure.models.picking_wave import PickingWaveModel
from app.shared.core.transaction import TransactionalRepository


class PickingWaveRepository(TransactionalRepository):
    """PostgreSQL-backed repository for Picking Waves and their nested tasks/orders."""

    def __init__(self, session: Session, auto_commit: bool = True):
        super().__init__(session, auto_commit=auto_commit)

    def save(self, wave: PickingWave) -> None:
        orders_data = [
            {
                "order_id": order.order_id,
                "carrier": order.carrier,
                "dispatch_cutoff": (
                    order.dispatch_cutoff.isoformat()
                    if isinstance(order.dispatch_cutoff, datetime)
                    else str(order.dispatch_cutoff)
                ),
                "items": [
                    {
                        "product_id": item.product_id,
                        "sku": item.sku,
                        "quantity": item.quantity,
                        "unit_weight_g": item.unit_weight_g,
                        "location_id": item.location_id,
                    }
                    for item in order.items
                ],
                "status": order.status,
            }
            for order in wave.orders
        ]

        tasks_data = [
            {
                "task_id": task.task_id,
                "wave_id": task.wave_id,
                "product_id": task.product_id,
                "sku": task.sku,
                "location_id": task.location_id,
                "total_quantity": task.total_quantity,
                "picked_quantity": task.picked_quantity,
                "status": task.status,
            }
            for task in wave.picking_tasks
        ]

        status_val = (
            wave.status.value
            if isinstance(wave.status, WaveStatus)
            else str(wave.status)
        )

        model = self.session.get(PickingWaveModel, wave.wave_id)
        if model is None:
            model = PickingWaveModel(
                wave_id=wave.wave_id,
                carrier=wave.carrier,
                dispatch_cutoff=wave.dispatch_cutoff,
                max_orders=wave.max_orders,
                status=status_val,
                orders=orders_data,
                picking_tasks=tasks_data,
                created_at=wave.created_at,
            )
            self.session.add(model)
        else:
            model.carrier = wave.carrier
            model.dispatch_cutoff = wave.dispatch_cutoff
            model.max_orders = wave.max_orders
            model.status = status_val
            model.orders = orders_data
            model.picking_tasks = tasks_data
            model.created_at = wave.created_at

        self._commit_if_auto()

    def get(self, wave_id: str) -> Optional[PickingWave]:
        model = self.session.get(PickingWaveModel, wave_id)
        if model is None:
            return None

        orders: List[OutboundOrder] = []
        for od in model.orders or []:
            items = [
                OrderItem(
                    product_id=it["product_id"],
                    sku=it["sku"],
                    quantity=it["quantity"],
                    unit_weight_g=it["unit_weight_g"],
                    location_id=it.get("location_id", "A-01-01"),
                )
                for it in od.get("items", [])
            ]
            cutoff_val = od["dispatch_cutoff"]
            cutoff = (
                datetime.fromisoformat(cutoff_val)
                if isinstance(cutoff_val, str)
                else cutoff_val
            )
            orders.append(
                OutboundOrder(
                    order_id=od["order_id"],
                    carrier=od["carrier"],
                    dispatch_cutoff=cutoff,
                    items=items,
                    status=od.get("status", "PENDING"),
                )
            )

        tasks: List[BatchPickingTask] = []
        for td in model.picking_tasks or []:
            tasks.append(
                BatchPickingTask(
                    task_id=td["task_id"],
                    wave_id=td["wave_id"],
                    product_id=td["product_id"],
                    sku=td["sku"],
                    location_id=td["location_id"],
                    total_quantity=td["total_quantity"],
                    picked_quantity=td.get("picked_quantity", 0),
                    status=td.get("status", "PENDING"),
                )
            )

        return PickingWave(
            wave_id=model.wave_id,
            carrier=model.carrier,
            dispatch_cutoff=model.dispatch_cutoff,
            max_orders=model.max_orders,
            orders=orders,
            picking_tasks=tasks,
            status=WaveStatus(model.status),
            created_at=model.created_at,
        )

    def exists(self, wave_id: str) -> bool:
        return self.session.get(PickingWaveModel, wave_id) is not None

    def delete(self, wave_id: str) -> None:
        model = self.session.get(PickingWaveModel, wave_id)
        if model:
            self.session.delete(model)
            self._commit_if_auto()
