from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class CustomerPayload(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""


class CustomerDebtPayload(BaseModel):
    amount: float = 0


class ProductPayload(BaseModel):
    product_id: int = 0
    name: str = ""
    price: float = 0
    description: str = ""


class WarehousePayload(BaseModel):
    name: str = ""


class WarehouseTransferPayload(BaseModel):
    to_warehouse_id: int = 0


class DocumentItemPayload(BaseModel):
    product_id: int = 0
    quantity: int = 0
    unit_price: float = 0


class DocumentPayload(BaseModel):
    source_warehouse_id: int = 0
    destination_warehouse_id: int = 0
    warehouse_id: int = 0
    customer_id: int = 0
    items: list[DocumentItemPayload] = Field(default_factory=list)
    created_by: str = "system"
    note: str = ""
    transaction_type: str = ""
    reason_code: str = ""


class PostDocumentPayload(BaseModel):
    approved_by: str = ""


class AIQueryPayload(BaseModel):
    question: str = ""
    mode: str = "auto"


class ConfirmItemPayload(BaseModel):
    product_id: int = 0
    quantity: int = 0


class ConfirmExecutionPayload(BaseModel):
    items: list[ConfirmItemPayload] = Field(default_factory=list)


class LoginPayload(BaseModel):
    email: str = ""
    password: str = ""


class InspectQaPayload(BaseModel):
    inspected_by: str = "system"
    passed: bool = True
    note: str = ""


class CreateProposalPayload(BaseModel):
    proposal_id: str = ""
    proposal_type: str = "DraftAdjustmentProposal"
    sku_code: str
    warehouse_id: int = 1
    location_code: str = ""
    position_id: int = 0
    current_quantity: int | None = None
    proposed_quantity: int | None = None
    adjustment: int | None = None
    reason: str = ""

    @model_validator(mode="after")
    def validate_location_for_negative_adjustments(self) -> CreateProposalPayload:
        adj = self.adjustment
        if adj is None:
            if self.proposed_quantity is not None and self.current_quantity is not None:
                adj = self.proposed_quantity - self.current_quantity
            else:
                adj = 0

        has_loc = bool(
            (self.location_code and self.location_code.strip())
            or (self.position_id and self.position_id > 0)
        )
        if adj < 0 and not has_loc:
            raise ValueError(
                "location_code or position_id is required for negative inventory adjustments"
            )
        return self


class ApproveProposalPayload(BaseModel):
    digital_signature: str = ""


class RejectProposalPayload(BaseModel):
    rejection_reason: str = "Rejected by manager"


class CancelProposalPayload(BaseModel):
    cancellation_reason: str = "Cancelled by creator"




