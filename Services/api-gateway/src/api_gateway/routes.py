from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api_gateway.auth import get_current_user
from api_gateway.grpc_clients import (
    customer_stub,
    inventory_stub,
    product_stub,
    warehouse_ops_stub,
    warehouse_stub,
)
from api_gateway.gen.wms.customer.v1 import customer_pb2
from api_gateway.gen.wms.inventory.v1 import inventory_pb2
from api_gateway.gen.wms.product.v1 import product_pb2
from api_gateway.gen.wms.warehouse.v1 import warehouse_pb2


router = APIRouter(prefix="/api/v1")


# ---- Customers ----
@router.get("/customers", dependencies=[Depends(get_current_user)])
def list_customers():
    with customer_stub() as stub:
        resp = stub.ListCustomers(customer_pb2.ListCustomersRequest(), timeout=10)
    return [
        {
            "customer_id": int(c.customer_id),
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "address": c.address,
            "debt_balance": float(c.debt_balance),
            "created_at": c.created_at,
        }
        for c in resp.customers
    ]


@router.post("/customers", dependencies=[Depends(get_current_user)])
def create_customer(payload: dict):
    with customer_stub() as stub:
        resp = stub.CreateCustomer(
            customer_pb2.CreateCustomerRequest(
                name=str(payload.get("name") or ""),
                email=str(payload.get("email") or ""),
                phone=str(payload.get("phone") or ""),
                address=str(payload.get("address") or ""),
            ),
            timeout=10,
        )
    return {
        "customer_id": int(resp.customer_id),
        "name": resp.name,
        "email": resp.email,
        "phone": resp.phone,
        "address": resp.address,
        "debt_balance": float(resp.debt_balance),
        "created_at": resp.created_at,
    }


@router.get("/customers/{customer_id}", dependencies=[Depends(get_current_user)])
def get_customer(customer_id: int):
    try:
        with customer_stub() as stub:
            c = stub.GetCustomer(customer_pb2.GetCustomerRequest(customer_id=customer_id), timeout=10)
    except Exception:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {
        "customer_id": int(c.customer_id),
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "debt_balance": float(c.debt_balance),
        "created_at": c.created_at,
    }


@router.patch("/customers/{customer_id}", dependencies=[Depends(get_current_user)])
def update_customer(customer_id: int, payload: dict):
    try:
        with customer_stub() as stub:
            c = stub.UpdateCustomer(
                customer_pb2.UpdateCustomerRequest(
                    customer_id=customer_id,
                    name=str(payload.get("name") or ""),
                    email=str(payload.get("email") or ""),
                    phone=str(payload.get("phone") or ""),
                    address=str(payload.get("address") or ""),
                ),
                timeout=10,
            )
    except Exception:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {
        "customer_id": int(c.customer_id),
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "debt_balance": float(c.debt_balance),
        "created_at": c.created_at,
    }


@router.patch("/customers/{customer_id}/debt", dependencies=[Depends(get_current_user)])
def update_debt(customer_id: int, payload: dict):
    with customer_stub() as stub:
        resp = stub.UpdateDebt(
            customer_pb2.UpdateDebtRequest(customer_id=customer_id, amount=float(payload.get("amount") or 0)),
            timeout=10,
        )
    return {"message": resp.message, "delta": float(resp.delta)}


@router.get("/customers/{customer_id}/purchases", dependencies=[Depends(get_current_user)])
def list_purchases(customer_id: int):
    with customer_stub() as stub:
        resp = stub.ListPurchases(customer_pb2.ListPurchasesRequest(customer_id=customer_id), timeout=10)
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
@router.get("/products", dependencies=[Depends(get_current_user)])
def list_products():
    with product_stub() as stub:
        resp = stub.ListProducts(product_pb2.ListProductsRequest(), timeout=10)
    return [
        {"product_id": int(p.product_id), "name": p.name, "price": float(p.price), "description": p.description}
        for p in resp.products
    ]


@router.post("/products", dependencies=[Depends(get_current_user)])
def create_product(payload: dict):
    with product_stub() as stub:
        resp = stub.CreateProduct(
            product_pb2.CreateProductRequest(
                product_id=int(payload.get("product_id") or 0),
                name=str(payload.get("name") or ""),
                price=float(payload.get("price") or 0),
                description=str(payload.get("description") or ""),
            ),
            timeout=10,
        )
    return {"product_id": int(resp.product_id), "name": resp.name, "price": float(resp.price), "description": resp.description}


@router.get("/products/{product_id}", dependencies=[Depends(get_current_user)])
def get_product(product_id: int):
    try:
        with product_stub() as stub:
            p = stub.GetProduct(product_pb2.GetProductRequest(product_id=product_id), timeout=10)
    except Exception:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product_id": int(p.product_id), "name": p.name, "price": float(p.price), "description": p.description}


@router.put("/products/{product_id}", dependencies=[Depends(get_current_user)])
def update_product(product_id: int, payload: dict):
    try:
        with product_stub() as stub:
            p = stub.UpdateProduct(
                product_pb2.UpdateProductRequest(
                    product_id=product_id,
                    name=str(payload.get("name") or ""),
                    price=float(payload.get("price") or 0),
                    description=str(payload.get("description") or ""),
                ),
                timeout=10,
            )
    except Exception:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product_id": int(p.product_id), "name": p.name, "price": float(p.price), "description": p.description}


