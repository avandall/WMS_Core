from __future__ import annotations

import os

import grpc

from app.gen.wms.warehouse.v1 import warehouse_pb2, warehouse_pb2_grpc


def _addr() -> str:
    return os.getenv("WAREHOUSE_GRPC_ADDR", "warehouse-service:50054")


def list_warehouses() -> list[dict]:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseServiceStub(channel)
        resp = stub.ListWarehouses(warehouse_pb2.ListWarehousesRequest(), timeout=10)
        rows = []
        for w in resp.warehouses:
            rows.append(
                {
                    "warehouse_id": int(w.warehouse_id),
                    "name": w.name,
                    "location": w.location,
                    "inventory": [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in w.inventory],
                }
            )
        return rows


def get_warehouse(warehouse_id: int) -> dict | None:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseServiceStub(channel)
        try:
            w = stub.GetWarehouse(warehouse_pb2.GetWarehouseRequest(warehouse_id=warehouse_id), timeout=10)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
        return {
            "warehouse_id": int(w.warehouse_id),
            "name": w.name,
            "location": w.location,
            "inventory": [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in w.inventory],
        }


def create_warehouse(name: str) -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseServiceStub(channel)
        w = stub.CreateWarehouse(warehouse_pb2.CreateWarehouseRequest(name=name), timeout=10)
        return {"warehouse_id": int(w.warehouse_id), "name": w.name, "location": w.location, "inventory": []}


def delete_warehouse(warehouse_id: int) -> dict | None:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseServiceStub(channel)
        try:
            resp = stub.DeleteWarehouse(warehouse_pb2.DeleteWarehouseRequest(warehouse_id=warehouse_id), timeout=10)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
        return {"message": resp.message}


def transfer_all_inventory(warehouse_id: int, to_warehouse_id: int) -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseServiceStub(channel)
        resp = stub.TransferAllInventory(
            warehouse_pb2.TransferAllInventoryRequest(warehouse_id=warehouse_id, to_warehouse_id=to_warehouse_id),
            timeout=30,
        )
        return {
            "from_warehouse_id": int(resp.from_warehouse_id),
            "to_warehouse_id": int(resp.to_warehouse_id),
            "transferred_items": [{"product_id": int(i.product_id), "quantity": int(i.quantity)} for i in resp.transferred_items],
            "message": resp.message,
        }


def system_overview() -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseOperationsServiceStub(channel)
        resp = stub.GetSystemOverview(warehouse_pb2.GetSystemOverviewRequest(), timeout=10)
        return {
            "total_warehouses": int(resp.total_warehouses),
            "total_products": int(resp.total_products),
            "total_inventory_value": float(resp.total_inventory_value),
            "warehouses": list(resp.warehouses),
        }


def inventory_health() -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseOperationsServiceStub(channel)
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
                        {
                            "product_id": int(p.product_id),
                            "name": p.name,
                            "quantity": int(p.quantity),
                            "value": float(p.value),
                        }
                        for p in w.products
                    ],
                }
                for w in resp.warehouses
            ],
        }


def optimize_distribution(product_id: int) -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseOperationsServiceStub(channel)
        resp = stub.OptimizeDistribution(warehouse_pb2.OptimizeDistributionRequest(product_id=product_id), timeout=30)
        if resp.error:
            return {"error": resp.error}
        return {
            "product_id": int(resp.product_id),
            "product_name": resp.product_name,
            "distribution": [
                {"warehouse_id": int(d.warehouse_id), "location": d.location, "quantity": int(d.quantity)}
                for d in resp.distribution
            ],
            "recommendations": list(resp.recommendations),
        }


def bulk_transfer(transfers: list[dict]) -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = warehouse_pb2_grpc.WarehouseOperationsServiceStub(channel)
        items = []
        for t in transfers:
            items.append(
                warehouse_pb2.BulkTransferItem(
                    from_warehouse_id=int(t["from_warehouse_id"]),
                    to_warehouse_id=int(t["to_warehouse_id"]),
                    product_id=int(t["product_id"]),
                    quantity=int(t["quantity"]),
                )
            )
        resp = stub.BulkTransfer(warehouse_pb2.BulkTransferRequest(transfers=items), timeout=60)
        return {
            "total_transfers": int(resp.total_transfers),
            "successful": int(resp.successful),
            "failed": int(resp.failed),
        }

