from __future__ import annotations

from datetime import datetime, timezone

import grpc
from sqlalchemy import select

from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.positions.infrastructure.models.position import PositionModel
from app.modules.products.infrastructure.models.product import ProductModel
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.shared.core.database import get_db_session
from app.shared.core.logging import get_logger
from shared_utils.events import get_publisher

from warehouse_service.gen.wms.warehouse.v1 import warehouse_pb2, warehouse_pb2_grpc

logger = get_logger(__name__)


class WarehouseServiceServicer(warehouse_pb2_grpc.WarehouseServiceServicer):
    _publisher = get_publisher("warehouse-service")

    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "x-request-id":
                return v
        return None

    def _service(self, db: object) -> WarehouseService:
        return WarehouseService(WarehouseRepo(db), session=db)

    def ListWarehouses(self, request: warehouse_pb2.ListWarehousesRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            warehouses = service.get_all_warehouses()
            rows = [
                warehouse_pb2.Warehouse(
                    warehouse_id=int(w.warehouse_id),
                    name=w.location or "",
                    location=w.location or "",
                )
                for w in warehouses
            ]
            return warehouse_pb2.ListWarehousesResponse(warehouses=rows)

    def GetWarehouse(self, request: warehouse_pb2.GetWarehouseRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                w = service.get_warehouse(int(request.warehouse_id))
                return warehouse_pb2.Warehouse(
                    warehouse_id=int(w.warehouse_id),
                    name=w.location or "",
                    location=w.location or "",
                )
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Warehouse not found")
            return warehouse_pb2.Warehouse()

    def CreateWarehouse(self, request: warehouse_pb2.CreateWarehouseRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            w = service.create_warehouse(request.name)
            self._publisher.publish(
                event_type="WarehouseCreated",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "warehouse",
                    "entity_id": int(w.warehouse_id),
                    "warehouse_id": int(w.warehouse_id),
                    "location": w.location,
                },
            )
            return warehouse_pb2.Warehouse(
                warehouse_id=int(w.warehouse_id),
                name=w.location or "",
                location=w.location or "",
            )

    def DeleteWarehouse(self, request: warehouse_pb2.DeleteWarehouseRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                warehouse_id = int(request.warehouse_id)
                service.delete_warehouse(warehouse_id)
                self._publisher.publish(
                    event_type="WarehouseDeleted",
                    payload={
                        "request_id": self._request_id(context),
                        "entity_type": "warehouse",
                        "entity_id": warehouse_id,
                        "warehouse_id": warehouse_id,
                    },
                )
                return warehouse_pb2.DeleteWarehouseResponse(
                    message=f"Warehouse {warehouse_id} deleted successfully"
                )
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Warehouse not found")
            return warehouse_pb2.DeleteWarehouseResponse(message="Warehouse not found")

    def TransferAllInventory(
        self, request: warehouse_pb2.TransferAllInventoryRequest, context: grpc.ServicerContext
    ):
        with get_db_session() as db:
            service = self._service(db)
            service.transfer_all_inventory(int(request.warehouse_id), int(request.to_warehouse_id))
            return warehouse_pb2.TransferAllInventoryResponse(
                from_warehouse_id=int(request.warehouse_id),
                to_warehouse_id=int(request.to_warehouse_id),
                transferred_items=[],
                message="Warehouse inventory ownership moved to inventory-service",
            )


class WarehouseOperationsServiceServicer(warehouse_pb2_grpc.WarehouseOperationsServiceServicer):
    def _repo(self, db: object) -> WarehouseRepo:
        return WarehouseRepo(db)

    def GetSystemOverview(self, request: warehouse_pb2.GetSystemOverviewRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            repo = self._repo(db)
            warehouses = repo.get_all()
            return warehouse_pb2.SystemOverview(
                total_warehouses=len(warehouses),
                total_products=0,
                total_inventory_value=0,
                warehouses=[str(w) for w in warehouses.values()],
            )

    def GetInventoryHealth(self, request: warehouse_pb2.GetInventoryHealthRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            warehouses = db.execute(select(WarehouseModel)).unique().scalars().all()
            if not warehouses:
                return warehouse_pb2.InventoryHealthReport(system_health_score=100.0, warehouses=[])

            products = db.execute(select(ProductModel)).unique().scalars().all()
            prod_map = {p.product_id: p for p in products}

            wh_health_reports = []
            total_health_score_sum = 0.0
            now_utc = datetime.now(timezone.utc)

            for wh in warehouses:
                wh_id = wh.warehouse_id

                # 1. Position availability ratio score
                positions = db.execute(
                    select(PositionModel).where(PositionModel.warehouse_id == wh_id)
                ).scalars().all()
                if positions:
                    active_positions = sum(1 for p in positions if getattr(p, "is_active", 1))
                    position_score = (active_positions / len(positions)) * 100.0
                else:
                    position_score = 100.0

                # 2. Near-expiry / fresh inventory score
                loc_records = db.execute(
                    select(InventoryLocationModel).where(InventoryLocationModel.warehouse_id == wh_id)
                ).scalars().all()
                if loc_records:
                    expired_count = 0
                    for loc in loc_records:
                        exp_val = getattr(loc, "expiry_date", None)
                        if exp_val:
                            if isinstance(exp_val, str):
                                try:
                                    exp_dt = datetime.fromisoformat(exp_val)
                                    if exp_dt.tzinfo is None:
                                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                                except ValueError:
                                    exp_dt = None
                            else:
                                exp_dt = (
                                    exp_val if exp_val.tzinfo is not None else exp_val.replace(tzinfo=timezone.utc)
                                )

                            if exp_dt and exp_dt < now_utc:
                                expired_count += 1
                    fresh_score = ((len(loc_records) - expired_count) / len(loc_records)) * 100.0
                else:
                    fresh_score = 100.0

                # 3. Stock availability / in-stock SKU ratio score
                wh_inv_rows = db.execute(
                    select(WarehouseInventoryModel).where(WarehouseInventoryModel.warehouse_id == wh_id)
                ).scalars().all()
                if wh_inv_rows:
                    in_stock_skus = sum(
                        1
                        for row in wh_inv_rows
                        if (getattr(row, "physical_qty", 0) or getattr(row, "quantity", 0)) > 0
                    )
                    stock_availability_score = (in_stock_skus / len(wh_inv_rows)) * 100.0
                else:
                    stock_availability_score = 100.0

                wh_health_score = round(
                    position_score * 0.3 + fresh_score * 0.4 + stock_availability_score * 0.3, 2
                )
                total_health_score_sum += wh_health_score

                wh_products = []
                wh_total_val = 0.0
                for inv_row in wh_inv_rows:
                    pid = inv_row.product_id
                    qty = getattr(inv_row, "physical_qty", 0) or getattr(inv_row, "quantity", 0)
                    prod = prod_map.get(pid)
                    prod_name = prod.name if prod else f"Product #{pid}"
                    prod_price = float(getattr(prod, "price", 0.0) or 0.0)
                    item_val = round(qty * prod_price, 2)
                    wh_total_val += item_val
                    wh_products.append(
                        warehouse_pb2.InventoryHealthProduct(
                            product_id=pid,
                            name=prod_name,
                            quantity=qty,
                            value=item_val,
                        )
                    )

                wh_health_reports.append(
                    warehouse_pb2.InventoryHealthWarehouse(
                        warehouse_id=wh_id,
                        location=wh.location or "",
                        total_value=round(wh_total_val, 2),
                        health_score=wh_health_score,
                        products=wh_products,
                    )
                )

            system_health_score = round(total_health_score_sum / len(warehouses), 2)
            return warehouse_pb2.InventoryHealthReport(
                system_health_score=system_health_score,
                warehouses=wh_health_reports,
            )

    def OptimizeDistribution(
        self, request: warehouse_pb2.OptimizeDistributionRequest, context: grpc.ServicerContext
    ):
        with get_db_session() as db:
            pid = int(request.product_id)
            prod = db.execute(select(ProductModel).where(ProductModel.product_id == pid)).unique().scalar_one_or_none()
            if not prod:
                return warehouse_pb2.OptimizeDistributionResponse(
                    product_id=pid,
                    product_name="",
                    distribution=[],
                    recommendations=[],
                    error=f"Product {pid} not found",
                )

            warehouses = db.execute(select(WarehouseModel)).unique().scalars().all()
            if not warehouses:
                return warehouse_pb2.OptimizeDistributionResponse(
                    product_id=pid,
                    product_name=prod.name or "",
                    distribution=[],
                    recommendations=["No active warehouses in system"],
                    error="",
                )

            wh_inv_rows = db.execute(
                select(WarehouseInventoryModel).where(WarehouseInventoryModel.product_id == pid)
            ).scalars().all()
            stock_by_wh = {
                row.warehouse_id: getattr(row, "physical_qty", 0) or getattr(row, "quantity", 0)
                for row in wh_inv_rows
            }

            dist_items = []
            total_qty = 0
            for wh in warehouses:
                qty = stock_by_wh.get(wh.warehouse_id, 0)
                total_qty += qty
                dist_items.append(
                    warehouse_pb2.DistributionItem(
                        warehouse_id=wh.warehouse_id,
                        location=wh.location or "",
                        quantity=qty,
                    )
                )

            recommendations = []
            if total_qty == 0:
                recommendations.append(
                    f"Product '{prod.name}' is out of stock across all warehouses. Restock required."
                )
            else:
                target_avg = total_qty // len(warehouses)
                overstocked = [wh for wh in warehouses if stock_by_wh.get(wh.warehouse_id, 0) > target_avg + 1]
                understocked = [wh for wh in warehouses if stock_by_wh.get(wh.warehouse_id, 0) < target_avg]

                if overstocked and understocked:
                    for o_wh in overstocked:
                        for u_wh in understocked:
                            excess = stock_by_wh.get(o_wh.warehouse_id, 0) - target_avg
                            deficit = target_avg - stock_by_wh.get(u_wh.warehouse_id, 0)
                            transfer_qty = min(excess, deficit)
                            if transfer_qty > 0:
                                recommendations.append(
                                    f"Transfer {transfer_qty} units of '{prod.name}' from Warehouse {o_wh.warehouse_id} ({o_wh.location}) to Warehouse {u_wh.warehouse_id} ({u_wh.location}) to balance distribution."
                                )
                                stock_by_wh[o_wh.warehouse_id] -= transfer_qty
                                stock_by_wh[u_wh.warehouse_id] += transfer_qty

                if not recommendations:
                    recommendations.append(
                        f"Inventory distribution for product '{prod.name}' is balanced across all warehouses."
                    )

            return warehouse_pb2.OptimizeDistributionResponse(
                product_id=pid,
                product_name=prod.name or "",
                distribution=dist_items,
                recommendations=recommendations,
                error="",
            )

    def BulkTransfer(self, request: warehouse_pb2.BulkTransferRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            transfers = request.transfers
            total_transfers = len(transfers)
            successful = 0
            failed = 0

            for item in transfers:
                from_wh_id = int(item.from_warehouse_id)
                to_wh_id = int(item.to_warehouse_id)
                pid = int(item.product_id)
                qty = int(item.quantity)

                if qty <= 0:
                    failed += 1
                    logger.warning(
                        f"BulkTransfer item failed: Invalid transfer quantity {qty} for product {pid}"
                    )
                    continue

                if from_wh_id == to_wh_id:
                    failed += 1
                    logger.warning(
                        f"BulkTransfer item failed: Source and destination warehouse are identical ({from_wh_id})"
                    )
                    continue

                from_wh = db.execute(
                    select(WarehouseModel).where(WarehouseModel.warehouse_id == from_wh_id)
                ).scalar_one_or_none()
                to_wh = db.execute(
                    select(WarehouseModel).where(WarehouseModel.warehouse_id == to_wh_id)
                ).scalar_one_or_none()

                if not from_wh:
                    failed += 1
                    logger.warning(f"BulkTransfer item failed: Source warehouse {from_wh_id} not found")
                    continue

                if not to_wh:
                    failed += 1
                    logger.warning(f"BulkTransfer item failed: Destination warehouse {to_wh_id} not found")
                    continue

                from_inv = db.execute(
                    select(WarehouseInventoryModel)
                    .where(
                        WarehouseInventoryModel.warehouse_id == from_wh_id,
                        WarehouseInventoryModel.product_id == pid,
                    )
                    .with_for_update()
                ).scalar_one_or_none()

                avail_qty = (
                    (getattr(from_inv, "physical_qty", 0) or getattr(from_inv, "quantity", 0))
                    if from_inv
                    else 0
                )
                if avail_qty < qty:
                    failed += 1
                    logger.warning(
                        f"BulkTransfer item failed: Insufficient stock for product {pid} in warehouse {from_wh_id} (Available: {avail_qty}, Requested: {qty})"
                    )
                    continue

                # Deduct from source warehouse
                if hasattr(from_inv, "physical_qty") and from_inv is not None:
                    from_inv.physical_qty -= qty
                if hasattr(from_inv, "quantity") and from_inv is not None:
                    from_inv.quantity -= qty

                # Add to destination warehouse
                to_inv = db.execute(
                    select(WarehouseInventoryModel)
                    .where(
                        WarehouseInventoryModel.warehouse_id == to_wh_id,
                        WarehouseInventoryModel.product_id == pid,
                    )
                    .with_for_update()
                ).scalar_one_or_none()

                if not to_inv:
                    to_inv = WarehouseInventoryModel(
                        warehouse_id=to_wh_id,
                        product_id=pid,
                        physical_qty=qty,
                        quantity=qty,
                        owner_id="DEFAULT_OWNER",
                    )
                    db.add(to_inv)
                else:
                    if hasattr(to_inv, "physical_qty"):
                        to_inv.physical_qty += qty
                    if hasattr(to_inv, "quantity"):
                        to_inv.quantity += qty

                successful += 1

            db.commit()
            return warehouse_pb2.BulkTransferResponse(
                total_transfers=total_transfers,
                successful=successful,
                failed=failed,
            )


add_WarehouseServiceServicer_to_server = warehouse_pb2_grpc.add_WarehouseServiceServicer_to_server
add_WarehouseOperationsServiceServicer_to_server = (
    warehouse_pb2_grpc.add_WarehouseOperationsServiceServicer_to_server
)
