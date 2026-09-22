from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.modules.documents.infrastructure.repositories.carton_package_repo import (
        PackingRepository,
    )

from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)


class PackingStatus(str, Enum):
    PACKING = "PACKING"
    WEIGHT_VERIFIED = "WEIGHT_VERIFIED"
    WEIGHT_FAILED = "WEIGHT_FAILED"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"


@dataclass(slots=True)
class PackItem:
    """Represents an item packed into a carton package."""

    product_id: str
    sku: str
    quantity: int
    unit_weight_g: float


@dataclass(slots=True)
class WeightVerificationResult:
    """Result of check-weigher verification at packing station."""

    carton_id: str
    theoretical_weight_g: float
    measured_weight_g: float
    deviation_g: float
    is_valid: bool
    allowed_tolerance_g: float = 50.0
    message: str = ""


@dataclass(slots=True)
class CartonPackage:
    """Represents a packaged carton containing order items prepared at pack station."""

    carton_id: str
    order_id: str
    packaging_tare_weight_g: float = 100.0
    items: List[PackItem] = field(default_factory=list)
    status: PackingStatus = PackingStatus.PACKING
    measured_weight_g: Optional[float] = None
    verification_result: Optional[WeightVerificationResult] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def items_weight_g(self) -> float:
        """Calculates total net weight of items in grams."""
        return sum(item.quantity * item.unit_weight_g for item in self.items)

    @property
    def theoretical_weight_g(self) -> float:
        """Calculates gross theoretical weight (items + packaging tare) in grams."""
        return self.items_weight_g + self.packaging_tare_weight_g


class PackingService:
    """Service managing pack station operations and check-weigher weight verification backed by DB persistence."""

    DEFAULT_TOLERANCE_G: float = 50.0

    def __init__(
        self,
        tolerance_g: float = DEFAULT_TOLERANCE_G,
        repo: Optional[PackingRepository] = None,
        session: Optional[Session] = None,
    ) -> None:
        from app.modules.documents.infrastructure.repositories.carton_package_repo import (
            PackingRepository,
        )

        self.tolerance_g = tolerance_g
        if repo is not None:
            self._repo = repo
        elif session is not None:
            self._repo = PackingRepository(session, auto_commit=True)
        else:
            try:
                from app.shared.core.database import SessionLocal
                session_obj = SessionLocal()
                from sqlalchemy import text
                session_obj.execute(text("SELECT 1"))
                self._repo = PackingRepository(session_obj, auto_commit=True)
            except Exception:
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker
                from app.shared.core.database import Base, import_all_models
                import_all_models()
                engine = create_engine("sqlite:///:memory:", future=True)
                Base.metadata.create_all(bind=engine)
                fallback = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
                self._repo = PackingRepository(fallback, auto_commit=True)

        self._identity_map: Dict[str, CartonPackage] = {}

    def create_carton(
        self,
        carton_id: str,
        order_id: str,
        items: List[PackItem],
        packaging_tare_weight_g: float = 100.0,
    ) -> CartonPackage:
        """Creates a new carton package for an order and persists to DB."""
        if not items:
            raise ValidationError("Cannot create carton package with empty items list")

        if carton_id in self._identity_map or self._repo.exists(carton_id):
            raise BusinessRuleViolationError(f"Carton '{carton_id}' already exists")

        carton = CartonPackage(
            carton_id=carton_id,
            order_id=order_id,
            packaging_tare_weight_g=packaging_tare_weight_g,
            items=items,
        )
        self._identity_map[carton_id] = carton
        self._repo.save(carton)
        return carton

    def get_carton(self, carton_id: str) -> CartonPackage:
        """Retrieves a carton package by ID from identity map or DB."""
        if carton_id in self._identity_map:
            return self._identity_map[carton_id]

        carton = self._repo.get(carton_id)
        if carton is None:
            raise EntityNotFoundError(f"Carton '{carton_id}' not found")

        self._identity_map[carton_id] = carton
        return carton

    def verify_check_weigher(
        self,
        carton_id: str,
        measured_weight_g: float,
        override_tolerance_g: Optional[float] = None,
    ) -> WeightVerificationResult:
        """Compares theoretical gross weight against electronic scale measurement.

        If deviation > tolerance (default 50g), flags warning and rejects verification.
        """
        carton = self.get_carton(carton_id)
        tolerance = override_tolerance_g if override_tolerance_g is not None else self.tolerance_g

        if measured_weight_g <= 0:
            raise ValidationError("Measured weight from electronic scale must be positive")

        theoretical = carton.theoretical_weight_g
        deviation = abs(measured_weight_g - theoretical)
        is_valid = deviation <= tolerance

        if is_valid:
            msg = (
                f"Weight verification PASSED. Theoretical: {theoretical:.1f}g, "
                f"Measured: {measured_weight_g:.1f}g, Deviation: {deviation:.1f}g (<= {tolerance:.1f}g)"
            )
            carton.status = PackingStatus.WEIGHT_VERIFIED
        else:
            msg = (
                f"ALERT: Weight verification FAILED! Theoretical: {theoretical:.1f}g, "
                f"Measured: {measured_weight_g:.1f}g, Deviation: {deviation:.1f}g exceeds "
                f"allowed limit ({tolerance:.1f}g). Re-check package contents for theft/loss."
            )
            carton.status = PackingStatus.WEIGHT_FAILED

        result = WeightVerificationResult(
            carton_id=carton_id,
            theoretical_weight_g=theoretical,
            measured_weight_g=measured_weight_g,
            deviation_g=deviation,
            is_valid=is_valid,
            allowed_tolerance_g=tolerance,
            message=msg,
        )

        carton.measured_weight_g = measured_weight_g
        carton.verification_result = result
        self._repo.save(carton)
        return result

    def finalize_packing(
        self,
        carton_id: str,
        measured_weight_g: float,
        strict_check: bool = True,
    ) -> CartonPackage:
        """Finalizes package packing after electronic scale verification."""
        carton = self.get_carton(carton_id)
        result = self.verify_check_weigher(carton_id, measured_weight_g)

        if strict_check and not result.is_valid:
            raise BusinessRuleViolationError(
                f"Packing rejected: {result.message}"
            )

        if result.is_valid:
            carton.status = PackingStatus.PACKED
            self._repo.save(carton)

        return carton
