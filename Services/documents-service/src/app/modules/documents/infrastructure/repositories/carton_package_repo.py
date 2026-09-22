from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.documents.application.services.packing_service import (
    CartonPackage,
    PackItem,
    PackingStatus,
    WeightVerificationResult,
)
from app.modules.documents.infrastructure.models.carton_package import (
    CartonPackageModel,
)
from app.shared.core.transaction import TransactionalRepository


class PackingRepository(TransactionalRepository):
    """PostgreSQL-backed repository for Carton Packages and check-weigher records."""

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

        return CartonPackage(
            carton_id=model.carton_id,
            order_id=model.order_id,
            packaging_tare_weight_g=model.packaging_tare_weight_g,
            items=items,
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
