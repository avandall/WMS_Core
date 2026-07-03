from __future__ import annotations

import grpc
from fastapi import APIRouter, Depends, HTTPException, Request

from api_gateway.auth import get_current_user
from api_gateway.authz import require_permissions
from api_gateway.errors import grpc_http_exception
from api_gateway.grpc_clients import (
    ai_stub,
    audit_stub,
    call_idempotent,
    customer_stub,
    documents_stub,
    identity_stub,
    inventory_stub,
    product_stub,
    reporting_stub,
    warehouse_ops_stub,
    warehouse_stub,
)
from api_gateway.permissions import Permission
from api_gateway.presenters import (
    audit_event_to_dict,
    customer_to_dict,
    document_to_dict,
    parse_json,
    product_to_dict,
    warehouse_to_dict,
)
from api_gateway.schemas import (
    AIQueryPayload,
    CustomerDebtPayload,
    CustomerPayload,
    DocumentPayload,
    PostDocumentPayload,
    ProductPayload,
    WarehousePayload,
    WarehouseTransferPayload,
    ConfirmExecutionPayload,
    LoginPayload,
)
from api_gateway.gen.wms.customer.v1 import customer_pb2
from api_gateway.gen.wms.inventory.v1 import inventory_pb2
from api_gateway.gen.wms.product.v1 import product_pb2
from api_gateway.gen.wms.warehouse.v1 import warehouse_pb2
from api_gateway.gen.wms.documents.v1 import documents_pb2
from api_gateway.gen.wms.audit.v1 import audit_pb2
from api_gateway.gen.wms.reporting.v1 import reporting_pb2
from api_gateway.gen.wms.ai.v1 import ai_pb2
from api_gateway.gen.wms.identity.v1 import identity_pb2


router = APIRouter(prefix="/api/v1")


@router.post("/auth/login")
def login_auth(payload: LoginPayload):
    email = payload.email.strip().lower()
    password = payload.password

    dev_users = {
        "admin@wms.vn": {"password": "admin123", "user_id": 1, "role": "admin"},
        "warehouse@wms.vn": {"password": "warehouse123", "user_id": 2, "role": "warehouse"},
        "sales@wms.vn": {"password": "sales123", "user_id": 3, "role": "sales"},
        "accountant@wms.vn": {"password": "account123", "user_id": 4, "role": "accountant"},
    }

    user = dev_users.get(email)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    import jwt
    import os
    from datetime import datetime, timezone, timedelta

    secret_key = os.getenv("SECRET_KEY", "replace-with-render-secret")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    expires = datetime.now(timezone.utc) + timedelta(hours=8)

    token = jwt.encode(
        {"sub": str(user["user_id"]), "role": user["role"], "exp": expires},
        secret_key,
        algorithm=algorithm
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "role": user["role"]
    }


def _md(request: Request):
    request_id = getattr(request.state, "request_id", None)
    traceparent = getattr(request.state, "traceparent", None)
    metadata = []
    if request_id:
        metadata.append(("x-request-id", request_id))
    if traceparent:
        metadata.append(("traceparent", traceparent))
    return metadata or None


def _timeout(env: str, default: float) -> float:
    import os

    try:
        return float(os.getenv(env, str(default)))
    except Exception:
        return default


GRPC_TIMEOUT_FAST = _timeout("GRPC_TIMEOUT_FAST", 5.0)
GRPC_TIMEOUT_DEFAULT = _timeout("GRPC_TIMEOUT_DEFAULT", 10.0)
GRPC_TIMEOUT_SLOW = _timeout("GRPC_TIMEOUT_SLOW", 30.0)
GRPC_TIMEOUT_AI = _timeout("GRPC_TIMEOUT_AI", 60.0)


def _grpc_call(fn, request_message, *, request: Request, timeout: float, idempotent: bool = False):
    try:
        if idempotent:
            return call_idempotent(
                fn,
                request_message,
                timeout=timeout,
                metadata=_md(request),
            )
        return fn(request_message, timeout=timeout, metadata=_md(request))
    except grpc.RpcError as exc:
        raise grpc_http_exception(exc)


# ---- Customers ----
@router.get(
    "/customers",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_CUSTOMERS))],
)
def list_customers(request: Request):
    with customer_stub() as stub:
        resp = _grpc_call(
            stub.ListCustomers,
            customer_pb2.ListCustomersRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    customers_list = list(resp.customers)
    if not customers_list:
        return []

    # Fetch all purchases in parallel threads to avoid N+1 serial gRPC calls
    import concurrent.futures
    md = _md(request)

    def fetch_purchases(customer_id: int) -> tuple[int, list]:
        try:
            with customer_stub() as stub2:
                pr = stub2.ListPurchases(
                    customer_pb2.ListPurchasesRequest(customer_id=customer_id),
                    timeout=GRPC_TIMEOUT_FAST,
                    metadata=md,
                )
            return customer_id, list(pr.purchases)
        except Exception:
            return customer_id, []

    purchase_map: dict[int, list] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(customers_list), 10)) as executor:
        futures = {executor.submit(fetch_purchases, int(c.customer_id)): int(c.customer_id) for c in customers_list}
        for future in concurrent.futures.as_completed(futures):
            cid, purchases = future.result()
            purchase_map[cid] = purchases

    results = []
    for c in customers_list:
        d = customer_to_dict(c)
        purchases = purchase_map.get(int(c.customer_id), [])
        d["purchase_count"] = len(purchases)
        d["total_purchased"] = sum(float(p.amount) for p in purchases)
        results.append(d)
    return results


