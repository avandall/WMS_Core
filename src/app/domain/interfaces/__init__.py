from app.domain.interfaces.audit_event_repo import IAuditEventRepo
from app.domain.interfaces.customer_repo import ICustomerRepo
from app.domain.interfaces.document_repo import IDocumentRepo
from app.domain.interfaces.inventory_repo import IInventoryRepo
from app.domain.interfaces.position_repo import IPositionRepo
from app.domain.interfaces.product_repo import IProductRepo
from app.domain.interfaces.user_repo import IUserRepo
from app.domain.interfaces.warehouse_repo import IWarehouseRepo

__all__ = [
    "IAuditEventRepo",
    "ICustomerRepo",
    "IDocumentRepo",
    "IInventoryRepo",
    "IPositionRepo",
    "IProductRepo",
    "IUserRepo",
    "IWarehouseRepo",
]
