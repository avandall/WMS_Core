"""
Comprehensive Unit Tests for CustomerService
Covers all CustomerService methods, validation, edge cases, and business logic
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from app.modules.customers.application.services.customer_service import CustomerService
from app.modules.customers.domain.interfaces.customer_repo import ICustomerRepo


class TestCustomerService:
    """Test CustomerService Application Service"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_customer_repo(self):
        """Mock customer repository"""
        return Mock(spec=ICustomerRepo)

    @pytest.fixture
    def customer_service(self, mock_customer_repo):
        """CustomerService instance with mocked dependencies"""
        return CustomerService(mock_customer_repo)

    @pytest.fixture
    def sample_customer_data(self):
        """Sample customer data for testing"""
        return {
            "customer_id": 1,
            "name": "Test Customer",
            "email": "test@example.com",
            "phone": "123-456-7890",
            "address": "123 Test St",
            "debt_balance": 100.0,
            "created_at": datetime.now(),
        }

    @pytest.fixture
    def sample_customer(self, sample_customer_data):
        """Sample customer object for testing"""
        customer = Mock()
        customer.customer_id = sample_customer_data["customer_id"]
        customer.name = sample_customer_data["name"]
        customer.email = sample_customer_data["email"]
        customer.phone = sample_customer_data["phone"]
        customer.address = sample_customer_data["address"]
        customer.debt_balance = sample_customer_data["debt_balance"]
        customer.created_at = sample_customer_data["created_at"]
        return customer

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_customer_service_initialization(self, mock_customer_repo):
        """Test CustomerService initialization"""
        service = CustomerService(mock_customer_repo)
        assert service.customer_repo == mock_customer_repo

    # ============================================================================
    # CREATE CUSTOMER TESTS
    # ============================================================================

    def test_create_customer(self, customer_service, mock_customer_repo, sample_customer_data):
        """Test create customer"""
        mock_customer_repo.create.return_value = sample_customer_data

        result = customer_service.create(sample_customer_data)

        mock_customer_repo.create.assert_called_once_with(sample_customer_data)
        assert result == sample_customer_data

    # ============================================================================
    # LIST CUSTOMERS TESTS
    # ============================================================================

    def test_list_customers_empty(self, customer_service, mock_customer_repo):
        """Test list customers with no customers"""
        mock_customer_repo.get_all.return_value = []
        mock_customer_repo.list_purchases.return_value = []

        result = customer_service.list()

        assert result == []
        mock_customer_repo.get_all.assert_called_once()

    def test_list_customers_single(self, customer_service, mock_customer_repo, sample_customer):
        """Test list customers with single customer"""
        mock_customer_repo.get_all.return_value = [sample_customer]
        mock_customer_repo.list_purchases.return_value = []

        result = customer_service.list()

        assert len(result) == 1
        assert result[0]["customer_id"] == sample_customer.customer_id
        assert result[0]["name"] == sample_customer.name
        assert result[0]["email"] == sample_customer.email
        assert result[0]["debt_balance"] == sample_customer.debt_balance
        assert result[0]["purchase_count"] == 0
        assert result[0]["total_purchased"] == 0

    def test_list_customers_multiple(self, customer_service, mock_customer_repo):
        """Test list customers with multiple customers"""
        customer1 = Mock()
        customer1.customer_id = 1
        customer1.name = "Customer 1"
        customer1.email = "customer1@example.com"
        customer1.phone = "111-111-1111"
        customer1.address = "Address 1"
        customer1.debt_balance = 50.0
        customer1.created_at = datetime.now()

        customer2 = Mock()
        customer2.customer_id = 2
        customer2.name = "Customer 2"
        customer2.email = "customer2@example.com"
        customer2.phone = "222-222-2222"
        customer2.address = "Address 2"
        customer2.debt_balance = 75.0
        customer2.created_at = datetime.now()

        mock_customer_repo.get_all.return_value = [customer1, customer2]
        mock_customer_repo.list_purchases.return_value = []

        result = customer_service.list()

        assert len(result) == 2
        assert result[0]["customer_id"] == 1
        assert result[1]["customer_id"] == 2

    def test_list_customers_with_purchases(self, customer_service, mock_customer_repo, sample_customer):
        """Test list customers with purchase statistics"""
        mock_customer_repo.get_all.return_value = [sample_customer]
        mock_customer_repo.list_purchases.return_value = [
            {"document_id": 1, "total_value": 100.0},
            {"document_id": 2, "total_value": 50.0},
        ]

        result = customer_service.list()

        assert len(result) == 1
        assert result[0]["purchase_count"] == 2
        assert result[0]["total_purchased"] == 150.0

    # ============================================================================
    # GET CUSTOMER TESTS
    # ============================================================================

    def test_get_customer_found(self, customer_service, mock_customer_repo, sample_customer):
        """Test get customer when found"""
        mock_customer_repo.get.return_value = sample_customer
        mock_customer_repo.list_purchases.return_value = []

        result = customer_service.get(1)

        assert result is not None
        assert result["customer_id"] == sample_customer.customer_id
        assert result["name"] == sample_customer.name
        mock_customer_repo.get.assert_called_once_with(1)

    def test_get_customer_not_found(self, customer_service, mock_customer_repo):
        """Test get customer when not found"""
        mock_customer_repo.get.return_value = None

        result = customer_service.get(999)

        assert result is None
        mock_customer_repo.get.assert_called_once_with(999)

    def test_get_customer_with_purchases(self, customer_service, mock_customer_repo, sample_customer):
        """Test get customer with purchase history"""
        mock_customer_repo.get.return_value = sample_customer
        mock_customer_repo.list_purchases.return_value = [
            {"document_id": 1, "total_value": 100.0},
        ]

        result = customer_service.get(1)

        assert result is not None
        assert "purchases" in result
        assert len(result["purchases"]) == 1
        assert result["purchase_count"] == 1
        assert result["total_purchased"] == 100.0

    # ============================================================================
    # UPDATE DEBT TESTS
    # ============================================================================

    def test_update_debt(self, customer_service, mock_customer_repo):
        """Test update customer debt"""
        customer_service.update_debt(1, 50.0)

        mock_customer_repo.update_debt.assert_called_once_with(1, 50.0)

    def test_update_debt_negative(self, customer_service, mock_customer_repo):
        """Test update customer debt with negative delta"""
        customer_service.update_debt(1, -25.0)

        mock_customer_repo.update_debt.assert_called_once_with(1, -25.0)

    # ============================================================================
    # UPDATE CUSTOMER TESTS
    # ============================================================================

    def test_update_customer(self, customer_service, mock_customer_repo):
        """Test update customer"""
        update_data = {"name": "Updated Name", "email": "updated@example.com"}

        customer_service.update(1, update_data)

        mock_customer_repo.update.assert_called_once_with(1, update_data)

    # ============================================================================
    # RECORD PURCHASE TESTS
    # ============================================================================

    def test_record_purchase(self, customer_service, mock_customer_repo):
        """Test record purchase"""
        customer_service.record_purchase(1, 100, 250.0)

        mock_customer_repo.record_purchase.assert_called_once_with(1, 100, 250.0)

    # ============================================================================
    # PURCHASES TESTS
    # ============================================================================

    def test_purchases(self, customer_service, mock_customer_repo):
        """Test get customer purchases"""
        expected_purchases = [
            {"document_id": 1, "total_value": 100.0},
            {"document_id": 2, "total_value": 50.0},
        ]
        mock_customer_repo.list_purchases.return_value = expected_purchases

        result = customer_service.purchases(1)

        assert result == expected_purchases
        mock_customer_repo.list_purchases.assert_called_once_with(1)

    def test_purchases_empty(self, customer_service, mock_customer_repo):
        """Test get customer purchases with no purchases"""
        mock_customer_repo.list_purchases.return_value = []

        result = customer_service.purchases(1)

        assert result == []
        mock_customer_repo.list_purchases.assert_called_once_with(1)

    # ============================================================================
    # PURCHASE STATS TESTS
    # ============================================================================

    def test_purchase_stats_empty(self, customer_service, mock_customer_repo):
        """Test purchase stats with no purchases"""
        mock_customer_repo.list_purchases.return_value = []

        # Access private method for testing
        result = customer_service._purchase_stats(1)

        assert result["purchase_count"] == 0
        assert result["total_purchased"] == 0

    def test_purchase_stats_with_purchases(self, customer_service, mock_customer_repo):
        """Test purchase stats with purchases"""
        mock_customer_repo.list_purchases.return_value = [
            {"document_id": 1, "total_value": 100.0},
            {"document_id": 2, "total_value": 50.0},
            {"document_id": 3, "total_value": 75.0},
        ]

        result = customer_service._purchase_stats(1)

        assert result["purchase_count"] == 3
        assert result["total_purchased"] == 225.0