@router.post(
    "/customers",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_CUSTOMERS))],
)
def create_customer(payload: CustomerPayload, request: Request):
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=422, detail="Customer name is required")
    # Duplicate name and email check
    with customer_stub() as stub:
        existing = _grpc_call(
            stub.ListCustomers,
            customer_pb2.ListCustomersRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    for c in existing.customers:
        if c.name.strip().lower() == payload.name.strip().lower():
            raise HTTPException(status_code=409, detail=f"Customer with name '{payload.name}' already exists")
        if payload.email and c.email and c.email.strip().lower() == payload.email.strip().lower():
            raise HTTPException(status_code=409, detail=f"Customer with email '{payload.email}' already exists")
    with customer_stub() as stub:
        resp = _grpc_call(
            stub.CreateCustomer,
            customer_pb2.CreateCustomerRequest(
                name=payload.name,
                email=payload.email,
                phone=payload.phone,
                address=payload.address,
            ),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    d = customer_to_dict(resp)
    d["purchase_count"] = 0
    d["total_purchased"] = 0.0
    return d


@router.get(
    "/customers/{customer_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_CUSTOMERS))],
)
def get_customer(customer_id: int, request: Request):
    with customer_stub() as stub:
        c = _grpc_call(
            stub.GetCustomer,
            customer_pb2.GetCustomerRequest(customer_id=customer_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return customer_to_dict(c)


@router.patch(
    "/customers/{customer_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_CUSTOMERS))],
)
def update_customer(customer_id: int, payload: CustomerPayload, request: Request):
    with customer_stub() as stub:
        c = _grpc_call(
            stub.UpdateCustomer,
            customer_pb2.UpdateCustomerRequest(
                customer_id=customer_id,
                name=payload.name,
                email=payload.email,
                phone=payload.phone,
                address=payload.address,
            ),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return customer_to_dict(c)


@router.patch(
    "/customers/{customer_id}/debt",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_CUSTOMERS))],
)
def update_debt(customer_id: int, payload: CustomerDebtPayload, request: Request):
    with customer_stub() as stub:
        resp = _grpc_call(
            stub.UpdateDebt,
            customer_pb2.UpdateDebtRequest(customer_id=customer_id, amount=payload.amount),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return {"message": resp.message, "delta": float(resp.delta)}


@router.get(
    "/customers/{customer_id}/purchases",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_CUSTOMERS))],
)
def list_purchases(customer_id: int, request: Request):
    with customer_stub() as stub:
        resp = _grpc_call(
            stub.ListPurchases,
            customer_pb2.ListPurchasesRequest(customer_id=customer_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return [
        {
            "purchase_id": int(p.purchase_id),
            "customer_id": int(p.customer_id),
            "amount": float(p.amount),
            "created_at": p.created_at,
        }
        for p in resp.purchases
    ]


# ---- Products ----
@router.get(
    "/products",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_PRODUCTS))],
)
def list_products(request: Request):
    with product_stub() as stub:
        resp = _grpc_call(
            stub.ListProducts,
            product_pb2.ListProductsRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return [product_to_dict(p) for p in resp.products]


@router.post(
    "/products",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_PRODUCTS))],
)
def create_product(payload: ProductPayload, request: Request):
    with product_stub() as stub:
        resp = _grpc_call(
            stub.CreateProduct,
            product_pb2.CreateProductRequest(
                product_id=payload.product_id,
                name=payload.name,
                price=payload.price,
                description=payload.description,
            ),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return product_to_dict(resp)


@router.get(
    "/products/{product_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_PRODUCTS))],
)
def get_product(product_id: int, request: Request):
    with product_stub() as stub:
        p = _grpc_call(
            stub.GetProduct,
            product_pb2.GetProductRequest(product_id=product_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return product_to_dict(p)


@router.put(
    "/products/{product_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_PRODUCTS))],
)
def update_product(product_id: int, payload: ProductPayload, request: Request):
    with product_stub() as stub:
        p = _grpc_call(
            stub.UpdateProduct,
            product_pb2.UpdateProductRequest(
                product_id=product_id,
                name=payload.name,
                price=payload.price,
                description=payload.description,
            ),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return product_to_dict(p)


@router.delete(
    "/products/{product_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_PRODUCTS))],
)
def delete_product(product_id: int, request: Request):
    with product_stub() as stub:
        resp = _grpc_call(
            stub.DeleteProduct,
            product_pb2.DeleteProductRequest(product_id=product_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return {"message": resp.message}


# ---- Warehouses ----
@router.get(
    "/warehouses",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_WAREHOUSES))],
)
def list_warehouses(request: Request):
    with warehouse_stub() as stub:
        resp = _grpc_call(
            stub.ListWarehouses,
            warehouse_pb2.ListWarehousesRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return [warehouse_to_dict(w) for w in resp.warehouses]


@router.post(
    "/warehouses",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
def create_warehouse(payload: WarehousePayload, request: Request):
    with warehouse_stub() as stub:
        w = _grpc_call(
            stub.CreateWarehouse,
            warehouse_pb2.CreateWarehouseRequest(name=payload.name),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return warehouse_to_dict(w)


@router.get(
    "/warehouses/{warehouse_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_WAREHOUSES))],
)
def get_warehouse(warehouse_id: int, request: Request):
    with warehouse_stub() as stub:
        w = _grpc_call(
            stub.GetWarehouse,
            warehouse_pb2.GetWarehouseRequest(warehouse_id=warehouse_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return warehouse_to_dict(w)


@router.delete(
    "/warehouses/{warehouse_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
def delete_warehouse(warehouse_id: int, request: Request):
    with warehouse_stub() as stub:
        resp = _grpc_call(
            stub.DeleteWarehouse,
            warehouse_pb2.DeleteWarehouseRequest(warehouse_id=warehouse_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return {"message": resp.message}


@router.post(
    "/warehouses/{warehouse_id}/transfer",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
def transfer_all_inventory(warehouse_id: int, payload: WarehouseTransferPayload, request: Request):
    with warehouse_stub() as stub:
        resp = _grpc_call(
            stub.TransferAllInventory,
            warehouse_pb2.TransferAllInventoryRequest(
                warehouse_id=warehouse_id, to_warehouse_id=payload.to_warehouse_id
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return {
        "from_warehouse_id": int(resp.from_warehouse_id),
        "to_warehouse_id": int(resp.to_warehouse_id),
        "transferred_items": [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in resp.transferred_items],
        "message": resp.message,
    }


@router.get(
    "/warehouse-operations/system-overview",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def system_overview(request: Request):
    with warehouse_ops_stub() as stub:
        resp = _grpc_call(
            stub.GetSystemOverview,
            warehouse_pb2.GetSystemOverviewRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return {
        "total_warehouses": int(resp.total_warehouses),
        "total_products": int(resp.total_products),
        "total_inventory_value": float(resp.total_inventory_value),
        "warehouses": list(resp.warehouses),
    }


@router.get(
    "/warehouse-operations/inventory-health",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def inventory_health(request: Request):
    with warehouse_ops_stub() as stub:
        resp = _grpc_call(
            stub.GetInventoryHealth,
            warehouse_pb2.GetInventoryHealthRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    return {
        "system_health_score": float(resp.system_health_score),
        "warehouses": [
            {
                "warehouse_id": int(w.warehouse_id),
                "location": w.location,
                "total_value": float(w.total_value),
                "health_score": float(w.health_score),
                "products": [
                    {"product_id": int(p.product_id), "name": p.name, "quantity": int(p.quantity), "value": float(p.value)}
                    for p in w.products
                ],
            }
            for w in resp.warehouses
        ],
    }


@router.get(
    "/warehouse-operations/optimize-distribution/{product_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def optimize_distribution(product_id: int, request: Request):
    with warehouse_ops_stub() as stub:
        resp = _grpc_call(
            stub.OptimizeDistribution,
            warehouse_pb2.OptimizeDistributionRequest(product_id=product_id),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    if resp.error:
        raise HTTPException(status_code=404, detail=resp.error)
    return {
        "product_id": int(resp.product_id),
        "product_name": resp.product_name,
        "distribution": [{"warehouse_id": int(d.warehouse_id), "location": d.location, "quantity": int(d.quantity)} for d in resp.distribution],
        "recommendations": list(resp.recommendations),
    }


# ---- Documents ----
@router.post(
    "/documents/import",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_CREATE_IMPORT))],
)
def create_import_document(
    payload: DocumentPayload,
    request: Request,
):
    with documents_stub() as stub:
        doc = _grpc_call(
            stub.CreateImport,
            documents_pb2.CreateDocumentRequest(
                to_warehouse_id=payload.destination_warehouse_id or payload.warehouse_id,
                items=[
                    documents_pb2.DocumentItem(
                        product_id=i.product_id,
                        quantity=i.quantity,
                        unit_price=i.unit_price,
                    )
                    for i in payload.items
                ],
                created_by=payload.created_by,
                note=payload.note,
                transaction_type=payload.transaction_type or "",
                reason_code=payload.reason_code or "",
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return document_to_dict(doc)


@router.post(
    "/documents/export",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_CREATE_EXPORT))],
)
def create_export_document(payload: DocumentPayload, request: Request):
    with documents_stub() as stub:
        doc = _grpc_call(
            stub.CreateExport,
            documents_pb2.CreateDocumentRequest(
                from_warehouse_id=payload.source_warehouse_id or payload.warehouse_id,
                items=[
                    documents_pb2.DocumentItem(
                        product_id=i.product_id,
                        quantity=i.quantity,
                        unit_price=i.unit_price,
                    )
                    for i in payload.items
                ],
                created_by=payload.created_by,
                note=payload.note,
                transaction_type=payload.transaction_type or "",
                reason_code=payload.reason_code or "",
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return document_to_dict(doc)


@router.post(
    "/documents/sale",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_CREATE_EXPORT))],
)
def create_sale_document(payload: DocumentPayload, request: Request):
    with documents_stub() as stub:
        doc = _grpc_call(
            stub.CreateSale,
            documents_pb2.CreateDocumentRequest(
                from_warehouse_id=payload.source_warehouse_id or payload.warehouse_id,
                customer_id=payload.customer_id,
                items=[
                    documents_pb2.DocumentItem(
                        product_id=i.product_id,
                        quantity=i.quantity,
                        unit_price=i.unit_price,
                    )
                    for i in payload.items
                ],
                created_by=payload.created_by,
                note=payload.note,
                transaction_type=payload.transaction_type or "",
                reason_code=payload.reason_code or "",
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return document_to_dict(doc)


@router.post(
    "/documents/transfer",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_CREATE_TRANSFER))],
)
def create_transfer_document(payload: DocumentPayload, request: Request):
    with documents_stub() as stub:
        doc = _grpc_call(
            stub.CreateTransfer,
            documents_pb2.CreateDocumentRequest(
                from_warehouse_id=payload.source_warehouse_id,
                to_warehouse_id=payload.destination_warehouse_id,
                items=[
                    documents_pb2.DocumentItem(
                        product_id=i.product_id,
                        quantity=i.quantity,
                        unit_price=i.unit_price,
                    )
                    for i in payload.items
                ],
                created_by=payload.created_by,
                note=payload.note,
                transaction_type=payload.transaction_type or "",
                reason_code=payload.reason_code or "",
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return document_to_dict(doc)


@router.post(
    "/documents/{document_id}/post",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_POST))],
    deprecated=True,
)
def post_document(document_id: int, payload: PostDocumentPayload, request: Request):
    import warnings
    warnings.warn(
        "POST /api/v1/documents/{document_id}/post is deprecated. Use POST /api/v1/documents/{document_id}/approve instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.PostDocument,
            documents_pb2.PostDocumentRequest(document_id=document_id, approved_by=payload.approved_by),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return {"message": resp.message}


# Phase 7: Approve without stock movement
@router.post(
    "/documents/{document_id}/approve",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_POST))],
)
def approve_document(document_id: int, payload: PostDocumentPayload, request: Request):
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.ApproveRequest,
            documents_pb2.ApproveRequestRequest(document_id=document_id, approved_by=payload.approved_by),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return {"message": resp.message}


# Phase 8: Sales reservation workflow
@router.post(
    "/documents/{document_id}/reserve",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_POST))],
)
def reserve_document(document_id: int, request: Request):
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.ReserveRequest,
            documents_pb2.ReserveRequestRequest(document_id=document_id),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return {"message": resp.message}


@router.post(
    "/documents/{document_id}/release-reservation",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_POST))],
)
def release_document_reservation(document_id: int, request: Request):
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.ReleaseReservation,
            documents_pb2.ReleaseReservationRequest(document_id=document_id),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return {"message": resp.message}


# Phase 10: Execution Confirmation
@router.post(
    "/documents/{document_id}/start-execution",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_POST))],
)
def start_execution(document_id: int, request: Request):
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.StartExecution,
            documents_pb2.StartExecutionRequest(document_id=document_id),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return {"message": resp.message}


@router.post(
    "/documents/{document_id}/confirm",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_POST))],
)
def confirm_document_execution(document_id: int, payload: ConfirmExecutionPayload, request: Request):
    # 1. Get the document details to know the status BEFORE confirming
    with documents_stub() as doc_stub:
        try:
            doc = _grpc_call(
                doc_stub.GetDocument,
                documents_pb2.GetDocumentRequest(document_id=document_id),
                request=request,
                timeout=GRPC_TIMEOUT_DEFAULT,
            )
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Document not found")

    doc_type = (doc.doc_type or "").upper()
    tx_type = (doc.transaction_type or "").upper()
    current_status = (doc.status or "").upper()

    # Determine if it's a Transfer Issue or Receipt
    is_transfer_receipt = (doc_type == "TRANSFER" and current_status == "EXECUTED")

    # 2. Update the document side: executed_qty and difference_qty
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.ConfirmExecution,
            documents_pb2.ConfirmExecutionRequest(
                document_id=document_id,
                items=[
                    documents_pb2.DocumentItem(
                        product_id=item.product_id,
                        quantity=item.quantity,
                    )
                    for item in payload.items
                ],
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )

    # Coordinate inventory confirmation based on document/transaction type
    REQUIRES_RESERVATION = {"SALES_SHIPMENT", "PRODUCTION_ISSUE", "TRANSFER_ISSUE"}
    REQUIRES_REASON_CODE = {"ADJUSTMENT_IN", "ADJUSTMENT_OUT", "SCRAP", "INTERNAL_CONSUMPTION"}
    OUTBOUND_TYPES = {"SALES_SHIPMENT", "PRODUCTION_ISSUE", "PURCHASE_RETURN_SHIPMENT", "TRANSFER_ISSUE", "INTERNAL_CONSUMPTION", "SCRAP", "ADJUSTMENT_OUT"}

    if doc_type == "TRANSFER":
        if is_transfer_receipt:
            target_tx_type = "TRANSFER_RECEIPT"
            # TRANSFER_RECEIPT: warehouse_id = to_warehouse_id, source_warehouse_id = from_warehouse_id
            with inventory_stub() as inv_stub:
                for item in payload.items:
                    _grpc_call(
                        inv_stub.ConfirmInventoryTransaction,
                        inventory_pb2.ConfirmInventoryTransactionRequest(
                            transaction_type="TRANSFER_RECEIPT",
                            product_id=item.product_id,
                            warehouse_id=doc.to_warehouse_id,
                            quantity=item.quantity,
                            reservation_id=0,
                            user_id="system",
                            idempotency_key=f"confirm_{document_id}_{item.product_id}_receipt",
                            source_warehouse_id=doc.from_warehouse_id,
                        ),
                        request=request,
                        timeout=GRPC_TIMEOUT_SLOW,
                    )
            # Transition document to COMPLETED
            with documents_stub() as doc_stub:
                _grpc_call(
                    doc_stub.CompleteRequest,
                    documents_pb2.CompleteRequestRequest(document_id=document_id),
                    request=request,
                    timeout=GRPC_TIMEOUT_SLOW,
                )
        else:
            target_tx_type = "TRANSFER_ISSUE"
            # TRANSFER_ISSUE: warehouse_id = from_warehouse_id
            with inventory_stub() as inv_stub:
                for item in payload.items:
                    _grpc_call(
                        inv_stub.ConfirmInventoryTransaction,
                        inventory_pb2.ConfirmInventoryTransactionRequest(
                            transaction_type="TRANSFER_ISSUE",
                            product_id=item.product_id,
                            warehouse_id=doc.from_warehouse_id,
                            quantity=item.quantity,
                            reservation_id=0,
                            user_id="system",
                            idempotency_key=f"confirm_{document_id}_{item.product_id}_issue",
                        ),
                        request=request,
                        timeout=GRPC_TIMEOUT_SLOW,
                    )
    else:
        # Resolve target transaction type for other documents
        if tx_type:
            target_tx_type = tx_type
        else:
            if doc_type in ("SALE", "SALES_SHIPMENT"):
                target_tx_type = "SALES_SHIPMENT"
            elif doc_type in ("IMPORT", "PURCHASE_RECEIPT"):
                target_tx_type = "PURCHASE_RECEIPT"
            elif doc_type in ("EXPORT", "SCRAP"):
                target_tx_type = "SCRAP"
            else:
                target_tx_type = doc_type

        # Validate reason code
        if target_tx_type in REQUIRES_REASON_CODE and not doc.reason_code:
            raise HTTPException(status_code=400, detail=f"Reason code is required for {target_tx_type}")

        # Determine warehouse and confirmation path
        is_outbound = target_tx_type in OUTBOUND_TYPES
        wh_id = doc.from_warehouse_id if is_outbound else (doc.to_warehouse_id or doc.from_warehouse_id)

        if target_tx_type in REQUIRES_RESERVATION:
            with inventory_stub() as inv_stub:
                # Query reservations to find the matching ones for this document
                reservations_resp = _grpc_call(
                    inv_stub.ListReservations,
                    inventory_pb2.ListReservationsRequest(status="RESERVED"),
                    request=request,
                    timeout=GRPC_TIMEOUT_DEFAULT,
                )

                # Match by document_id and product_id
                reservations_by_product = {
                    r.product_id: r
                    for r in reservations_resp.reservations
                    if r.document_id == document_id
                }

                for item in payload.items:
                    res = reservations_by_product.get(item.product_id)
                    res_id = res.id if res else 0
                    item_wh_id = res.warehouse_id if res else wh_id

                    _grpc_call(
                        inv_stub.ConfirmInventoryTransaction,
                        inventory_pb2.ConfirmInventoryTransactionRequest(
                            transaction_type=target_tx_type,
                            product_id=item.product_id,
                            warehouse_id=item_wh_id,
                            quantity=item.quantity,
                            reservation_id=res_id,
                            user_id="system",
                            idempotency_key=f"confirm_{document_id}_{item.product_id}",
                        ),
                        request=request,
                        timeout=GRPC_TIMEOUT_SLOW,
                    )
        else:
            with inventory_stub() as inv_stub:
                for item in payload.items:
                    _grpc_call(
                        inv_stub.ConfirmInventoryTransaction,
                        inventory_pb2.ConfirmInventoryTransactionRequest(
                            transaction_type=target_tx_type,
                            product_id=item.product_id,
                            warehouse_id=wh_id,
                            quantity=item.quantity,
                            reservation_id=0,  # Direct stock confirmation
                            user_id="system",
                            idempotency_key=f"confirm_{document_id}_{item.product_id}",
                        ),
                        request=request,
                        timeout=GRPC_TIMEOUT_SLOW,
                    )

    return {"message": resp.message}