@router.delete("/products/{product_id}", dependencies=[Depends(get_current_user)])
def delete_product(product_id: int):
    try:
        with product_stub() as stub:
            resp = stub.DeleteProduct(product_pb2.DeleteProductRequest(product_id=product_id), timeout=10)
    except Exception:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": resp.message}


# ---- Warehouses ----
@router.get("/warehouses", dependencies=[Depends(get_current_user)])
def list_warehouses():
    with warehouse_stub() as stub:
        resp = stub.ListWarehouses(warehouse_pb2.ListWarehousesRequest(), timeout=10)
    return [
        {
            "warehouse_id": int(w.warehouse_id),
            "name": w.location,
            "location": w.location,
            "inventory": [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in w.inventory],
        }
        for w in resp.warehouses
    ]


@router.post("/warehouses", dependencies=[Depends(get_current_user)])
def create_warehouse(payload: dict):
    with warehouse_stub() as stub:
        w = stub.CreateWarehouse(
            warehouse_pb2.CreateWarehouseRequest(name=str(payload.get("name") or "")), timeout=10
        )
    return {"warehouse_id": int(w.warehouse_id), "name": w.location, "location": w.location, "inventory": []}


@router.get("/warehouses/{warehouse_id}", dependencies=[Depends(get_current_user)])
def get_warehouse(warehouse_id: int):
    try:
        with warehouse_stub() as stub:
            w = stub.GetWarehouse(warehouse_pb2.GetWarehouseRequest(warehouse_id=warehouse_id), timeout=10)
    except Exception:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return {
        "warehouse_id": int(w.warehouse_id),
        "name": w.location,
        "location": w.location,
        "inventory": [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in w.inventory],
    }


@router.delete("/warehouses/{warehouse_id}", dependencies=[Depends(get_current_user)])
def delete_warehouse(warehouse_id: int):
    try:
        with warehouse_stub() as stub:
            resp = stub.DeleteWarehouse(
                warehouse_pb2.DeleteWarehouseRequest(warehouse_id=warehouse_id), timeout=10
            )
    except Exception:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return {"message": resp.message}


@router.post("/warehouses/{warehouse_id}/transfer", dependencies=[Depends(get_current_user)])
def transfer_all_inventory(warehouse_id: int, payload: dict):
    with warehouse_stub() as stub:
        resp = stub.TransferAllInventory(
            warehouse_pb2.TransferAllInventoryRequest(
                warehouse_id=warehouse_id, to_warehouse_id=int(payload.get("to_warehouse_id") or 0)
            ),
            timeout=30,
        )
    return {
        "from_warehouse_id": int(resp.from_warehouse_id),
        "to_warehouse_id": int(resp.to_warehouse_id),
        "transferred_items": [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in resp.transferred_items],
        "message": resp.message,
    }


@router.get("/warehouse-operations/system-overview", dependencies=[Depends(get_current_user)])
def system_overview():
    with warehouse_ops_stub() as stub:
        resp = stub.GetSystemOverview(warehouse_pb2.GetSystemOverviewRequest(), timeout=10)
    return {
        "total_warehouses": int(resp.total_warehouses),
        "total_products": int(resp.total_products),
        "total_inventory_value": float(resp.total_inventory_value),
        "warehouses": list(resp.warehouses),
    }


@router.get("/warehouse-operations/inventory-health", dependencies=[Depends(get_current_user)])
def inventory_health():
    with warehouse_ops_stub() as stub:
        resp = stub.GetInventoryHealth(warehouse_pb2.GetInventoryHealthRequest(), timeout=30)
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


@router.get("/warehouse-operations/optimize-distribution/{product_id}", dependencies=[Depends(get_current_user)])
def optimize_distribution(product_id: int):
    with warehouse_ops_stub() as stub:
        resp = stub.OptimizeDistribution(
            warehouse_pb2.OptimizeDistributionRequest(product_id=product_id), timeout=30
        )
    if resp.error:
        raise HTTPException(status_code=404, detail=resp.error)
    return {
        "product_id": int(resp.product_id),
        "product_name": resp.product_name,
        "distribution": [{"warehouse_id": int(d.warehouse_id), "location": d.location, "quantity": int(d.quantity)} for d in resp.distribution],
        "recommendations": list(resp.recommendations),
    }


# ---- Inventory ----
@router.get("/inventory", dependencies=[Depends(get_current_user)])
def list_inventory():
    with inventory_stub() as stub:
        resp = stub.ListInventoryItems(inventory_pb2.ListInventoryItemsRequest(), timeout=10)
    return [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in resp.items]


@router.get("/inventory/by-warehouse", dependencies=[Depends(get_current_user)])
def inventory_by_warehouse():
    with inventory_stub() as stub:
        resp = stub.GetInventoryByWarehouse(inventory_pb2.GetInventoryByWarehouseRequest(), timeout=30)
    return [
        {
            "product_id": int(r.product_id),
            "warehouse_id": int(r.warehouse_id),
            "warehouse_name": r.warehouse_name,
            "quantity": int(r.quantity),
        }
        for r in resp.rows
    ]


@router.get("/inventory/{product_id}", dependencies=[Depends(get_current_user)])
def product_quantity(product_id: int):
    with inventory_stub() as stub:
        resp = stub.GetProductQuantity(
            inventory_pb2.GetProductQuantityRequest(product_id=product_id), timeout=10
        )
    return {"product_id": int(resp.product_id), "quantity": int(resp.quantity)}
