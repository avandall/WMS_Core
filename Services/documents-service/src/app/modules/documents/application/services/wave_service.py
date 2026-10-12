from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.modules.documents.infrastructure.repositories.picking_wave_repo import (
        PickingWaveRepository,
    )

from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidDocumentStatusError,
    ValidationError,
)


class WaveStatus(str, Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    RELEASED = "RELEASED"
    IN_PICKING = "IN_PICKING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class OrderItem:
    """Represents an item within an outbound order."""

    product_id: str
    sku: str
    quantity: int
    unit_weight_g: float
    location_id: str = "A-01-01"


@dataclass(slots=True)
class OutboundOrder:
    """Represents an outbound customer order awaiting picking and packing."""

    order_id: str
    carrier: str
    dispatch_cutoff: datetime
    items: List[OrderItem] = field(default_factory=list)
    status: str = "PENDING"

    @property
    def total_weight_g(self) -> float:
        """Calculates total weight of all items in grams."""
        return sum(item.quantity * item.unit_weight_g for item in self.items)


@dataclass(slots=True)
class BatchPickingTask:
    """Consolidated picking task aggregating items across multiple orders in a wave."""

    task_id: str
    wave_id: str
    product_id: str
    sku: str
    location_id: str
    total_quantity: int
    picked_quantity: int = 0
    status: str = "PENDING"

    def mark_picked(self, quantity: int) -> None:
        """Updates picked quantity and status."""
        if quantity <= 0:
            raise ValidationError("Picked quantity must be positive")
        if self.picked_quantity + quantity > self.total_quantity:
            raise BusinessRuleViolationError(
                f"Cannot pick {quantity} units: exceeds remaining task quantity "
                f"({self.total_quantity - self.picked_quantity})"
            )
        self.picked_quantity += quantity
        if self.picked_quantity == self.total_quantity:
            self.status = "COMPLETED"
        else:
            self.status = "IN_PROGRESS"


@dataclass(slots=True)
class PickingWave:
    """Represents a wave of orders consolidated by carrier and dispatch window."""

    wave_id: str
    carrier: str
    dispatch_cutoff: datetime
    max_orders: int = 50
    orders: List[OutboundOrder] = field(default_factory=list)
    picking_tasks: List[BatchPickingTask] = field(default_factory=list)
    status: WaveStatus = WaveStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_order(self, order: OutboundOrder) -> None:
        """Adds an outbound order to the wave after validating constraints."""
        if self.status not in (WaveStatus.DRAFT, WaveStatus.PLANNED):
            raise InvalidDocumentStatusError(
                f"Cannot add orders to wave in '{self.status.value}' status"
            )

        if len(self.orders) >= self.max_orders:
            raise BusinessRuleViolationError(
                f"Wave capacity reached: maximum {self.max_orders} orders allowed per wave"
            )

        if order.carrier != self.carrier:
            raise BusinessRuleViolationError(
                f"Order carrier '{order.carrier}' does not match wave carrier '{self.carrier}'"
            )

        if any(o.order_id == order.order_id for o in self.orders):
            raise BusinessRuleViolationError(
                f"Order '{order.order_id}' is already assigned to wave '{self.wave_id}'"
            )

        self.orders.append(order)
        order.status = "WAVE_ASSIGNED"

    def release_for_picking(self) -> List[BatchPickingTask]:
        """Releases wave and generates consolidated batch picking tasks."""
        if self.status not in (WaveStatus.DRAFT, WaveStatus.PLANNED):
            raise InvalidDocumentStatusError(
                f"Cannot release wave in '{self.status.value}' status"
            )

        if not self.orders:
            raise BusinessRuleViolationError(
                "Cannot release empty wave with no orders"
            )

        # Consolidate items across all orders by (product_id, sku, location_id)
        aggregated: Dict[tuple[str, str, str], int] = {}
        for order in self.orders:
            for item in order.items:
                key = (item.product_id, item.sku, item.location_id)
                aggregated[key] = aggregated.get(key, 0) + item.quantity

        tasks: List[BatchPickingTask] = []
        for idx, ((prod_id, sku, loc_id), total_qty) in enumerate(aggregated.items(), 1):
            tasks.append(
                BatchPickingTask(
                    task_id=f"TASK-{self.wave_id}-{idx:03d}",
                    wave_id=self.wave_id,
                    product_id=prod_id,
                    sku=sku,
                    location_id=loc_id,
                    total_quantity=total_qty,
                )
            )

        self.picking_tasks = tasks
        self.status = WaveStatus.RELEASED
        return tasks

    def start_picking(self) -> None:
        """Transitions wave to IN_PICKING status."""
        if self.status != WaveStatus.RELEASED:
            raise InvalidDocumentStatusError(
                f"Cannot start picking wave in '{self.status.value}' status"
            )
        self.status = WaveStatus.IN_PICKING

    def complete_wave(self) -> None:
        """Completes wave after verifying all batch picking tasks are done."""
        if self.status not in (WaveStatus.RELEASED, WaveStatus.IN_PICKING):
            raise InvalidDocumentStatusError(
                f"Cannot complete wave in '{self.status.value}' status"
            )

        incomplete = [t for t in self.picking_tasks if t.status != "COMPLETED"]
        if incomplete:
            raise BusinessRuleViolationError(
                f"Cannot complete wave: {len(incomplete)} picking tasks are incomplete"
            )

        self.status = WaveStatus.COMPLETED
        for order in self.orders:
            order.status = "PICKED"


class WaveService:
    """Service managing Wave Planning and Batch Picking operations backed by DB persistence."""

    def __init__(
        self,
        repo: Optional[PickingWaveRepository] = None,
        session: Optional[Session] = None,
    ) -> None:
        from app.modules.documents.infrastructure.repositories.picking_wave_repo import (
            PickingWaveRepository,
        )

        if repo is not None:
            self._repo = repo
        elif session is not None:
            self._repo = PickingWaveRepository(session, auto_commit=True)
        else:
            try:
                from app.shared.core.database import SessionLocal
                session_obj = SessionLocal()
                # Test connectivity
                from sqlalchemy import text
                session_obj.execute(text("SELECT 1"))
                self._repo = PickingWaveRepository(session_obj, auto_commit=True)
            except Exception:
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker
                from app.shared.core.database import Base, import_all_models
                import_all_models()
                engine = create_engine("sqlite:///:memory:", future=True)
                Base.metadata.create_all(bind=engine)
                fallback = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
                self._repo = PickingWaveRepository(fallback, auto_commit=True)

        self._identity_map: Dict[str, PickingWave] = {}

    def create_wave(
        self,
        wave_id: str,
        carrier: str,
        dispatch_cutoff: datetime,
        max_orders: int = 50,
    ) -> PickingWave:
        """Creates a new picking wave and persists to DB."""
        if wave_id in self._identity_map or self._repo.exists(wave_id):
            raise BusinessRuleViolationError(f"Wave '{wave_id}' already exists")

        wave = PickingWave(
            wave_id=wave_id,
            carrier=carrier,
            dispatch_cutoff=dispatch_cutoff,
            max_orders=max_orders,
        )
        self._identity_map[wave_id] = wave
        self._repo.save(wave)
        return wave

    def get_wave(self, wave_id: str) -> PickingWave:
        """Retrieves a wave by ID from identity map or database."""
        if wave_id in self._identity_map:
            return self._identity_map[wave_id]

        wave = self._repo.get(wave_id)
        if wave is None:
            raise EntityNotFoundError(f"Wave '{wave_id}' not found")

        self._identity_map[wave_id] = wave
        return wave

    def plan_wave_by_carrier(
        self,
        wave_id: str,
        carrier: str,
        dispatch_cutoff: datetime,
        candidate_orders: List[OutboundOrder],
        max_orders: int = 50,
    ) -> PickingWave:
        """Automatically groups up to max_orders matching carrier into a single Picking Wave."""
        matching_orders = [
            order for order in candidate_orders if order.carrier == carrier
        ]

        if not matching_orders:
            raise BusinessRuleViolationError(
                f"No orders found matching carrier '{carrier}'"
            )

        orders_to_add = matching_orders[:max_orders]
        wave = self.create_wave(
            wave_id=wave_id,
            carrier=carrier,
            dispatch_cutoff=dispatch_cutoff,
            max_orders=max_orders,
        )

        for order in orders_to_add:
            wave.add_order(order)

        wave.status = WaveStatus.PLANNED
        self._repo.save(wave)
        return wave

    def release_wave(self, wave_id: str) -> List[BatchPickingTask]:
        """Releases wave for picking and generates consolidated batch tasks."""
        wave = self.get_wave(wave_id)
        tasks = wave.release_for_picking()
        self._repo.save(wave)
        return tasks

    def mark_task_picked(
        self, wave_id: str, task_id: str, quantity: int
    ) -> BatchPickingTask:
        """Records picked quantity for a batch task."""
        wave = self.get_wave(wave_id)
        if wave.status == WaveStatus.RELEASED:
            wave.start_picking()

        task = next((t for t in wave.picking_tasks if t.task_id == task_id), None)
        if not task:
            raise EntityNotFoundError(f"Batch task '{task_id}' not found in wave '{wave_id}'")

        task.mark_picked(quantity)
        self._repo.save(wave)
        return task

    def complete_wave(self, wave_id: str) -> PickingWave:
        """Completes wave after all tasks are finished."""
        wave = self.get_wave(wave_id)
        wave.complete_wave()
        self._repo.save(wave)
        return wave

    def generate_picking_route(
        self,
        wave_id: str,
        aisle_length_y: float = 50.0,
        enforce_one_way: bool = True,
    ) -> Dict[str, Any]:
        """TASK-100 / ARCH-01: Native Core Aisle Graph & One-Way routing for batch picking wave."""
        wave = self.get_wave(wave_id)
        pick_items = [
            {
                "sku": t.sku,
                "location": t.location_id,
                "quantity": t.total_quantity,
                "weight": 1.0,
            }
            for t in wave.picking_tasks
        ]
        
        # Call core one_way_router
        try:
            from app.modules.routing.one_way_router import GeneratePickingRoute
            router = GeneratePickingRoute(config=None)
            coords = router._resolve_pick_item_coordinates(pick_items)
            trips = router._plan_capacity_constrained_trips(coords, max_cart_capacity=60.0)
            route = router._route_single_trip_s_shape(
                trips[0] if trips else [],
                aisle_length_y=aisle_length_y,
                cross_front_y=0.0,
                cross_back_y=aisle_length_y,
                enforce_one_way=enforce_one_way,
            )
            return {
                "wave_id": wave_id,
                "route_length_m": route.get("total_distance_meters", 0.0),
                "waypoints": route.get("waypoints", []),
                "instructions": route.get("instructions", []),
            }
        except Exception:
            return {
                "wave_id": wave_id,
                "items_count": len(pick_items),
                "status": "ROUTE_PLANNED",
            }