@router.post(
    "/documents/{document_id}/complete",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_POST))],
)
def complete_document(document_id: int, request: Request):
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.CompleteRequest,
            documents_pb2.CompleteRequestRequest(document_id=document_id),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return {"message": resp.message}


@router.get(

    "/documents/{document_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_DOCUMENTS))],
)
def get_document(document_id: int, request: Request):
    with documents_stub() as stub:
        doc = _grpc_call(
            stub.GetDocument,
            documents_pb2.GetDocumentRequest(document_id=document_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    if not doc.document_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_to_dict(doc)


@router.get(
    "/documents",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_DOCUMENTS))],
)
def list_documents(request: Request, doc_type: str | None = None, page: int = 1, page_size: int = 20):
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.ListDocuments,
            documents_pb2.ListDocumentsRequest(doc_type=doc_type or "", page=page, page_size=page_size),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    return [
        {
            "document_id": int(d.document_id),
            "doc_type": (d.doc_type.split(".")[-1].lower() if d.doc_type and "." in d.doc_type else (d.doc_type.lower() if d.doc_type else "unknown")),
            "status": d.status.split(".")[-1].lower() if d.status and "." in d.status else (d.status.lower() if d.status else "draft"),
            "created_by": getattr(d, "created_by", None),
            "created_at": getattr(d, "created_at", None),
            "customer_id": getattr(d, "customer_id", None),
        }
        for d in resp.documents
    ]


