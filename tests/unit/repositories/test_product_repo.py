"""
Comprehensive Unit Tests for ProductRepo
Covers all ProductRepo methods, validation, edge cases, and database operations
"""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.infrastructure.persistence.repositories.product_repo import ProductRepo
from app.domain.entities.product import Product
# Use mock models to avoid SQLAlchemy dependency issues
try:
    from app.infrastructure.persistence.models import ProductModel, InventoryModel
    REAL_MODELS_AVAILABLE = True
except ImportError:
    from tests.mocks.models import MockProductModel as ProductModel, MockInventoryModel as InventoryModel
    REAL_MODELS_AVAILABLE = False



class TestProductRepo:
    """Test Product Repository Implementation"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        session = Mock(spec=Session)
        session.get = Mock()
        session.add = Mock()
        session.delete = Mock()
        session.execute = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session

    @pytest.fixture
    def product_repo(self, mock_session):
        """ProductRepo instance with mocked session"""
        return ProductRepo(session=mock_session, auto_commit=False)

    @pytest.fixture
    def product_repo_auto_commit(self, mock_session):
        """ProductRepo instance with auto_commit enabled"""
        return ProductRepo(session=mock_session, auto_commit=True)

    @pytest.fixture
    def sample_product(self):
        """Sample product for testing"""
        return Product(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )

    @pytest.fixture
    def sample_product_model(self):
        """Sample ProductModel for testing"""
        return ProductModel(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_product_repo_initialization(self, mock_session):
        """Test ProductRepo initialization"""
        repo = ProductRepo(session=mock_session, auto_commit=False)
        
        assert repo.session == mock_session
        assert repo._auto_commit is False

    def test_product_repo_initialization_auto_commit(self, mock_session):
        """Test ProductRepo initialization with auto_commit"""
        repo = ProductRepo(session=mock_session, auto_commit=True)
        
        assert repo.session == mock_session
        assert repo._auto_commit is True

    def test_product_repo_initialization_default_auto_commit(self, mock_session):
        """Test ProductRepo initialization with default auto_commit"""
        repo = ProductRepo(session=mock_session)
        
        assert repo._auto_commit is False

    # ============================================================================
    # SAVE TESTS
    # ============================================================================

    def test_save_new_product(self, product_repo, mock_session, sample_product, sample_product_model):
        """Test save method with new product"""
        # Mock session.get to return None (product doesn't exist)
        mock_session.get.return_value = None
        
        # Mock the execute result for get_all
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        product_repo.save(sample_product)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(ProductModel, 1)
        
        # Verify session.add was called (new product)
        mock_session.add.assert_called_once()
        
        # Verify commit was not called (auto_commit=False)
        mock_session.commit.assert_not_called()

    def test_save_existing_product(self, product_repo, mock_session, sample_product, sample_product_model):
        """Test save method with existing product"""
        # Mock session.get to return existing product
        mock_session.get.return_value = sample_product_model
        
        product_repo.save(sample_product)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(ProductModel, 1)
        
        # Verify session.add was not called (existing product)
        mock_session.add.assert_not_called()
        
        # Verify existing model was updated
        assert sample_product_model.name == "Test Product"
        assert sample_product_model.description == "Test Description"
        assert sample_product_model.price == 99.99

    def test_save_with_auto_commit(self, product_repo_auto_commit, mock_session, sample_product):
        """Test save method with auto_commit enabled"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        product_repo_auto_commit.save(sample_product)
        
        # Verify commit was called (auto_commit=True)
        mock_session.commit.assert_called_once()

    def test_save_product_without_description(self, product_repo, mock_session):
        """Test save method with product without description"""
        product = Product(product_id=1, name="Test Product", price=99.99)
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        product_repo.save(product)
        
        # Verify session.add was called
        mock_session.add.assert_called_once()
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.description is None

    def test_save_product_with_zero_price(self, product_repo, mock_session):
        """Test save method with product with zero price"""
        product = Product(product_id=1, name="Test Product", price=0.0)
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        product_repo.save(product)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.price == 0.0

    def test_save_product_with_large_values(self, product_repo, mock_session):
        """Test save method with product having large values"""
        product = Product(
            product_id=999999,
            name="A" * 100,
            description="B" * 1000,
            price=999999.99
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        product_repo.save(product)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.product_id == 999999
        assert added_model.name == "A" * 100
        assert added_model.description == "B" * 1000
        assert added_model.price == 999999.99

    # ============================================================================
    # GET TESTS
    # ============================================================================

    def test_get_product_found(self, product_repo, mock_session, sample_product_model):
        """Test get method when product is found"""
        # Mock session.get to return product model
        mock_session.get.return_value = sample_product_model
        
        result = product_repo.get(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(ProductModel, 1)
        
        # Verify result
        assert result is not None
        assert result.product_id == 1
        assert result.name == "Test Product"
        assert result.description == "Test Description"
        assert result.price == 99.99

    def test_get_product_not_found(self, product_repo, mock_session):
        """Test get method when product is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        result = product_repo.get(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(ProductModel, 1)
        
        # Verify result
        assert result is None

    def test_get_product_with_none_description(self, product_repo, mock_session):
        """Test get method when product has no description"""
        # Create model with None description
        product_model = ProductModel(
            product_id=1,
            name="Test Product",
            description=None,
            price=99.99
        )
        
        # Mock session.get to return product model
        mock_session.get.return_value = product_model
        
        result = product_repo.get(1)
        
        # Verify result
        assert result is not None
        assert result.description is None

    # ============================================================================
    # GET ALL TESTS
    # ============================================================================

    def test_get_all_products_success(self, product_repo, mock_session):
        """Test get_all method successful retrieval"""
        # Create sample models
        product_model1 = ProductModel(product_id=1, name="Product 1", description="Desc 1", price=10.0)
        product_model2 = ProductModel(product_id=2, name="Product 2", description="Desc 2", price=20.0)
        
        # Mock session.execute to return models
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [product_model1, product_model2]
        mock_session.execute.return_value = mock_result
        
        result = product_repo.get_all()
        
        # Verify session.execute was called
        mock_session.execute.assert_called_once()
        
        # Verify result
        assert len(result) == 2
        assert 1 in result
        assert 2 in result
        assert result[1].name == "Product 1"
        assert result[2].name == "Product 2"

    def test_get_all_products_empty(self, product_repo, mock_session):
        """Test get_all method with no products"""
        # Mock session.execute to return empty list
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = product_repo.get_all()
        
        # Verify result
        assert result == {}

    def test_get_all_products_with_none_descriptions(self, product_repo, mock_session):
        """Test get_all method with products having None descriptions"""
        # Create models with None descriptions
        product_model1 = ProductModel(product_id=1, name="Product 1", description=None, price=10.0)
        product_model2 = ProductModel(product_id=2, name="Product 2", description=None, price=20.0)
        
        # Mock session.execute to return models
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [product_model1, product_model2]
        mock_session.execute.return_value = mock_result
        
        result = product_repo.get_all()
        
        # Verify result
        assert len(result) == 2
        assert result[1].description is None
        assert result[2].description is None

    # ============================================================================
    # GET PRICE TESTS
    # ============================================================================

    def test_get_price_success(self, product_repo, mock_session, sample_product_model):
        """Test get_price method successful retrieval"""
        # Mock get to return product model
        mock_session.get.return_value = sample_product_model
        
        result = product_repo.get_price(1)
        
        # Verify get was called
        mock_session.get.assert_called_once_with(ProductModel, 1)
        
        # Verify result
        assert result == 99.99

    def test_get_price_product_not_found(self, product_repo, mock_session):
        """Test get_price method when product not found"""
        # Mock get to return None
        mock_session.get.return_value = None
        
        with pytest.raises(KeyError, match="Product not found"):
            product_repo.get_price(1)

    def test_get_price_zero_price(self, product_repo, mock_session):
        """Test get_price method with zero price"""
        # Create model with zero price
        product_model = ProductModel(product_id=1, name="Test Product", description=None, price=0.0)
        
        # Mock get to return product model
        mock_session.get.return_value = product_model
        
        result = product_repo.get_price(1)
        
        # Verify result
        assert result == 0.0

    # ============================================================================
    # DELETE TESTS
    # ============================================================================

    def test_delete_product_success(self, product_repo, mock_session, sample_product_model):
        """Test delete method successful deletion"""
        # Mock session.get to return product model
        mock_session.get.return_value = sample_product_model
        
        product_repo.delete(1)
        
        # Verify session.get was called for product
        mock_session.get.assert_any_call(ProductModel, 1)
        
        # Verify session.delete was called for product (may be called multiple times in implementation)
        assert mock_session.delete.call_count >= 1
        assert mock_session.delete.call_args_list[0][0][0] == sample_product_model

    def test_delete_product_not_found(self, product_repo, mock_session):
        """Test delete method when product not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        with pytest.raises(KeyError, match="Product not found"):
            product_repo.delete(1)

    def test_delete_product_with_inventory(self, product_repo, mock_session, sample_product_model):
        """Test delete method when product has inventory"""
        # Create inventory model
        inventory_model = InventoryModel(product_id=1, quantity=50)
        
        # Mock session.get to return models
        mock_session.get.side_effect = [sample_product_model, inventory_model]
        
        product_repo.delete(1)
        
        # Verify both product and inventory were deleted
        mock_session.delete.assert_any_call(sample_product_model)
        mock_session.delete.assert_any_call(inventory_model)
        assert mock_session.delete.call_count == 2

    def test_delete_product_without_inventory(self, product_repo, mock_session, sample_product_model):
        """Test delete method when product has no inventory"""
        # Mock session.get to return product model and None for inventory
        mock_session.get.side_effect = [sample_product_model, None]
        
        product_repo.delete(1)
        
        # Verify only product was deleted
        mock_session.delete.assert_called_once_with(sample_product_model)

    # ============================================================================
    # TO DOMAIN TESTS
    # ============================================================================

    def test_to_domain_conversion(self):
        """Test _to_domain static method"""
        # Create product model
        product_model = ProductModel(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )
        
        result = ProductRepo._to_domain(product_model)
        
        # Verify conversion
        assert result.product_id == 1
        assert result.name == "Test Product"
        assert result.description == "Test Description"
        assert result.price == 99.99
        assert isinstance(result, Product)

    def test_to_domain_conversion_with_none_description(self):
        """Test _to_domain static method with None description"""
        # Create product model with None description
        product_model = ProductModel(
            product_id=1,
            name="Test Product",
            description=None,
            price=99.99
        )
        
        result = ProductRepo._to_domain(product_model)
        
        # Verify conversion
        assert result.description is None

    def test_to_domain_conversion_with_zero_price(self):
        """Test _to_domain static method with zero price"""
        # Create product model with zero price
        product_model = ProductModel(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=0.0
        )
        
        result = ProductRepo._to_domain(product_model)
        
        # Verify conversion
        assert result.price == 0.0

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    def test_save_then_get_integration(self, product_repo, mock_session, sample_product):
        """Test integration between save and get methods"""
        # Mock session.get to return None first, then product model
        product_model = ProductModel(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )
        mock_session.get.side_effect = [None, product_model]
        
        # Save product
        product_repo.save(sample_product)
        
        # Get product
        result = product_repo.get(1)
        
        # Verify result
        assert result is not None
        assert result.product_id == 1
        assert result.name == "Test Product"

    def test_save_then_get_all_integration(self, product_repo, mock_session, sample_product):
        """Test integration between save and get_all methods"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        # Mock session.execute for get_all
        product_model = ProductModel(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [product_model]
        mock_session.execute.return_value = mock_result
        
        # Save product
        product_repo.save(sample_product)
        
        # Get all products
        result = product_repo.get_all()
        
        # Verify result
        assert len(result) == 1
        assert 1 in result
        assert result[1].name == "Test Product"

    def test_save_then_delete_integration(self, product_repo, mock_session, sample_product):
        """Test integration between save and delete methods"""
        # Mock session.get to return None first, then product model
        product_model = ProductModel(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )
        mock_session.get.side_effect = [None, product_model]
        
        # Save product
        product_repo.save(sample_product)
        
        # Reset side_effect for delete operation
        mock_session.get.side_effect = None
        mock_session.get.return_value = product_model  # Return the saved product model
        
        # Delete product
        with patch('app.infrastructure.persistence.repositories.product_repo.InventoryModel') as mock_inventory_model:
            mock_inventory_model.return_value = Mock()
            product_repo.delete(1)
        
        # Verify delete was called (may be called multiple times in implementation)
        assert mock_session.delete.call_count >= 1

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_save_product_with_unicode_data(self, product_repo, mock_session):
        """Test save method with Unicode data"""
        product = Product(
            product_id=1,
            name="Üñïçødé Prödüçt",
            description="Üñïçødé dëscrïptïøn",
            price=99.99
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        product_repo.save(product)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.name == "Üñïçødé Prödüçt"
        assert added_model.description == "Üñïçødé dëscrïptïøn"

    def test_save_product_with_special_characters(self, product_repo, mock_session):
        """Test save method with special characters"""
        product = Product(
            product_id=1,
            name="Product-123_@#$%",
            description="Special chars: !@#$%^&*()",
            price=99.99
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        product_repo.save(product)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.name == "Product-123_@#$%"
        assert added_model.description == "Special chars: !@#$%^&*()"

    def test_save_product_with_large_id(self, product_repo, mock_session):
        """Test save method with large product ID"""
        product = Product(
            product_id=2147483647,  # Max int
            name="Large ID Product",
            price=99.99
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        product_repo.save(product)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.product_id == 2147483647

    def test_get_product_with_large_id(self, product_repo, mock_session):
        """Test get method with large product ID"""
        product_model = ProductModel(
            product_id=2147483647,
            name="Large ID Product",
            description="Large ID Description",
            price=99.99
        )
        
        # Mock session.get to return product model
        mock_session.get.return_value = product_model
        
        result = product_repo.get(2147483647)
        
        # Verify result
        assert result is not None
        assert result.product_id == 2147483647

    def test_delete_product_with_large_id(self, product_repo, mock_session):
        """Test delete method with large product ID"""
        product_model = ProductModel(
            product_id=2147483647,
            name="Large ID Product",
            description="Large ID Description",
            price=99.99
        )
        
        # Mock session.get to return product model
        mock_session.get.return_value = product_model
        
        product_repo.delete(2147483647)
        
        # Verify session.delete was called for product (may be called multiple times in implementation)
        assert mock_session.delete.call_count >= 1
        assert mock_session.delete.call_args_list[0][0][0] == product_model

    def test_save_product_with_decimal_price(self, product_repo, mock_session):
        """Test save method with decimal price"""
        product = Product(
            product_id=1,
            name="Decimal Price Product",
            price=99.999
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        product_repo.save(product)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.price == 99.999

    def test_get_price_with_decimal_price(self, product_repo, mock_session):
        """Test get_price method with decimal price"""
        product_model = ProductModel(
            product_id=1,
            name="Decimal Price Product",
            description="Decimal Price Description",
            price=99.999
        )
        
        # Mock session.get to return product model
        mock_session.get.return_value = product_model
        
        result = product_repo.get_price(1)
        
        # Verify result
        assert result == 99.999

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_save_database_error_handling(self, product_repo, mock_session, sample_product):
        """Test save method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            product_repo.save(sample_product)

    def test_get_database_error_handling(self, product_repo, mock_session):
        """Test get method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            product_repo.get(1)

    def test_get_all_database_error_handling(self, product_repo, mock_session):
        """Test get_all method handles database errors gracefully"""
        # Mock session.execute to raise exception
        mock_session.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            product_repo.get_all()

    def test_delete_database_error_handling(self, product_repo, mock_session):
        """Test delete method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            product_repo.delete(1)
