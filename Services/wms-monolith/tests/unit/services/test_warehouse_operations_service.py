"""
Unit Tests for WarehouseOperationsService
"""

import pytest
from unittest.mock import Mock

from app.modules.warehouses.application.services.warehouse_operations_service import WarehouseOperationsService
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.modules.products.domain.entities.product import Product


class TestWarehouseOperationsService:
    @pytest.fixture
    def service(self):
        mock_warehouse_repo = Mock()
        mock_product_repo = Mock()
        mock_inventory_repo = Mock()
        mock_document_repo = Mock()
        return WarehouseOperationsService(mock_warehouse_repo, mock_product_repo, mock_inventory_repo, mock_document_repo)

    @pytest.fixture
    def sample_warehouse(self):
        return Warehouse(warehouse_id=1, location="Main Warehouse")

    @pytest.fixture
    def sample_product(self):
        return Product(product_id=1, name="Test Product", price=99.99)

    def test_get_system_overview(self, service, sample_warehouse, sample_product):
        service.warehouse_repo.get_all.return_value = {1: sample_warehouse}
        service.product_repo.get_all.return_value = {1: sample_product}
        service.inventory_repo.get_all.return_value = [Mock(product_id=1, quantity=50)]

        result = service.get_system_overview()
        assert result["total_warehouses"] == 1
        assert result["total_products"] == 1

    def test_optimize_inventory_distribution(self, service, sample_product, sample_warehouse):
        service.product_repo.get.return_value = sample_product
        service.warehouse_repo.get_all.return_value = {1: sample_warehouse}
        service.warehouse_repo.get_warehouse_inventory.return_value = [Mock(product_id=1, quantity=50)]

        result = service.optimize_inventory_distribution(1)
        assert result["product_id"] == 1
        assert len(result["distribution"]) == 1

    def test_bulk_transfer_products(self, service):
        transfers = [{"from_warehouse_id": 1, "to_warehouse_id": 2, "product_id": 1, "quantity": 50}]
        service.warehouse_repo.get_warehouse_inventory.return_value = [Mock(product_id=1, quantity=100)]

        result = service.bulk_transfer_products(transfers)
        assert result["total_transfers"] == 1
        assert result["successful"] == 1

    def test_get_inventory_health_report(self, service, sample_warehouse, sample_product):
        service.warehouse_repo.get_all.return_value = {1: sample_warehouse}
        service.product_repo.get_all.return_value = {1: sample_product}
        service.warehouse_repo.get_warehouse_inventory.return_value = [Mock(product_id=1, quantity=50)]

        result = service.get_inventory_health_report()
        assert len(result["warehouses"]) == 1
