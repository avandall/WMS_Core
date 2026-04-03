from __future__ import annotations

from typing import Any, Dict, List

from app.domain.interfaces import IDocumentRepo, IInventoryRepo, IProductRepo, IWarehouseRepo


class WarehouseOperationsService:
    """Cross-domain warehouse operations and analytics."""

    def __init__(
        self,
        warehouse_repo: IWarehouseRepo,
        product_repo: IProductRepo,
        inventory_repo: IInventoryRepo,
        document_repo: IDocumentRepo,
    ):
        self.warehouse_repo = warehouse_repo
        self.product_repo = product_repo
        self.inventory_repo = inventory_repo
        self.document_repo = document_repo

    def get_system_overview(self) -> Dict[str, Any]:
        warehouses = self.warehouse_repo.get_all()
        total_products = len(self.product_repo.get_all())
        total_inventory_value = self._calculate_total_inventory_value()
        return {
            "total_warehouses": len(warehouses),
            "total_products": total_products,
            "total_inventory_value": total_inventory_value,
            "warehouses": [w.location for w in warehouses.values()],
        }

    def optimize_inventory_distribution(self, product_id: int) -> Dict[str, Any]:
        product = self.product_repo.get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        distribution = []
        for warehouse in self.warehouse_repo.get_all().values():
            quantity = self._get_warehouse_product_quantity(
                warehouse.warehouse_id, product_id
            )
            distribution.append(
                {
                    "warehouse_id": warehouse.warehouse_id,
                    "location": warehouse.location,
                    "quantity": quantity,
                }
            )

        return {
            "product_id": product_id,
            "product_name": product.name,
            "distribution": distribution,
            "recommendations": self._generate_distribution_recommendations(distribution),
        }

    def bulk_transfer_products(self, transfers: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        successful = 0
        failed = 0

        for transfer in transfers:
            try:
                from_wh = transfer["from_warehouse_id"]
                to_wh = transfer["to_warehouse_id"]
                product_id = transfer["product_id"]
                quantity = transfer["quantity"]

                inventory = self.warehouse_repo.get_warehouse_inventory(from_wh)
                available = 0
                for item in inventory:
                    if item.product_id == product_id:
                        available = item.quantity
                        break

                if available >= quantity:
                    self.warehouse_repo.remove_product_from_warehouse(
                        from_wh, product_id, quantity
                    )
                    self.warehouse_repo.add_product_to_warehouse(
                        to_wh, product_id, quantity
                    )
                    results.append(
                        {
                            "transfer": transfer,
                            "status": "success",
                            "message": f"Transferred {quantity} units",
                        }
                    )
                    successful += 1
                else:
                    results.append(
                        {
                            "transfer": transfer,
                            "status": "failed",
                            "message": f"Insufficient stock: {available} available, {quantity} requested",
                        }
                    )
                    failed += 1
            except Exception as exc:
                results.append(
                    {"transfer": transfer, "status": "error", "message": str(exc)}
                )
                failed += 1

        return {
            "total_transfers": len(transfers),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

    def get_inventory_health_report(self) -> Dict[str, Any]:
        warehouses = self.warehouse_repo.get_all()
        products = self.product_repo.get_all()

        products_dict = products if isinstance(products, dict) else {p.product_id: p for p in products}

        warehouse_inventories = {}
        for warehouse in warehouses.values():
            inventory = self.warehouse_repo.get_warehouse_inventory(warehouse.warehouse_id)
            warehouse_inventories[warehouse.warehouse_id] = {
                item.product_id: item.quantity for item in inventory
            }

        report = {"warehouses": [], "system_health_score": 0, "recommendations": []}
        total_health_score = 0

        for warehouse in warehouses.values():
            warehouse_data = {
                "warehouse_id": warehouse.warehouse_id,
                "location": warehouse.location,
                "products": [],
                "total_value": 0,
                "health_score": 0,
            }

            inventory = warehouse_inventories[warehouse.warehouse_id]
            for product_id, product in products_dict.items():
                quantity = inventory.get(product_id, 0)
                if quantity > 0:
                    value = quantity * product.price
                    warehouse_data["products"].append(
                        {
                            "product_id": product.product_id,
                            "name": product.name,
                            "quantity": quantity,
                            "value": value,
                        }
                    )
                    warehouse_data["total_value"] += value

            warehouse_data["health_score"] = min(100, len(warehouse_data["products"]) * 10)
            total_health_score += warehouse_data["health_score"]
            report["warehouses"].append(warehouse_data)

        report["system_health_score"] = (
            total_health_score / len(report["warehouses"]) if report["warehouses"] else 0
        )
        return report

    def _calculate_total_inventory_value(self) -> float:
        all_inventory = self.inventory_repo.get_all()
        products = self.product_repo.get_all()
        products_dict = products if isinstance(products, dict) else {p.product_id: p for p in products}
        return sum(
            item.quantity * products_dict[item.product_id].price
            for item in all_inventory
            if item.product_id in products_dict
        )

    def _generate_distribution_recommendations(self, distribution: List[Dict]) -> List[str]:
        total_quantity = sum(d["quantity"] for d in distribution)
        if total_quantity == 0:
            return ["No inventory to distribute"]
        avg_quantity = total_quantity / len(distribution)
        low_stock = [d for d in distribution if d["quantity"] < avg_quantity * 0.5]
        if not low_stock:
            return []
        return [
            f"Consider redistributing stock to warehouses: {[w['location'] for w in low_stock]}"
        ]

    def _get_warehouse_product_quantity(self, warehouse_id: int, product_id: int) -> int:
        inventory = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
        for item in inventory:
            if item.product_id == product_id:
                return item.quantity
        return 0

