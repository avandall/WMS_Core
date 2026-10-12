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
    InvalidQuantityError,
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
class CartonManifestItem:
    """Represents an item in a carton manifest linking package to document, product and lot."""

    carton_id: str
    product_id: int
    quantity: int
    document_id: Optional[int] = None
    package_id: Optional[str] = None
    sku: str = ""
    lot_number: str = ""
    unit_weight_g: float = 0.0
    id: Optional[int] = None


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
    manifest_items: List[CartonManifestItem] = field(default_factory=list)
    status: PackingStatus = PackingStatus.PACKING
    measured_weight_g: Optional[float] = None
    verification_result: Optional[WeightVerificationResult] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def items_weight_g(self) -> float:
        """Calculates total net weight of items in grams."""
        if self.items:
            return sum(item.quantity * item.unit_weight_g for item in self.items)
        return sum(item.quantity * item.unit_weight_g for item in self.manifest_items)

    @property
    def theoretical_weight_g(self) -> float:
        """Calculates gross theoretical weight (items + packaging tare) in grams."""
        return self.items_weight_g + self.packaging_tare_weight_g


class PackingService:
    """Service managing pack station operations, check-weigher weight verification and carton manifests."""

    DEFAULT_TOLERANCE_G: float = 50.0

    def __init__(
        self,
        tolerance_g: float = DEFAULT_TOLERANCE_G,
        repo: Optional[PackingRepository] = None,
        session: Optional[Session] = None,
        document_repo: Optional[Any] = None,
    ) -> None:
        from app.modules.documents.infrastructure.repositories.carton_package_repo import (
            PackingRepository,
        )

        self.tolerance_g = tolerance_g
        self._document_repo = document_repo
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

    def pack_items_to_carton(
        self,
        document_id: int | str,
        carton_code: str,
        items_list: List[Any],
        packaging_tare_weight_g: float = 100.0,
    ) -> CartonPackage:
        """Packs order items into a carton package and records detailed manifest.

        TASK-090: Reconciles total packed quantity against required document export quantity.
        Raises BusinessRuleViolationError if packed quantity would exceed document requirement.
        """
        if not carton_code or not str(carton_code).strip():
            raise ValidationError("carton_code cannot be empty")
        if not items_list:
            raise ValidationError("items_list cannot be empty")

        clean_carton_code = str(carton_code).strip()

        # Parse document ID
        doc_id_int: Optional[int] = None
        try:
            doc_id_int = int(document_id)
        except (ValueError, TypeError):
            pass

        # 1. Fetch document items for reconciliation if document exists in DB / repo
        doc_required_qty: Dict[int, int] = {}
        if self._document_repo is not None:
            doc = self._document_repo.get(document_id)
            if doc is not None and hasattr(doc, "products"):
                for p in doc.products:
                    pid = int(p.product_id)
                    doc_required_qty[pid] = doc_required_qty.get(pid, 0) + int(p.quantity)
        elif self._repo is not None and hasattr(self._repo, "session") and self._repo.session is not None:
            from sqlalchemy import select
            from app.modules.documents.infrastructure.models.document import DocumentModel
            from app.modules.documents.infrastructure.models.document_item import DocumentItemModel

            if doc_id_int is not None:
                doc_model = self._repo.session.execute(
                    select(DocumentModel).where(DocumentModel.document_id == doc_id_int).with_for_update()
                ).scalar_one_or_none()
                if doc_model is not None and doc_model.items:
                    for di in doc_model.items:
                        pid = int(di.product_id)
                        doc_required_qty[pid] = doc_required_qty.get(pid, 0) + int(di.quantity)

        # 2. Normalize items_list and validate quantities
        new_manifest_items: List[CartonManifestItem] = []
        new_pack_items: List[PackItem] = []
        batch_counts: Dict[int, int] = {}

        for item in items_list:
            if isinstance(item, dict):
                pid = int(item["product_id"])
                qty = int(item["quantity"])
                sku = str(item.get("sku", "") or f"SKU-{pid}")
                lot = str(item.get("lot_number", "") or "")
                weight = float(item.get("unit_weight_g", 0.0) or 0.0)
            elif isinstance(item, CartonManifestItem):
                pid = int(item.product_id)
                qty = int(item.quantity)
                sku = str(item.sku or f"SKU-{pid}")
                lot = str(item.lot_number or "")
                weight = float(item.unit_weight_g or 0.0)
            elif isinstance(item, PackItem):
                pid = int(item.product_id)
                qty = int(item.quantity)
                sku = str(item.sku or f"SKU-{pid}")
                lot = ""
                weight = float(item.unit_weight_g or 0.0)
            else:
                pid = int(getattr(item, "product_id"))
                qty = int(getattr(item, "quantity"))
                sku = str(getattr(item, "sku", "") or f"SKU-{pid}")
                lot = str(getattr(item, "lot_number", "") or "")
                weight = float(getattr(item, "unit_weight_g", 0.0) or 0.0)

            if qty <= 0:
                raise InvalidQuantityError(f"Packed quantity must be positive, got {qty} for product {pid}")

            batch_counts[pid] = batch_counts.get(pid, 0) + qty

            new_manifest_items.append(
                CartonManifestItem(
                    carton_id=clean_carton_code,
                    package_id=clean_carton_code,
                    document_id=doc_id_int,
                    product_id=pid,
                    sku=sku,
                    quantity=qty,
                    lot_number=lot,
                    unit_weight_g=weight,
                )
            )
            new_pack_items.append(
                PackItem(
                    product_id=str(pid),
                    sku=sku,
                    quantity=qty,
                    unit_weight_g=weight,
                )
            )

        # 3. Reconcile against document export requirements
        if doc_required_qty:
            for pid, added_qty in batch_counts.items():
                if pid not in doc_required_qty:
                    raise BusinessRuleViolationError(
                        f"Product {pid} is not present in document {document_id}"
                    )
                already_packed = self._repo.get_packed_quantity_for_document(document_id, pid)
                max_allowed = doc_required_qty[pid]
                if already_packed + added_qty > max_allowed:
                    raise BusinessRuleViolationError(
                        f"Cannot pack {added_qty} units of product {pid}: already packed {already_packed}/{max_allowed} for document {document_id}"
                    )

        # 4. Create or update CartonPackage
        if self._repo.exists(clean_carton_code):
            carton = self.get_carton(clean_carton_code)
            if carton.order_id and str(carton.order_id) != str(document_id):
                raise BusinessRuleViolationError(
                    f"Carton '{clean_carton_code}' is already assigned to order '{carton.order_id}'. "
                    f"Cannot mix items from order '{document_id}' into this carton."
                )
            carton.manifest_items.extend(new_manifest_items)
            carton.items.extend(new_pack_items)
        else:
            carton = CartonPackage(
                carton_id=clean_carton_code,
                order_id=str(document_id),
                packaging_tare_weight_g=packaging_tare_weight_g,
                items=new_pack_items,
                manifest_items=new_manifest_items,
            )
            self._identity_map[clean_carton_code] = carton

        self._repo.save(carton)
        self._repo.save_manifest_items(clean_carton_code, new_manifest_items)
        return carton

    def get_carton_manifest(self, carton_code: str) -> List[CartonManifestItem]:
        """Retrieves manifest items for a carton package by barcode / SSCC code."""
        if not carton_code or not str(carton_code).strip():
            raise ValidationError("carton_code cannot be empty")
        clean_code = str(carton_code).strip()
        return self._repo.get_manifest_by_carton(clean_code)

    def get_carton_manifest_details(self, carton_code: str) -> Dict[str, Any]:
        """Returns comprehensive carton package and manifest breakdown."""
        carton = self.get_carton(carton_code)
        manifest_items = self.get_carton_manifest(carton_code)
        return {
            "carton_id": carton.carton_id,
            "order_id": carton.order_id,
            "status": carton.status.value,
            "measured_weight_g": carton.measured_weight_g,
            "packaging_tare_weight_g": carton.packaging_tare_weight_g,
            "theoretical_weight_g": carton.theoretical_weight_g,
            "items_count": len(manifest_items),
            "manifest_items": [
                {
                    "id": it.id,
                    "carton_id": it.carton_id,
                    "package_id": it.package_id,
                    "document_id": it.document_id,
                    "product_id": it.product_id,
                    "sku": it.sku,
                    "quantity": it.quantity,
                    "lot_number": it.lot_number,
                    "unit_weight_g": it.unit_weight_g,
                }
                for it in manifest_items
            ],
        }

    def get_manifest_by_document(self, document_id: int | str) -> List[CartonManifestItem]:
        """Retrieves all packed manifest items across cartons for a given document."""
        return self._repo.get_manifest_by_document(document_id)

    def suggest_packing_box(
        self,
        items: List[Dict[str, Any]],
        available_boxes: Optional[List[Dict[str, Any]]] = None,
        dunnage_buffer: float = 0.10,
    ) -> Dict[str, Any]:
        """TASK-100 / ARCH-01: Native Core 3D-BPP carton box suggestion for packing station.
        
        Evaluates 3D item geometry, orientation, zero-load on fragile items, liquid isolation,
        and billable dimensional weight.
        """
        from shared_utils.algorithms.packing_3d import SuggestPackingBox
        packer = SuggestPackingBox(config=None)
        
        boxes = available_boxes or [
            {"box_id": "BOX-S", "name": "Small Box", "length": 25.0, "width": 20.0, "height": 15.0, "max_weight": 5.0},
            {"box_id": "BOX-M", "name": "Medium Box", "length": 35.0, "width": 28.0, "height": 20.0, "max_weight": 10.0},
            {"box_id": "BOX-L", "name": "Large Box", "length": 45.0, "width": 35.0, "height": 30.0, "max_weight": 20.0},
            {"box_id": "BOX-XL", "name": "Extra Large Box", "length": 60.0, "width": 45.0, "height": 40.0, "max_weight": 30.0},
        ]
        
        total_vol = sum(float(it.get("length", 10.0)) * float(it.get("width", 10.0)) * float(it.get("height", 10.0)) * int(it.get("quantity", 1)) for it in items)
        total_wt = sum(float(it.get("weight", 0.5)) * int(it.get("quantity", 1)) for it in items)
        
        recs = packer._find_optimal_boxes_3d(
            items=items,
            total_volume=total_vol,
            total_weight=total_wt,
            available_boxes=boxes,
            dunnage_buffer=dunnage_buffer,
        )
        return {
            "success": bool(recs),
            "recommendations": recs,
            "selected_box": recs[0] if recs else None,
        }


