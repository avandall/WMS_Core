"""
Unit Tests for ReportOrchestrator
"""

import pytest
from unittest.mock import Mock
from datetime import date, timedelta

from app.shared.application.services.report_orchestrator import ReportOrchestrator
from app.shared.core.exceptions import ReportGenerationError


class TestReportOrchestrator:
    @pytest.fixture
    def service(self):
        mock_product_repo = Mock()
        mock_document_repo = Mock()
        mock_warehouse_repo = Mock()
        mock_inventory_repo = Mock()
        mock_customer_repo = Mock()
        return ReportOrchestrator(mock_product_repo, mock_document_repo, mock_warehouse_repo, mock_inventory_repo, mock_customer_repo)

    def test_generate_inventory_report_total(self, service):
        service.warehouse_repo.get_all.return_value = {}
        service.inventory_repo.get_all.return_value = []
        service.product_repo.get_all.return_value = {}

        result = service.generate_inventory_report()
        assert "warehouses" in result or "total_products" in result

    def test_generate_inventory_report_warehouse_specific(self, service):
        service.warehouse_repo.get.return_value = Mock()
        service.inventory_repo.get_all.return_value = []
        service.product_repo.get_all.return_value = {}
        service.warehouse_repo.get_warehouse_inventory.return_value = []

        result = service.generate_inventory_report(warehouse_id=1)
        assert result is not None

    def test_generate_product_movement_report(self, service):
        service.document_repo.get_all.return_value = []
        
        result = service.generate_product_movement_report()
        assert "documents" in result or "movements" in result or result is not None

    def test_generate_warehouse_performance_report(self, service):
        service.warehouse_repo.get_all.return_value = {}
        service.document_repo.get_all.return_value = []
        
        result = service.generate_warehouse_performance_report()
        assert result is not None

    def test_generate_report_with_error(self, service):
        service.warehouse_repo.get_all.side_effect = Exception("DB Error")
        
        with pytest.raises(ReportGenerationError):
            service.generate_inventory_report()
