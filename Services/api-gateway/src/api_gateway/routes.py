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
)
from api_gateway.gen.wms.customer.v1 import customer_pb2
from api_gateway.gen.wms.inventory.v1 import inventory_pb2
from api_gateway.gen.wms.product.v1 import product_pb2
from api_gateway.gen.wms.warehouse.v1 import warehouse_pb2
from api_gateway.gen.wms.documents.v1 import documents_pb2
from api_gateway.gen.wms.audit.v1 import audit_pb2
from api_gateway.gen.wms.reporting.v1 import reporting_pb2
from api_gateway.gen.wms.ai.v1 import ai_pb2


router = APIRouter(prefix="/api/v1")


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
    return [customer_to_dict(c) for c in resp.customers]


@router.post(
    "/customers",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.MANAGE_CUSTOMERS))],
)
def create_customer(payload: CustomerPayload, request: Request):
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
    return customer_to_dict(resp)


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
            ),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return document_to_dict(doc)


@router.post(
    "/documents/{document_id}/post",
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.DOC_POST))],
)
def post_document(document_id: int, payload: PostDocumentPayload, request: Request):
    with documents_stub() as stub:
        resp = _grpc_call(
            stub.PostDocument,
            documents_pb2.PostDocumentRequest(document_id=document_id, approved_by=payload.approved_by),
            request=request,
            timeout=GRPC_TIMEOUT_SLOW,
        )
    return {"message": resp.message}


@router.get("/documents/{document_id}", dependencies=[Depends(get_current_user)])
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


@router.get("/documents", dependencies=[Depends(get_current_user)])
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
        {"document_id": int(d.document_id), "doc_type": d.doc_type, "status": d.status}
        for d in resp.documents
    ]


@router.delete("/documents/{document_id}", dependencies=[Depends(get_current_user)])
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
    return parse_json(resp.json)


# ---- AI ----
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
    return [
        {
            "product_id": int(r.product_id),
            "warehouse_id": int(r.warehouse_id),
            "warehouse_name": r.warehouse_name,
            "quantity": int(r.quantity),
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
