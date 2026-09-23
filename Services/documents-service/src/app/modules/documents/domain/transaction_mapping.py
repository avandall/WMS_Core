from __future__ import annotations

from app.modules.documents.domain.entities.document import DocumentType
from app.modules.documents.domain.transaction_types import TransactionType


DOC_TYPE_TO_TRANSACTION_TYPE: dict[DocumentType, TransactionType] = {
    DocumentType.IMPORT: TransactionType.PURCHASE_RECEIPT,
    DocumentType.EXPORT: TransactionType.ADJUSTMENT_OUT,
    DocumentType.SALE: TransactionType.SALES_SHIPMENT,
    DocumentType.TRANSFER: TransactionType.TRANSFER_ISSUE,
    DocumentType.PURCHASE_RETURN: TransactionType.PURCHASE_RETURN_SHIPMENT,
    DocumentType.SALES_RETURN: TransactionType.SALES_RETURN_RECEIPT,
}


def default_transaction_type(doc_type: DocumentType) -> TransactionType:
    return DOC_TYPE_TO_TRANSACTION_TYPE[doc_type]
