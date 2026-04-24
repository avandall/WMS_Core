"""
Mock models for testing to avoid SQLAlchemy dependency issues
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class MockWarehouseModel:
    """Mock WarehouseModel for testing"""
    warehouse_id: int
    location: str
    inventory: Optional[List] = None
    
    def __init__(self, warehouse_id=None, location=None, inventory=None):
        self.warehouse_id = warehouse_id
        self.location = location
        self.inventory = inventory or []


@dataclass
class MockWarehouseInventoryModel:
    """Mock WarehouseInventoryModel for testing"""
    warehouse_id: int
    product_id: int
    quantity: int
    position_code: Optional[str] = None
    
    def __init__(self, warehouse_id=None, product_id=None, quantity=None, position_code=None):
        self.warehouse_id = warehouse_id
        self.product_id = product_id
        self.quantity = quantity
        self.position_code = position_code


@dataclass
class MockProductModel:
    """Mock ProductModel for testing"""
    product_id: int
    name: str
    price: float
    description: Optional[str] = None
    
    def __init__(self, product_id=None, name=None, price=None, description=None):
        self.product_id = product_id
        self.name = name
        self.price = price
        self.description = description


@dataclass
class MockInventoryModel:
    """Mock InventoryModel for testing"""
    product_id: int
    quantity: int
    warehouse_id: Optional[int] = None
    
    def __init__(self, product_id=None, quantity=None, warehouse_id=None):
        self.product_id = product_id
        self.quantity = quantity
        self.warehouse_id = warehouse_id


@dataclass
class MockDocumentModel:
    """Mock DocumentModel for testing"""
    document_id: int
    doc_type: str
    status: str
    from_warehouse_id: Optional[int] = None
    to_warehouse_id: Optional[int] = None
    created_by: Optional[str] = None
    
    def __init__(self, document_id=None, doc_type=None, status=None, from_warehouse_id=None, to_warehouse_id=None, created_by=None):
        self.document_id = document_id
        self.doc_type = doc_type
        self.status = status
        self.from_warehouse_id = from_warehouse_id
        self.to_warehouse_id = to_warehouse_id
        self.created_by = created_by


@dataclass
class MockUserModel:
    """Mock UserModel for testing"""
    user_id: int
    email: str
    role: str
    full_name: Optional[str] = None
    
    def __init__(self, user_id=None, email=None, role=None, full_name=None):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.full_name = full_name


# Mock AuditLogModel to avoid dependency issues
@dataclass
class MockAuditLogModel:
    """Mock AuditLogModel for testing"""
    log_id: int
    action: str
    user_id: int
    timestamp: str
    
    def __init__(self, log_id=None, action=None, user_id=None, timestamp=None):
        self.log_id = log_id
        self.action = action
        self.user_id = user_id
        self.timestamp = timestamp
