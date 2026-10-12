from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.application.services.packing_service import (
    CartonManifestItem,
    CartonPackage,
    PackItem,
    PackingStatus,
    WeightVerificationResult,
)
from app.modules.documents.infrastructure.models.carton_package import (
    CartonManifestItemModel,
    CartonPackageModel,
)
from app.shared.core.transaction import TransactionalRepository


class PackingRepository(TransactionalRepository):
    """PostgreSQL-backed repository for Carton Packages, manifests, and check-weigher records."""

    def __init__(self, session: Session, auto_commit: bool = True):
        super().__init__(session, auto_commit=auto_commit)

    def save(self, carton: CartonPackage) -> None:
        items_data = [
            {
                "product_id": item.product_id,
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_weight_g": item.unit_weight_g,
            }
            for item in carton.items
        ]

        vr_data = None
        if carton.verification_result:
            vr = carton.verification_result
            vr_data = {
                "carton_id": vr.carton_id,
                "theoretical_weight_g": vr.theoretical_weight_g,
                "measured_weight_g": vr.measured_weight_g,
                "deviation_g": vr.deviation_g,
                "is_valid": vr.is_valid,
                "allowed_tolerance_g": vr.allowed_tolerance_g,
                "message": vr.message,
            }

        status_val = (
            carton.status.value
            if isinstance(carton.status, PackingStatus)
            else str(carton.status)
        )

        model = self.session.get(CartonPackageModel, carton.carton_id)
        if model is None:
            model = CartonPackageModel(
                carton_id=carton.carton_id,
                order_id=carton.order_id,
                packaging_tare_weight_g=carton.packaging_tare_weight_g,
                status=status_val,
                measured_weight_g=carton.measured_weight_g,
                verification_result=vr_data,
                items=items_data,
                created_at=carton.created_at,
            )
            self.session.add(model)
        else:
            model.order_id = carton.order_id
            model.packaging_tare_weight_g = carton.packaging_tare_weight_g
            model.status = status_val
            model.measured_weight_g = carton.measured_weight_g
            model.verification_result = vr_data
            model.items = items_data
            model.created_at = carton.created_at

        self._commit_if_auto()

    def get(self, carton_id: str) -> Optional[CartonPackage]:
        model = self.session.get(CartonPackageModel, carton_id)
        if model is None:
            return None

        items: List[PackItem] = [
            PackItem(
                product_id=it["product_id"],
                sku=it["sku"],
                quantity=it["quantity"],
                unit_weight_g=it["unit_weight_g"],
            )
            for it in (model.items or [])
        ]

        vr: Optional[WeightVerificationResult] = None
        if model.verification_result:
            vrd = model.verification_result
            vr = WeightVerificationResult(
                carton_id=vrd["carton_id"],
                theoretical_weight_g=vrd["theoretical_weight_g"],
                measured_weight_g=vrd["measured_weight_g"],
                deviation_g=vrd["deviation_g"],
                is_valid=vrd["is_valid"],
                allowed_tolerance_g=vrd.get("allowed_tolerance_g", 50.0),
                message=vrd.get("message", ""),
            )

        manifest_rows = self.get_manifest_by_carton(model.carton_id)

        return CartonPackage(
            carton_id=model.carton_id,
            order_id=model.order_id,
            packaging_tare_weight_g=model.packaging_tare_weight_g,
            items=items,
            manifest_items=manifest_rows,
            status=PackingStatus(model.status),
            measured_weight_g=model.measured_weight_g,
            verification_result=vr,
            created_at=model.created_at,
        )

    def exists(self, carton_id: str) -> bool:
        return self.session.get(CartonPackageModel, carton_id) is not None

    def delete(self, carton_id: str) -> None:
        model = self.session.get(CartonPackageModel, carton_id)
        if model:
            self.session.delete(model)
            self._commit_if_auto()

    def save_manifest_items(
        self, carton_id: str, manifest_items: List[CartonManifestItem]
    ) -> None:
        """Persists detailed carton manifest items into relational table."""
        for item in manifest_items:
            m = CartonManifestItemModel(
                carton_id=carton_id,
                package_id=item.package_id or carton_id,
                document_id=item.document_id,
                product_id=item.product_id,
                sku=item.sku,
                quantity=item.quantity,
                lot_number=item.lot_number,
                unit_weight_g=item.unit_weight_g,
            )
            self.session.add(m)
        self._commit_if_auto()

    def get_manifest_by_carton(self, carton_id: str) -> List[CartonManifestItem]:
        """Queries relational manifest lines by carton barcode / SSCC."""
        rows = self.session.execute(
            select(CartonManifestItemModel)
            .where(CartonManifestItemModel.carton_id == carton_id)
            .order_by(CartonManifestItemModel.id)
        ).scalars().all()
        return [
            CartonManifestItem(
                id=int(r.id),
                carton_id=r.carton_id,
                package_id=r.package_id,
                document_id=r.document_id,
                product_id=int(r.product_id),
                sku=r.sku or "",
                quantity=int(r.quantity),
                lot_number=r.lot_number or "",
                unit_weight_g=float(r.unit_weight_g or 0.0),
            )
            for r in rows
        ]

    def get_manifest_by_document(
        self, document_id: int | str
    ) -> List[CartonManifestItem]:
        """Queries relational manifest lines across cartons for a given document."""
        doc_id_int: Optional[int] = None
        try:
            doc_id_int = int(document_id)
        except (ValueError, TypeError):
            pass

        query = select(CartonManifestItemModel).outerjoin(
            CartonPackageModel,
            CartonManifestItemModel.carton_id == CartonPackageModel.carton_id,
        )
        if doc_id_int is not None:
            query = query.where(
                (CartonManifestItemModel.document_id == doc_id_int)
                | (CartonPackageModel.order_id == str(document_id))
            )
        else:
            query = query.where(CartonPackageModel.order_id == str(document_id))

        rows = self.session.execute(
            query.order_by(CartonManifestItemModel.id)
        ).scalars().all()
        return [
            CartonManifestItem(
                id=int(r.id),
                carton_id=r.carton_id,
                package_id=r.package_id,
                document_id=r.document_id,
                product_id=int(r.product_id),
                sku=r.sku or "",
                quantity=int(r.quantity),
                lot_number=r.lot_number or "",
                unit_weight_g=float(r.unit_weight_g or 0.0),
            )
            for r in rows
        ]

    def get_packed_quantity_for_document(
        self, document_id: int | str, product_id: int
    ) -> int:
        """Sums already packed quantity for a specific product under a document."""
        doc_id_int: Optional[int] = None
        try:
            doc_id_int = int(document_id)
        except (ValueError, TypeError):
            pass

        query = select(
            func.coalesce(func.sum(CartonManifestItemModel.quantity), 0)
        ).outerjoin(
            CartonPackageModel,
            CartonManifestItemModel.carton_id == CartonPackageModel.carton_id,
        ).where(
            CartonManifestItemModel.product_id == product_id
        )

        if doc_id_int is not None:
            query = query.where(
                (CartonManifestItemModel.document_id == doc_id_int)
                | (CartonPackageModel.order_id == str(document_id))
            )
        else:
            query = query.where(CartonPackageModel.order_id == str(document_id))

        result = self.session.execute(query).scalar()
        return int(result or 0)

