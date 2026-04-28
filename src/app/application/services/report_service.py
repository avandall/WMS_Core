from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.modules.documents.domain.entities.document import Document, DocumentStatus, DocumentType
from app.shared.domain.customer_repo import ICustomerRepo
from app.shared.domain.document_repo import IDocumentRepo
from app.shared.domain.inventory_repo import IInventoryRepo
from app.shared.domain.product_repo import IProductRepo
from app.shared.domain.warehouse_repo import IWarehouseRepo
from app.shared.core.exceptions import (
    InvalidReportParametersError,
    ReportGenerationError,
)


class ReportService:
    """Aggregates data from repositories to build reports."""

    def __init__(
        self,
        product_repo: IProductRepo,
        document_repo: IDocumentRepo,
        warehouse_repo: IWarehouseRepo,
        inventory_repo: IInventoryRepo,
        customer_repo: Optional[ICustomerRepo] = None,
    ):
        self.product_repo = product_repo
        self.document_repo = document_repo
        self.warehouse_repo = warehouse_repo
        self.inventory_repo = inventory_repo
        self.customer_repo = customer_repo

    def generate_inventory_report(
        self, warehouse_id: Optional[int] = None, low_stock_threshold: int = 10
    ) -> Dict[str, Any]:
        try:
            if warehouse_id:
                return self._generate_warehouse_inventory_report(
                    warehouse_id, low_stock_threshold
                )
            return self._generate_total_inventory_report(low_stock_threshold)
        except Exception as exc:
            raise ReportGenerationError(f"Failed to generate inventory report: {exc}") from exc

    def generate_product_movement_report(
        self,
        product_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        try:
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            documents = self.document_repo.get_all()
            filtered_docs = self._filter_documents_by_date(documents, start_date, end_date)

            if product_id:
                return self._generate_single_product_movement_report(
                    product_id, filtered_docs, start_date, end_date
                )
            return self._generate_all_products_movement_report(filtered_docs, start_date, end_date)
        except Exception as exc:
            raise ReportGenerationError(
                f"Failed to generate product movement report: {exc}"
            ) from exc

    def generate_warehouse_performance_report(
        self,
        warehouse_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        try:
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            documents = self.document_repo.get_all()
            filtered_docs = self._filter_documents_by_date(documents, start_date, end_date)

            if warehouse_id:
                return self._generate_single_warehouse_performance_report(
                    warehouse_id, filtered_docs, start_date, end_date
                )
            return self._generate_all_warehouses_performance_report(filtered_docs, start_date, end_date)
        except Exception as exc:
            raise ReportGenerationError(
                f"Failed to generate warehouse performance report: {exc}"
            ) from exc

    def generate_business_overview_report(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        try:
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            documents = self.document_repo.get_all()
            filtered_docs = self._filter_documents_by_date(documents, start_date, end_date)

            inventory_data = self._calculate_inventory_metrics()
            document_metrics = self._calculate_document_metrics(filtered_docs)
            warehouse_metrics = self._calculate_warehouse_metrics()
            insights = self._generate_business_insights(inventory_data, document_metrics, warehouse_metrics)

            return {
                "report_type": "business_overview",
                "period": {"start_date": start_date, "end_date": end_date},
                "generated_at": datetime.now(),
                "inventory_summary": inventory_data,
                "operations_summary": document_metrics,
                "warehouse_summary": warehouse_metrics,
                "key_insights": insights,
                "recommendations": self._generate_recommendations(insights),
            }
        except Exception as exc:
            raise ReportGenerationError(f"Failed to generate business overview report: {exc}") from exc

    def list_inventory_by_warehouse(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for warehouse_id, warehouse in self.warehouse_repo.get_all().items():
            for item in warehouse.inventory:
                rows.append(
                    {
                        "product_id": item.product_id,
                        "warehouse_id": warehouse_id,
                        "warehouse_name": warehouse.location,
                        "quantity": item.quantity,
                    }
                )
        rows.sort(key=lambda r: (r["warehouse_id"], r["product_id"]))
        return rows

    def list_documents_report(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        documents = self.document_repo.get_all()
        if start_date or end_date:
            if not start_date:
                start_date = date.min
            if not end_date:
                end_date = date.max
            documents = self._filter_documents_by_date(documents, start_date, end_date)

        results: List[Dict[str, Any]] = []
        for doc in documents:
            created_at = getattr(doc, "created_at", None)
            results.append(
                {
                    "document_id": doc.document_id,
                    "doc_type": doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type),
                    "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
                    "created_at": created_at,
                    "item_count": len(doc.items) if getattr(doc, "items", None) else 0,
                    "customer_id": getattr(doc, "customer_id", None),
                }
            )
        results.sort(key=lambda r: r["created_at"] or datetime.min, reverse=True)
        return results

    def generate_sales_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        salesperson: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.customer_repo:
            raise ReportGenerationError("Customer repository not configured for sales report")

        customers = {c.get("customer_id"): c for c in (self.customer_repo.get_all() or [])}
        documents = [
            d
            for d in self.document_repo.get_all()
            if getattr(d, "doc_type", None) == DocumentType.SALE
            or getattr(getattr(d, "doc_type", None), "value", None) == DocumentType.SALE.value
        ]

        if start_date or end_date:
            if start_date:
                documents = [
                    d
                    for d in documents
                    if getattr(d, "created_at", None)
                    and getattr(d, "created_at").date() >= start_date
                ]
            if end_date:
                documents = [
                    d
                    for d in documents
                    if getattr(d, "created_at", None)
                    and getattr(d, "created_at").date() <= end_date
                ]

        if customer_id:
            documents = [d for d in documents if getattr(d, "customer_id", None) == customer_id]

        if salesperson:
            salesperson_lc = salesperson.lower()
            documents = [
                d
                for d in documents
                if salesperson_lc in (getattr(d, "created_by", "") or "").lower()
            ]

        documents.sort(key=lambda d: getattr(d, "created_at", datetime.min), reverse=True)

        sales_data: List[Dict[str, Any]] = []
        total_sales = 0.0
        unique_customers: Dict[int, float] = {}

        for doc in documents:
            total_sale = float(sum(item.quantity * item.unit_price for item in (doc.items or [])))
            total_sales += total_sale

            customer_info = customers.get(getattr(doc, "customer_id", None)) or {}
            debt_balance = float(customer_info.get("debt_balance") or 0)
            cust_id = getattr(doc, "customer_id", None)
            if cust_id and cust_id not in unique_customers:
                unique_customers[cust_id] = debt_balance

            created_at = getattr(doc, "created_at", None)
            sales_data.append(
                {
                    "document_id": doc.document_id,
                    "salesperson": getattr(doc, "created_by", None),
                    "customer_id": cust_id,
                    "customer_name": customer_info.get("name") or "N/A",
                    "sale_date": created_at.isoformat() if created_at else None,
                    "total_sale": round(total_sale, 2),
                    "customer_debt": round(debt_balance, 2),
                }
            )

        total_debt = sum(unique_customers.values())
        return {
            "summary": {
                "total_sales": round(total_sales, 2),
                "total_debt": round(total_debt, 2),
                "transaction_count": len(sales_data),
                "unique_customers": len(unique_customers),
                "period": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None,
                },
            },
            "sales": sales_data,
        }

    def _generate_warehouse_inventory_report(
        self, warehouse_id: int, low_stock_threshold: int
    ) -> Dict[str, Any]:
        warehouse = self.warehouse_repo.get(warehouse_id)
        if not warehouse:
            raise InvalidReportParametersError(f"Warehouse {warehouse_id} not found")

        inventory_items = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
        products = self.product_repo.get_all()

        report_items = []
        total_value = 0.0
        low_stock_items = []

        for item in inventory_items:
            product = products.get(item.product_id)
            if not product:
                continue
            item_value = product.price * item.quantity
            total_value += item_value
            report_item = {
                "product_id": item.product_id,
                "product_name": product.name,
                "quantity": item.quantity,
                "unit_price": product.price,
                "total_value": item_value,
            }
            report_items.append(report_item)
            if item.quantity <= low_stock_threshold:
                low_stock_items.append(report_item)

        return {
            "report_type": "warehouse_inventory",
            "warehouse": {"id": warehouse.warehouse_id, "location": warehouse.location},
            "generated_at": datetime.now(),
            "total_items": len(report_items),
            "total_value": total_value,
            "inventory_items": report_items,
            "low_stock_items": low_stock_items,
            "low_stock_threshold": low_stock_threshold,
        }

    def _generate_total_inventory_report(self, low_stock_threshold: int) -> Dict[str, Any]:
        all_inventory = self.inventory_repo.get_all()
        products = self.product_repo.get_all()
        warehouses = self.warehouse_repo.get_all()

        report_items = []
        warehouse_breakdown: dict[int, Any] = {}
        total_value = 0.0

        for item in all_inventory:
            product = products.get(item.product_id)
            if not product:
                continue
            item_value = product.price * item.quantity
            total_value += item_value
            report_items.append(
                {
                    "product_id": item.product_id,
                    "product_name": product.name,
                    "total_quantity": item.quantity,
                    "unit_price": product.price,
                    "total_value": item_value,
                }
            )

        for warehouse_id, warehouse in warehouses.items():
            wh_inventory = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
            wh_value = 0.0
            wh_items = []
            for item in wh_inventory:
                product = products.get(item.product_id)
                if not product:
                    continue
                item_value = product.price * item.quantity
                wh_value += item_value
                wh_items.append(
                    {
                        "product_id": item.product_id,
                        "product_name": product.name,
                        "quantity": item.quantity,
                        "value": item_value,
                    }
                )
            warehouse_breakdown[warehouse_id] = {
                "warehouse_location": warehouse.location,
                "total_items": len(wh_items),
                "total_value": wh_value,
                "inventory_items": wh_items,
            }

        return {
            "report_type": "total_inventory",
            "generated_at": datetime.now(),
            "total_products": len(report_items),
            "total_value": total_value,
            "products": report_items,
            "warehouse_breakdown": warehouse_breakdown,
            "low_stock_threshold": low_stock_threshold,
        }

    def _generate_single_product_movement_report(
        self,
        product_id: int,
        documents: List[Document],
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        product = self.product_repo.get(product_id)
        if not product:
            raise InvalidReportParametersError(f"Product {product_id} not found")

        imported = exported = transferred_in = transferred_out = sold = 0
        for doc in documents:
            for item in doc.items:
                if item.product_id != product_id:
                    continue
                if doc.doc_type == DocumentType.IMPORT:
                    imported += item.quantity
                elif doc.doc_type == DocumentType.EXPORT:
                    exported += item.quantity
                elif doc.doc_type == DocumentType.TRANSFER:
                    transferred_out += item.quantity
                    transferred_in += item.quantity
                elif doc.doc_type == DocumentType.SALE:
                    sold += item.quantity

        return {
            "report_type": "product_movement",
            "product": {"id": product.product_id, "name": product.name},
            "period": {"start_date": start_date, "end_date": end_date},
            "generated_at": datetime.now(),
            "imported": imported,
            "exported": exported,
            "sold": sold,
            "transferred_in": transferred_in,
            "transferred_out": transferred_out,
            "net_movement": imported - exported - sold,
        }

    def _generate_all_products_movement_report(
        self, documents: List[Document], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        products = self.product_repo.get_all()
        movements: dict[int, dict[str, int]] = {}

        for doc in documents:
            for item in doc.items:
                stats = movements.setdefault(
                    item.product_id,
                    {"imported": 0, "exported": 0, "sold": 0, "transferred_in": 0, "transferred_out": 0},
                )
                if doc.doc_type == DocumentType.IMPORT:
                    stats["imported"] += item.quantity
                elif doc.doc_type == DocumentType.EXPORT:
                    stats["exported"] += item.quantity
                elif doc.doc_type == DocumentType.SALE:
                    stats["sold"] += item.quantity
                elif doc.doc_type == DocumentType.TRANSFER:
                    stats["transferred_in"] += item.quantity
                    stats["transferred_out"] += item.quantity

        items = []
        for product_id, stats in movements.items():
            product = products.get(product_id)
            if not product:
                continue
            items.append(
                {
                    "product_id": product_id,
                    "product_name": product.name,
                    **stats,
                    "net_movement": stats["imported"] - stats["exported"] - stats["sold"],
                }
            )

        return {
            "report_type": "product_movement",
            "period": {"start_date": start_date, "end_date": end_date},
            "generated_at": datetime.now(),
            "items": items,
        }

    def _generate_single_warehouse_performance_report(
        self, warehouse_id: int, documents: List[Document], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        warehouse = self.warehouse_repo.get(warehouse_id)
        if not warehouse:
            raise InvalidReportParametersError(f"Warehouse {warehouse_id} not found")
        relevant_docs = [
            d
            for d in documents
            if d.from_warehouse_id == warehouse_id or d.to_warehouse_id == warehouse_id
        ]
        return {
            "report_type": "warehouse_performance",
            "warehouse": {"id": warehouse_id, "location": warehouse.location},
            "period": {"start_date": start_date, "end_date": end_date},
            "generated_at": datetime.now(),
            "total_documents": len(relevant_docs),
        }

    def _generate_all_warehouses_performance_report(
        self, documents: List[Document], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        warehouses = self.warehouse_repo.get_all()
        items = []
        for warehouse_id, warehouse in warehouses.items():
            relevant_docs = [
                d
                for d in documents
                if d.from_warehouse_id == warehouse_id or d.to_warehouse_id == warehouse_id
            ]
            items.append(
                {
                    "warehouse_id": warehouse_id,
                    "location": warehouse.location,
                    "document_count": len(relevant_docs),
                }
            )
        return {
            "report_type": "warehouse_performance",
            "period": {"start_date": start_date, "end_date": end_date},
            "generated_at": datetime.now(),
            "items": items,
        }

    def _filter_documents_by_date(
        self, documents: List[Document], start_date: date, end_date: date
    ) -> List[Document]:
        filtered = []
        for doc in documents:
            doc_date = doc.date.date() if isinstance(doc.date, datetime) else doc.date
            if start_date <= doc_date <= end_date:
                filtered.append(doc)
        return filtered

    def _calculate_inventory_metrics(self) -> Dict[str, Any]:
        all_inventory = self.inventory_repo.get_all()
        products = self.product_repo.get_all()
        total_value = sum(
            item.quantity * products[item.product_id].price
            for item in all_inventory
            if item.product_id in products
        )
        return {"total_products": len(all_inventory), "total_value": total_value}

    def _calculate_document_metrics(self, documents: List[Document]) -> Dict[str, Any]:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for doc in documents:
            by_type[doc.doc_type.value] = by_type.get(doc.doc_type.value, 0) + 1
            by_status[doc.status.value] = by_status.get(doc.status.value, 0) + 1
        return {"by_type": by_type, "by_status": by_status, "total": len(documents)}

    def _calculate_warehouse_metrics(self) -> Dict[str, Any]:
        warehouses = self.warehouse_repo.get_all()
        return {"warehouse_count": len(warehouses)}

    def _generate_business_insights(
        self,
        inventory_data: Dict[str, Any],
        document_metrics: Dict[str, Any],
        warehouse_metrics: Dict[str, Any],
    ) -> List[str]:
        insights = []
        if inventory_data.get("total_value", 0) == 0:
            insights.append("Total inventory value is zero; check imports and stock updates.")
        if document_metrics.get("total", 0) == 0:
            insights.append("No documents in the selected period.")
        if warehouse_metrics.get("warehouse_count", 0) == 0:
            insights.append("No warehouses configured.")
        return insights

    def _generate_recommendations(self, insights: List[str]) -> List[str]:
        if not insights:
            return []
        return [f"Review: {i}" for i in insights]
