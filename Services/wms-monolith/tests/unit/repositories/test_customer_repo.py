"""
Comprehensive Unit Tests for CustomerRepo
Covers all CustomerRepo methods, validation, edge cases, and database operations
"""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from sqlalchemy.orm import Session
from typing import List

from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
# Use mock models to avoid SQLAlchemy dependency issues
try:
    # Import all models using the centralized import function to avoid SQLAlchemy mapper errors
    from app.shared.core.database import import_all_models
    import_all_models()
    from app.modules.customers.infrastructure.models.customer import CustomerModel
    from app.modules.customers.infrastructure.models.customer_purchase import CustomerPurchaseModel
    REAL_MODELS_AVAILABLE = True
except ImportError:
    from tests.mocks.models import MockCustomerModel as CustomerModel
    REAL_MODELS_AVAILABLE = False


class TestCustomerRepo:
    """Test Customer Repository Implementation"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        session = Mock(spec=Session)
        session.get = Mock()
        session.add = Mock()
        session.execute = Mock()
        session.commit = Mock()
        session.flush = Mock()
        session.refresh = Mock()
        session.expunge = Mock()
        # Make session support 'in' operator
        session.__contains__ = Mock(return_value=True)
        return session

    @pytest.fixture
    def customer_repo(self, mock_session):
        """CustomerRepo with mocked session"""
        return CustomerRepo(session=mock_session)

    @pytest.fixture
    def sample_customer_model(self):
        """Sample CustomerModel for testing"""
        return CustomerModel(
            customer_id=1,
            name="Test Customer",
            email="test@example.com",
            phone="123-456-7890",
            address="123 Test St",
            debt_balance=100.0
        )

    @pytest.fixture
    def sample_customer_purchase_model(self):
        """Sample CustomerPurchaseModel for testing"""
        return CustomerPurchaseModel(
            customer_id=1,
            document_id=10,
            total_value=50.0
        )

    # ============================================================================
    # CREATE TESTS
    # ============================================================================

    def test_create_customer(self, customer_repo, mock_session):
        """Test creating a new customer"""
        data = {
            "customer_id": 1,
            "name": "Test Customer",
            "email": "test@example.com",
            "phone": "123-456-7890",
            "address": "123 Test St"
        }
        
        result = customer_repo.create(data)
        
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result is not None

    def test_create_customer_with_auto_commit_disabled(self, customer_repo, mock_session):
        """Test creating customer with auto_commit disabled"""
        customer_repo.set_auto_commit(False)
        data = {"customer_id": 1, "name": "Test Customer"}
        
        customer_repo.create(data)
        
        mock_session.add.assert_called_once()
        mock_session.commit.assert_not_called()

    # ============================================================================
    # GET TESTS
    # ============================================================================

    def test_get_customer_found(self, customer_repo, mock_session, sample_customer_model):
        """Test getting a customer by ID when found"""
        mock_session.get.return_value = sample_customer_model
        
        result = customer_repo.get(1)
        
        mock_session.get.assert_called_once_with(CustomerModel, 1)
        assert result == sample_customer_model

    def test_get_customer_not_found(self, customer_repo, mock_session):
        """Test getting a customer by ID when not found"""
        mock_session.get.return_value = None
        
        result = customer_repo.get(999)
        
        mock_session.get.assert_called_once_with(CustomerModel, 999)
        assert result is None

    # ============================================================================
    # GET ALL TESTS
    # ============================================================================

    def test_get_all_customers(self, customer_repo, mock_session, sample_customer_model):
        """Test getting all customers"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_customer_model]
        mock_session.execute.return_value = mock_result
        
        result = customer_repo.get_all()
        
        mock_session.flush.assert_called_once()
        mock_session.execute.assert_called_once()
        assert len(result) == 1
        assert result[0] == sample_customer_model

    def test_get_all_customers_empty(self, customer_repo, mock_session):
        """Test getting all customers when none exist"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = customer_repo.get_all()
        
        assert len(result) == 0

    # ============================================================================
    # UPDATE DEBT TESTS
    # ============================================================================

    def test_update_debt_positive_delta(self, customer_repo, mock_session, sample_customer_model):
        """Test updating debt with positive delta"""
        mock_session.get.return_value = sample_customer_model
        
        customer_repo.update_debt(1, 50.0)
        
        assert sample_customer_model.debt_balance == 150.0
        mock_session.commit.assert_called_once()

    def test_update_debt_negative_delta(self, customer_repo, mock_session, sample_customer_model):
        """Test updating debt with negative delta"""
        mock_session.get.return_value = sample_customer_model
        
        customer_repo.update_debt(1, -50.0)
        
        assert sample_customer_model.debt_balance == 50.0
        mock_session.commit.assert_called_once()

    def test_update_debt_customer_not_found(self, customer_repo, mock_session):
        """Test updating debt when customer not found"""
        mock_session.get.return_value = None
        
        customer_repo.update_debt(999, 50.0)
        
        mock_session.commit.assert_not_called()

    # ============================================================================
    # RECORD PURCHASE TESTS
    # ============================================================================

    def test_record_purchase(self, customer_repo, mock_session, sample_customer_model):
        """Test recording a purchase"""
        mock_session.get.return_value = sample_customer_model
        
        customer_repo.record_purchase(1, 10, 75.0)
        
        mock_session.add.assert_called()
        mock_session.commit.assert_called()
        assert sample_customer_model.debt_balance == 175.0

    # ============================================================================
    # LIST PURCHASES TESTS
    # ============================================================================

    def test_list_purchases(self, customer_repo, mock_session, sample_customer_purchase_model):
        """Test listing customer purchases"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_customer_purchase_model]
        mock_session.execute.return_value = mock_result
        
        result = customer_repo.list_purchases(1)
        
        assert len(result) == 1
        assert result[0]["document_id"] == 10
        assert result[0]["total_value"] == 50.0

    def test_list_purchases_empty(self, customer_repo, mock_session):
        """Test listing purchases when none exist"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = customer_repo.list_purchases(1)
        
        assert len(result) == 0

    # ============================================================================
    # UPDATE TESTS
    # ============================================================================

    def test_update_customer(self, customer_repo, mock_session, sample_customer_model):
        """Test updating customer data"""
        mock_session.get.return_value = sample_customer_model
        
        customer_repo.update(1, {"name": "Updated Name", "email": "updated@example.com"})
        
        assert sample_customer_model.name == "Updated Name"
        assert sample_customer_model.email == "updated@example.com"
        mock_session.commit.assert_called_once()

    def test_update_customer_with_none_values(self, customer_repo, mock_session, sample_customer_model):
        """Test updating customer with None values (should not update)"""
        mock_session.get.return_value = sample_customer_model
        original_name = sample_customer_model.name
        
        customer_repo.update(1, {"name": None, "email": "updated@example.com"})
        
        assert sample_customer_model.name == original_name
        assert sample_customer_model.email == "updated@example.com"

    def test_update_customer_not_found(self, customer_repo, mock_session):
        """Test updating customer when not found"""
        mock_session.get.return_value = None
        
        customer_repo.update(999, {"name": "Updated"})
        
        mock_session.commit.assert_not_called()

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_update_debt_zero_delta(self, customer_repo, mock_session, sample_customer_model):
        """Test updating debt with zero delta"""
        mock_session.get.return_value = sample_customer_model
        original_balance = sample_customer_model.debt_balance
        
        customer_repo.update_debt(1, 0.0)
        
        assert sample_customer_model.debt_balance == original_balance

    def test_update_debt_large_delta(self, customer_repo, mock_session, sample_customer_model):
        """Test updating debt with large delta"""
        mock_session.get.return_value = sample_customer_model
        
        customer_repo.update_debt(1, 1000000.0)
        
        assert sample_customer_model.debt_balance == 1000100.0

    def test_record_purchase_zero_value(self, customer_repo, mock_session, sample_customer_model):
        """Test recording purchase with zero value"""
        mock_session.get.return_value = sample_customer_model
        
        customer_repo.record_purchase(1, 10, 0.0)
        
        assert sample_customer_model.debt_balance == 100.0

    # ============================================================================
    # AUTO COMMIT TESTS
    # ============================================================================

    def test_set_auto_commit_true(self, customer_repo):
        """Test enabling auto commit"""
        customer_repo.set_auto_commit(True)
        assert customer_repo.auto_commit is True

    def test_set_auto_commit_false(self, customer_repo):
        """Test disabling auto commit"""
        customer_repo.set_auto_commit(False)
        assert customer_repo.auto_commit is False