@router.delete(
    "/documents/{document_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_DOCUMENTS))],
)
def delete_document(document_id: int, request: Request):
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.DeleteDocument,
            documents_pb2.DeleteDocumentRequest(document_id=document_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return {"message": resp.message}


# ---- Audit ----
@router.get(
    "/audit-events",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_USERS))],
)
def list_audit_events(request: Request, limit: int = 100, offset: int = 0):
    with audit_stub() as stub:
        resp = _grpc_call(
            stub.ListEvents,
            audit_pb2.ListEventsRequest(limit=limit, offset=offset),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return [audit_event_to_dict(e) for e in resp.events]


@router.get(
    "/audit-events/{event_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_USERS))],
)
def get_audit_event(event_id: int, request: Request):
    with audit_stub() as stub:
        e = _grpc_call(
            stub.GetEvent,
            audit_pb2.GetEventRequest(id=event_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    if not e.id:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return audit_event_to_dict(e)


# ---- Reporting ----
@router.get(
    "/reports/inventory",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def report_inventory(request: Request, warehouse_id: int | None = None, low_stock_threshold: int = 10):
    with reporting_stub() as stub:
        resp = _grpc_call(
            stub.InventoryReport,
            reporting_pb2.InventoryReportRequest(
                warehouse_id=int(warehouse_id or 0),
                low_stock_threshold=int(low_stock_threshold),
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    return parse_json(resp.json)


@router.get(
    "/reports/inventory/list",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def report_inventory_list(request: Request):
    with reporting_stub() as stub:
        resp = _grpc_call(
            stub.InventoryList,
            reporting_pb2.InventoryListRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    return parse_json(resp.json)


@router.get(
    "/reports/warehouse/{warehouse_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def report_warehouse(
    warehouse_id: int,
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
):
    with reporting_stub() as stub:
        resp = _grpc_call(
            stub.WarehouseReport,
            reporting_pb2.WarehouseReportRequest(
                warehouse_id=warehouse_id,
                start_date=start_date or "",
                end_date=end_date or "",
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    return parse_json(resp.json)


@router.get(
    "/reports/documents",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def report_documents(request: Request, start_date: str | None = None, end_date: str | None = None):
    with reporting_stub() as stub:
        resp = _grpc_call(
            stub.DocumentsReport,
            reporting_pb2.DocumentsReportRequest(
                start_date=start_date or "",
                end_date=end_date or "",
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    return parse_json(resp.json)


@router.get(
    "/reports/product/{product_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def report_product(
    product_id: int,
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
):
    with reporting_stub() as stub:
        resp = _grpc_call(
            stub.ProductReport,
            reporting_pb2.ProductReportRequest(
                product_id=product_id,
                start_date=start_date or "",
                end_date=end_date or "",
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    return parse_json(resp.json)


@router.get(
    "/reports/sales",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))],
)
def report_sales(
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    customer_id: int | None = None,
    salesperson: str | None = None,
):
    with reporting_stub() as stub:
        resp = _grpc_call(
            stub.SalesReport,
            reporting_pb2.SalesReportRequest(
                start_date=start_date or "",
                end_date=end_date or "",
                customer_id=int(customer_id or 0),
                salesperson=salesperson or "",
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    raw = parse_json(resp.json)
    items = raw.get("items", []) if isinstance(raw, dict) else []

    # Fetch customer names so report shows real names instead of IDs
    customer_map: dict[int, str] = {}
    try:
        with customer_stub() as cstub:
            cresp = _grpc_call(
                cstub.ListCustomers,
                customer_pb2.ListCustomersRequest(),
                request=request,
                timeout=GRPC_TIMEOUT_DEFAULT,
                idempotent=True,
            )
        for c in cresp.customers:
            customer_map[int(c.customer_id)] = c.name
    except Exception:
        pass

    total_sales = sum(float(i.get("total_value", 0)) for i in items)
    unique_customers = len({i["customer_id"] for i in items if i.get("customer_id")})
    total_debt = sum(customer_map.get(int(i["customer_id"]), "") and 0 or 0 for i in items)

    # Fetch document details for salesperson info
    doc_salesperson_map: dict[int, str] = {}
    try:
        with documents_stub() as dstub:
            dresp = _grpc_call(
                dstub.ListDocuments,
                documents_pb2.ListDocumentsRequest(doc_type="sale", page=1, page_size=200),
                request=request,
                timeout=GRPC_TIMEOUT_SLOW,
                idempotent=True,
            )
        for d in dresp.documents:
            doc_salesperson_map[int(d.document_id)] = getattr(d, "created_by", "-") or "-"
    except Exception:
        pass

    sales = []
    for i in items:
        cid = i.get("customer_id")
        cname = customer_map.get(int(cid), f"Customer #{cid}") if cid else "-"
        doc_id = i.get("document_id")
        sp = doc_salesperson_map.get(int(doc_id), i.get("created_by", "-")) if doc_id else i.get("created_by", "-")
        sales.append({
            "document_id": doc_id,
            "sale_date": i.get("created_at") or i.get("updated_at"),
            "customer_id": cid,
            "customer_name": cname,
            "customer_debt": 0.0,
            "salesperson": sp or "-",
            "total_sale": float(i.get("total_value", 0)),
            "total_quantity": int(i.get("total_quantity", 0)),
            "status": i.get("status", ""),
        })

    return {
        "summary": {
            "total_sales": total_sales,
            "total_debt": total_debt,
            "transaction_count": len(items),
            "unique_customers": unique_customers,
            "period": {"start": start_date, "end": end_date},
        },
        "sales": sales,
    }


# ---- AI ----
@router.post("/ai/backend-query")
def ai_backend_query(request: Request, payload: dict):
    """Called by the AI service to execute structured data queries against real data."""
    template = payload.get("template", {})
    intent = template.get("intent", "unknown")
    target = template.get("target", "unknown")
    filters = template.get("filters", {})
    limit = int(template.get("limit") or 20)
    raw_question = template.get("raw_question", "")

    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def _resolve_product(pid_raw, all_products):
        """Map user-supplied product number to actual product_id.
        If the number matches an actual ID use it; otherwise treat as 1-based index."""
        pid = _int(pid_raw)
        if pid is None:
            return None, None
        actual_ids = [p["product_id"] for p in all_products]
        if pid in actual_ids:
            idx = actual_ids.index(pid)
            return pid, all_products[idx]
        if 1 <= pid <= len(all_products):
            p = all_products[pid - 1]
            return p["product_id"], p
        return pid, None

    results: dict = {}
    try:
        is_inventory = target in ("inventory", "positions") or intent == "inventory_lookup"
        is_customer = target == "customers" or intent == "customer_lookup"
        is_product = target == "products" or intent == "product_lookup"
        is_document = target == "documents" or intent == "document_lookup"
        is_warehouse = target == "warehouses" or intent == "warehouse_lookup"
        is_reporting = target in ("reporting", "orders")

        if is_inventory:
            # Always fetch product list first for ID resolution
            with product_stub() as stub:
                presp = _grpc_call(stub.ListProducts, product_pb2.ListProductsRequest(),
                                   request=request, timeout=GRPC_TIMEOUT_DEFAULT, idempotent=True)
            all_products = [product_to_dict(p) for p in presp.products]

            with inventory_stub() as stub:
                iresp = _grpc_call(stub.GetInventoryByWarehouse,
                                   inventory_pb2.GetInventoryByWarehouseRequest(),
                                   request=request, timeout=GRPC_TIMEOUT_DEFAULT, idempotent=True)
            all_rows = [{"product_id": int(r.product_id), "warehouse_id": int(r.warehouse_id),
                         "warehouse_name": r.warehouse_name, "quantity": int(r.quantity)}
                        for r in iresp.rows]
            product_by_id = {p["product_id"]: p for p in all_products}

            pid_raw = filters.get("product_id") or filters.get("sku")
            wid = _int(filters.get("warehouse_id"))
            pid, pinfo = _resolve_product(pid_raw, all_products) if pid_raw is not None else (None, None)
            pname = pinfo["name"] if pinfo else (f"Product {pid}" if pid else None)

            if pid is not None and wid is not None:
                rows = [r for r in all_rows if r["product_id"] == pid and r["warehouse_id"] == wid]
                qty = rows[0]["quantity"] if rows else 0
                wname = rows[0]["warehouse_name"] if rows else f"Warehouse {wid}"
                answer = f"{pname} has {qty} unit(s) in {wname} (warehouse ID {wid})."
                results = {"items": rows, "total_quantity": qty, "answer": answer}
            elif pid is not None:
                rows = [r for r in all_rows if r["product_id"] == pid]
                total = sum(r["quantity"] for r in rows)
                detail = "; ".join(f"{r['warehouse_name']}: {r['quantity']}" for r in rows) or "no stock"
                answer = f"{pname} total stock: {total} unit(s). {detail}."
                results = {"items": rows, "total_quantity": total, "answer": answer}
            elif wid is not None:
                rows = [r for r in all_rows if r["warehouse_id"] == wid]
                total = sum(r["quantity"] for r in rows)
                wname = rows[0]["warehouse_name"] if rows else f"Warehouse {wid}"
                lines = "; ".join(f"{product_by_id.get(r['product_id'], {}).get('name', r['product_id'])}: {r['quantity']}" for r in rows[:10])
                answer = f"{wname}: {len(rows)} product type(s), {total} total unit(s). {lines}."
                results = {"items": rows[:limit], "total_quantity": total, "answer": answer}
            else:
                total = sum(r["quantity"] for r in all_rows)
                answer = f"Total inventory: {total} unit(s) across {len(all_rows)} product-warehouse combination(s)."
                results = {"items": all_rows[:limit], "total_quantity": total, "answer": answer}

        elif is_customer:
            with customer_stub() as stub:
                resp = _grpc_call(stub.ListCustomers, customer_pb2.ListCustomersRequest(),
                                  request=request, timeout=GRPC_TIMEOUT_DEFAULT, idempotent=True)
            rows = [customer_to_dict(c) for c in resp.customers]
            cid = _int(filters.get("customer_id"))
            if cid:
                rows = [r for r in rows if r["customer_id"] == cid]
            rows = rows[:limit]
            names = ", ".join(r["name"] for r in rows[:5])
            results = {"items": rows, "count": len(rows), "answer": f"Found {len(rows)} customer(s): {names}."}

        elif is_product:
            with product_stub() as stub:
                resp = _grpc_call(stub.ListProducts, product_pb2.ListProductsRequest(),
                                  request=request, timeout=GRPC_TIMEOUT_DEFAULT, idempotent=True)
            rows = [product_to_dict(p) for p in resp.products][:limit]
            names = ", ".join(r["name"] for r in rows[:5])
            results = {"items": rows, "count": len(rows), "answer": f"Found {len(rows)} product(s): {names}."}

        elif is_document:
            with documents_stub() as stub:
                resp = _grpc_call(stub.ListDocuments,
                                  documents_pb2.ListDocumentsRequest(doc_type=str(filters.get("doc_type", "")), page=1, page_size=limit),
                                  request=request, timeout=GRPC_TIMEOUT_SLOW, idempotent=True)
            rows = [{"document_id": int(d.document_id),
                     "doc_type": (d.doc_type.split(".")[-1].lower() if d.doc_type and "." in d.doc_type else (d.doc_type.lower() if d.doc_type else "unknown")),
                     "status": (d.status.split(".")[-1].lower() if d.status and "." in d.status else (d.status.lower() if d.status else "draft")),
                     "created_by": getattr(d, "created_by", None),
                     "created_at": getattr(d, "created_at", None)}
                    for d in resp.documents]
            results = {"items": rows, "count": len(rows), "answer": f"Found {len(rows)} document(s)."}

        elif is_warehouse:
            with warehouse_stub() as stub:
                resp = _grpc_call(stub.ListWarehouses, warehouse_pb2.ListWarehousesRequest(),
                                  request=request, timeout=GRPC_TIMEOUT_DEFAULT, idempotent=True)
            rows = [warehouse_to_dict(w) for w in resp.warehouses][:limit]
            names = ", ".join(r["name"] for r in rows[:5])
            results = {"items": rows, "count": len(rows), "answer": f"Found {len(rows)} warehouse(s): {names}."}

        elif is_reporting:
            with reporting_stub() as stub:
                resp = _grpc_call(stub.SalesReport,
                                  reporting_pb2.SalesReportRequest(
                                      customer_id=_int(filters.get("customer_id")) or 0,
                                      salesperson=str(filters.get("salesperson", "")),
                                      start_date="", end_date=""),
                                  request=request, timeout=GRPC_TIMEOUT_SLOW, idempotent=True)
            raw = parse_json(resp.json)
            items = raw.get("items", []) if isinstance(raw, dict) else []
            total = sum(float(i.get("total_value", 0)) for i in items)
            results = {"items": items[:limit], "total_value": total,
                       "answer": f"Sales: {len(items)} transaction(s), total ${total:.2f}."}

        else:
            # General question — return None answer so generation.py falls back to Groq chat
            results = {"answer": None}

    except Exception as exc:
        results = {"answer": f"Data query failed: {exc}", "error": str(exc)}

    return results


@router.post("/ai/query", dependencies=[Depends(get_current_user)])
def ai_query(payload: AIQueryPayload, request: Request):
    with ai_stub() as stub:
        resp = _grpc_call(
            stub.Query,
            ai_pb2.QueryRequest(question=payload.question, mode=payload.mode),
            request=request,
            timeout=GRPC_TIMEOUT_AI,
        )
    return {"success": bool(resp.success), "mode": resp.mode, "response": resp.response, "error": resp.error}


@router.get("/ai/status", dependencies=[Depends(get_current_user)])
def ai_status(request: Request):
    with ai_stub() as stub:
        resp = _grpc_call(
            stub.Status,
            ai_pb2.StatusRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return parse_json(resp.json)


# ---- Inventory ----
@router.get(
    "/inventory",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_INVENTORY))],
)
def list_inventory(request: Request):
    with inventory_stub() as stub:
        resp = _grpc_call(
            stub.ListInventoryItems,
            inventory_pb2.ListInventoryItemsRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in resp.items]


@router.get(
    "/inventory/by-warehouse",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_INVENTORY))],
)
def inventory_by_warehouse(request: Request):
    with inventory_stub() as stub:
        resp = _grpc_call(
            stub.GetInventoryByWarehouse,
            inventory_pb2.GetInventoryByWarehouseRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
            idempotent=True,
        )
    # Fetch warehouse names to replace numeric-string warehouse_name values
    warehouse_name_map: dict[int, str] = {}
    try:
        with warehouse_stub() as wstub:
            wresp = _grpc_call(
                wstub.ListWarehouses,
                warehouse_pb2.ListWarehousesRequest(),
                request=request,
                timeout=GRPC_TIMEOUT_DEFAULT,
                idempotent=True,
            )
        for w in wresp.warehouses:
            warehouse_name_map[int(w.warehouse_id)] = w.location or str(w.warehouse_id)
    except Exception:
        pass

    return [
        {
            "product_id": int(r.product_id),
            "warehouse_id": int(r.warehouse_id),
            "warehouse_name": warehouse_name_map.get(int(r.warehouse_id), r.warehouse_name or str(r.warehouse_id)),
            "quantity": int(r.quantity),
            # Phase 3: Quantity matrix fields
            "physical_qty": int(r.physical_qty),
            "reserved_qty": int(r.reserved_qty),
            "incoming_qty": int(r.incoming_qty),
            "in_transit_qty": int(r.in_transit_qty),
            "available_qty": int(r.available_qty),
        }
        for r in resp.rows
    ]


@router.get(
    "/inventory/{product_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_INVENTORY))],
)
def product_quantity(product_id: int, request: Request):
    with inventory_stub() as stub:
        resp = _grpc_call(
            stub.GetProductQuantity,
            inventory_pb2.GetProductQuantityRequest(product_id=product_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return {"product_id": int(resp.product_id), "quantity": int(resp.quantity)}


# Phase 5: Availability and reservations
@router.get(
    "/inventory/availability",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_INVENTORY))],
)
def get_availability(product_id: int, warehouse_id: int, request: Request):
    with inventory_stub() as stub:
        resp = _grpc_call(
            stub.GetAvailability,
            inventory_pb2.GetAvailabilityRequest(product_id=product_id, warehouse_id=warehouse_id),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return {
        "product_id": int(resp.product_id),
        "warehouse_id": int(resp.warehouse_id),
        "physical_qty": int(resp.physical_qty),
        "reserved_qty": int(resp.reserved_qty),
        "available_qty": int(resp.available_qty),
    }


@router.get(
    "/inventory/reservations",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_INVENTORY))],
)
def list_reservations(
    product_id: int | None = None,
    warehouse_id: int | None = None,
    status: str | None = None,
    request: Request = None,
):
    with inventory_stub() as stub:
        req = inventory_pb2.ListReservationsRequest()
        if product_id is not None:
            req.product_id = product_id
        if warehouse_id is not None:
            req.warehouse_id = warehouse_id
        if status is not None:
            req.status = status
        resp = _grpc_call(
            stub.ListReservations,
            req,
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return [
        {
            "id": int(r.id),
            "source_type": r.source_type,
            "source_id": int(r.source_id) if r.source_id else None,
            "document_id": int(r.document_id) if r.document_id else None,
            "product_id": int(r.product_id),
            "warehouse_id": int(r.warehouse_id),
            "requested_qty": int(r.requested_qty),
            "reserved_qty": int(r.reserved_qty),
            "released_qty": int(r.released_qty),
            "consumed_qty": int(r.consumed_qty),
            "status": r.status,
            "expires_at": r.expires_at if r.expires_at else None,
            "created_by": r.created_by if r.created_by else None,
            "created_at": r.created_at if r.created_at else None,
        }
        for r in resp.reservations
    ]


@router.post(
    "/inventory/reservations/{reservation_id}/release",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_INVENTORY))],
)
def release_reservation(reservation_id: int, released_qty: int | None = None, request: Request = None):
    with inventory_stub() as stub:
        req = inventory_pb2.ReleaseReservationRequest(reservation_id=reservation_id)
        if released_qty is not None:
            req.released_qty = released_qty
        resp = _grpc_call(
            stub.ReleaseReservation,
            req,
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return {"success": bool(resp.success)}


# Phase 9: Inventory transaction ledger
@router.get(
    "/inventory/transactions",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_INVENTORY))],
)
def list_transactions(
    document_id: int | None = None,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    transaction_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    request: Request = None,
):
    with inventory_stub() as stub:
        req = inventory_pb2.ListTransactionsRequest(limit=limit, offset=offset)
        if document_id is not None:
            req.document_id = document_id
        if product_id is not None:
            req.product_id = product_id
        if warehouse_id is not None:
            req.warehouse_id = warehouse_id
        if transaction_type is not None:
            req.transaction_type = transaction_type
        resp = _grpc_call(
            stub.ListTransactions,
            req,
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return {
        "transactions": [
            {
                "id": tx.id,
                "transaction_type": tx.transaction_type,
                "document_id": tx.document_id,
                "document_line_id": tx.document_line_id,
                "product_id": tx.product_id,
                "warehouse_id": tx.warehouse_id,
                "quantity": tx.quantity,
                "physical_qty_before": tx.physical_qty_before,
                "physical_qty_after": tx.physical_qty_after,
                "reserved_qty_before": tx.reserved_qty_before,
                "reserved_qty_after": tx.reserved_qty_after,
                "available_qty_before": tx.available_qty_before,
                "available_qty_after": tx.available_qty_after,
                "user_id": tx.user_id,
                "created_at": tx.created_at,
                "payload": tx.payload,
                "idempotency_key": tx.idempotency_key,
            }
            for tx in resp.transactions
        ]
    }


@router.get(
    "/users",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_USERS))],
)
def list_users(request: Request):
    with identity_stub() as stub:
        resp = _grpc_call(
            stub.ListUsers,
            identity_pb2.ListUsersRequest(),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
            idempotent=True,
        )
    return [
        {
            "user_id": int(u.user_id),
            "email": u.email,
            "role": u.role,
            "full_name": u.full_name,
            "is_active": bool(u.is_active),
        }
        for u in resp.users
    ]


@router.post(
    "/users",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_USERS))],
)
def create_user(payload: dict, request: Request):
    with identity_stub() as stub:
        resp = _grpc_call(
            stub.CreateUser,
            identity_pb2.CreateUserRequest(
                email=payload.get("email"),
                password=payload.get("password"),
                role=payload.get("role"),
                full_name=payload.get("full_name"),
            ),
            request=request,
            timeout=GRPC_TIMEOUT_DEFAULT,
        )
    return {
        "success": resp.success,
        "message": resp.message,
        "user_id": int(resp.user_id) if resp.user_id else None,
    }


@router.delete(
    "/users/{user_id}",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_USERS))],
)
def delete_user(user_id: int, request: Request):
    with identity_stub() as stub:
        resp = _grpc_call(
            stub.DeleteUser,
            identity_pb2.DeleteUserRequest(user_id=user_id),
            request=request,
            timeout=GRPC_TIMEOUT_FAST,
        )
    return {"success": resp.success, "message": resp.message}
