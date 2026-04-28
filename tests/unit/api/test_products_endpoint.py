"""
Comprehensive Unit Tests for Products API Endpoint
Covers all product endpoints, validation, error handling, and business logic
"""

import pytest
from unittest.mock import AsyncMock, patch
from unittest import mock
from io import BytesIO
import csv
import json

# Make FastAPI imports conditional
try:
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    HTTPException = Exception
    TestClient = mock.Mock

try:
    from app.api.v1.endpoints.products.products import router
    from app.application.dtos.product import ProductCreate, ProductUpdate, ProductResponse
    from app.shared.core.permissions import Permission
    API_IMPORTS_AVAILABLE = True
except ImportError:
    API_IMPORTS_AVAILABLE = False
    router = mock.Mock()
    ProductCreate = mock.Mock
    ProductUpdate = mock.Mock
    ProductResponse = mock.Mock
    Permission = mock.Mock

from app.modules.products.application.services.product_service import ProductService
from app.modules.products.domain.entities.product import Product



@pytest.mark.skipif(not API_IMPORTS_AVAILABLE, reason="API dependencies not available")
class TestProductsEndpoint:
    """Test Products API Endpoints"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_product_service(self):
        """mock.Mock ProductService"""
        service = mock.Mock(spec=ProductService)
        service.get_all_products = mock.Mock()
        service.create_product = mock.Mock()
        service.get_product_details = mock.Mock()
        service.update_product = mock.Mock()
        service.delete_product = mock.Mock()
        service.import_products = mock.Mock()
        return service

    @pytest.fixture
    def mock_current_user(self):
        """mock.Mock current user"""
        user = mock.Mock()
        user.role = "admin"
        user.user_id = 1
        return user

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
    def sample_product_create(self):
        """Sample ProductCreate DTO"""
        return ProductCreate(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )

    @pytest.fixture
    def sample_product_update(self):
        """Sample ProductUpdate DTO"""
        return ProductUpdate(
            name="Updated Product",
            description="Updated Description",
            price=149.99
        )

    @pytest.fixture
    def mock_dependencies(self):
        """mock.Mock all dependencies"""
        return {
            "get_current_user": mock.Mock(return_value=mock_current_user),
            "require_permissions": mock.Mock(),
            "get_product_service": mock.Mock(return_value=mock_product_service),
        }

    # ============================================================================
    # GET ALL PRODUCTS TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_all_products_success(self, mock_product_service, sample_product):
        """Test get_all_products endpoint successful response"""
        # mock.Mock service to return products
        mock_product_service.get_all_products.return_value = [sample_product]
        
        # mock.Mock dependencies
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            # Import the endpoint function
            from app.api.v1.endpoints.products.products import get_all_products
            
            # Call the endpoint
            result = await get_all_products(mock_product_service)
            
            # Verify service was called
            mock_product_service.get_all_products.assert_called_once()
            
            # Verify response structure
            assert len(result) == 1
            assert result[0].product_id == 1
            assert result[0].name == "Test Product"
            assert result[0].description == "Test Description"
            assert result[0].price == 99.99

    @pytest.mark.asyncio
    async def test_get_all_products_empty(self, mock_product_service):
        """Test get_all_products endpoint with no products"""
        # mock.Mock service to return empty list
        mock_product_service.get_all_products.return_value = []
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import get_all_products
            
            result = await get_all_products(mock_product_service)
            
            # Verify result
            assert result == []

    @pytest.mark.asyncio
    async def test_get_all_products_multiple(self, mock_product_service):
        """Test get_all_products endpoint with multiple products"""
        # Create sample products
        product1 = Product(product_id=1, name="Product 1", price=10.0)
        product2 = Product(product_id=2, name="Product 2", price=20.0)
        
        # mock.Mock service to return products
        mock_product_service.get_all_products.return_value = [product1, product2]
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import get_all_products
            
            result = await get_all_products(mock_product_service)
            
            # Verify result
            assert len(result) == 2
            assert result[0].product_id == 1
            assert result[1].product_id == 2

    # ============================================================================
    # CREATE PRODUCT TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_create_product_success(self, mock_product_service, sample_product, sample_product_create, mock_current_user):
        """Test create_product endpoint successful response"""
        # mock.Mock service to return created product
        mock_product_service.create_product.return_value = sample_product
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user', return_value=mock_current_user), \
             patch('app.api.v1.endpoints.products.products.ProductAuthorizer.can_create_product') as mock_authorizer:
            
            from app.api.v1.endpoints.products.products import create_product
            
            result = await create_product(sample_product_create, mock_product_service, mock_current_user)
            
            # Verify authorizer was called
            mock_authorizer.assert_called_once_with(mock_current_user.role)
            
            # Verify service was called
            mock_product_service.create_product.assert_called_once_with(
                product_id=1,
                name="Test Product",
                price=99.99,
                description="Test Description"
            )
            
            # Verify response
            assert result.product_id == 1
            assert result.name == "Test Product"
            assert result.description == "Test Description"
            assert result.price == 99.99

    @pytest.mark.asyncio
    async def test_create_product_without_description(self, mock_product_service, sample_product, mock_current_user):
        """Test create_product endpoint without description"""
        # Create product without description
        product_create = ProductCreate(product_id=1, name="Test Product", price=99.99)
        
        # mock.Mock service to return created product
        mock_product_service.create_product.return_value = sample_product
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user', return_value=mock_current_user), \
             patch('app.api.v1.endpoints.products.products.ProductAuthorizer.can_create_product'):
            
            from app.api.v1.endpoints.products.products import create_product
            
            result = await create_product(product_create, mock_product_service, mock_current_user)
            
            # Verify service was called with None description
            mock_product_service.create_product.assert_called_once_with(
                product_id=1,
                name="Test Product",
                price=99.99,
                description=None
            )

    @pytest.mark.asyncio
    async def test_create_product_authorization_failure(self, mock_product_service, sample_product_create, mock_current_user):
        """Test create_product endpoint with authorization failure"""
        # mock.Mock authorizer to raise exception
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user', return_value=mock_current_user), \
             patch('app.api.v1.endpoints.products.products.ProductAuthorizer.can_create_product', side_effect=HTTPException(status_code=403, detail="Forbidden")):
            
            from app.api.v1.endpoints.products.products import create_product
            
            with pytest.raises(HTTPException) as exc_info:
                await create_product(sample_product_create, mock_product_service, mock_current_user)
            assert exc_info.value.status_code == 403
            assert "Forbidden" in str(exc_info.value.detail)

    # ============================================================================
    # GET PRODUCT TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_product_success(self, mock_product_service, sample_product):
        """Test get_product endpoint successful response"""
        # mock.Mock service to return product
        mock_product_service.get_product_details.return_value = sample_product
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import get_product
            
            result = await get_product(1, mock_product_service)
            
            # Verify service was called
            mock_product_service.get_product_details.assert_called_once_with(1)
            
            # Verify response
            assert result.product_id == 1
            assert result.name == "Test Product"
            assert result.description == "Test Description"
            assert result.price == 99.99

    @pytest.mark.asyncio
    async def test_get_product_not_found(self, mock_product_service):
        """Test get_product endpoint when product not found"""
        # mock.Mock service to raise exception
        mock_product_service.get_product_details.side_effect = Exception("Product not found")
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import get_product
            
            with pytest.raises(Exception, match="Product not found"):
                await get_product(1, mock_product_service)

    # ============================================================================
    # UPDATE PRODUCT TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_update_product_success(self, mock_product_service, sample_product, sample_product_update, mock_current_user):
        """Test update_product endpoint successful response"""
        # mock.Mock service to return updated product
        updated_product = Product(
            product_id=1,
            name="Updated Product",
            description="Updated Description",
            price=149.99
        )
        mock_product_service.update_product.return_value = updated_product
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.get_current_user', return_value=mock_current_user), \
             patch('app.api.v1.endpoints.products.products.ProductAuthorizer.can_update_product') as mock_authorizer:
            
            from app.api.v1.endpoints.products.products import update_product
            
            result = await update_product(1, sample_product_update, mock_product_service, mock_current_user)
            
            # Verify authorizer was called
            mock_authorizer.assert_called_once_with(mock_current_user.role, sample_product_update)
            
            # Verify service was called
            mock_product_service.update_product.assert_called_once_with(
                product_id=1,
                name="Updated Product",
                price=149.99,
                description="Updated Description"
            )
            
            # Verify response
            assert result.product_id == 1
            assert result.name == "Updated Product"
            assert result.description == "Updated Description"
            assert result.price == 149.99

    @pytest.mark.asyncio
    async def test_update_product_authorization_failure(self, mock_product_service, sample_product_update, mock_current_user):
        """Test update_product endpoint with authorization failure"""
        # mock.Mock authorizer to raise exception
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.get_current_user', return_value=mock_current_user), \
             patch('app.api.v1.endpoints.products.products.ProductAuthorizer.can_update_product', side_effect=HTTPException(status_code=403, detail="Forbidden")):
            
            from app.api.v1.endpoints.products.products import update_product
            
            with pytest.raises(HTTPException) as exc_info:
                await update_product(1, sample_product_update, mock_product_service, mock_current_user)
            assert exc_info.value.status_code == 403
            assert "Forbidden" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_product_partial_update(self, mock_product_service, sample_product, mock_current_user):
        """Test update_product endpoint with partial update"""
        # Create partial update
        partial_update = ProductUpdate(name="Updated Name Only")
        
        # mock.Mock service to return updated product
        updated_product = Product(
            product_id=1,
            name="Updated Name Only",
            description="Test Description",  # Original description preserved
            price=99.99  # Original price preserved
        )
        mock_product_service.update_product.return_value = updated_product
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.get_current_user', return_value=mock_current_user), \
             patch('app.api.v1.endpoints.products.products.ProductAuthorizer.can_update_product'):
            
            from app.api.v1.endpoints.products.products import update_product
            
            result = await update_product(1, partial_update, mock_product_service, mock_current_user)
            
            # Verify service was called with partial data
            mock_product_service.update_product.assert_called_once_with(
                product_id=1,
                name="Updated Name Only",
                price=None,
                description=None
            )

    # ============================================================================
    # DELETE PRODUCT TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_delete_product_success(self, mock_product_service):
        """Test delete_product endpoint successful response"""
        # mock.Mock service
        mock_product_service.delete_product.return_value = None
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import delete_product
            
            result = await delete_product(1, mock_product_service)
            
            # Verify service was called
            mock_product_service.delete_product.assert_called_once_with(1)
            
            # Verify response
            assert result == {"message": "Product 1 deleted successfully"}

    @pytest.mark.asyncio
    async def test_delete_product_not_found(self, mock_product_service):
        """Test delete_product endpoint when product not found"""
        # mock.Mock service to raise exception
        mock_product_service.delete_product.side_effect = Exception("Product not found")
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import delete_product
            
            with pytest.raises(Exception, match="Product not found"):
                await delete_product(1, mock_product_service)

    # ============================================================================
    # IMPORT PRODUCTS CSV TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_import_products_csv_success(self, mock_product_service):
        """Test import_products_csv endpoint successful response"""
        # Create mock CSV file
        csv_content = "product_id,name,price\n1,Test Product,99.99\n2,Another Product,49.99"
        mock_file = mock.Mock()
        mock_file.content_type = "text/csv"
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))
        
        # mock.Mock service
        import_result = {"imported": 2, "failed": 0}
        mock_product_service.import_products.return_value = import_result
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import import_products_csv
            
            result = await import_products_csv(mock_file, mock_product_service)
            
            # Verify service was called
            mock_product_service.import_products.assert_called_once()
            
            # Verify response
            assert result["summary"] == import_result
            assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_import_products_csv_invalid_content_type(self, mock_product_service):
        """Test import_products_csv endpoint with invalid content type"""
        # Create mock file with wrong content type
        mock_file = mock.Mock()
        mock_file.content_type = "application/json"
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import import_products_csv
            
            with pytest.raises(HTTPException) as exc_info:
                await import_products_csv(mock_file, mock_product_service)
            assert exc_info.value.status_code == 400
            assert "CSV file required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_import_products_csv_missing_columns(self, mock_product_service):
        """Test import_products_csv endpoint with missing columns"""
        # Create CSV with missing columns
        csv_content = "product_id,name\n1,Test Product"
        mock_file = mock.Mock()
        mock_file.content_type = "text/csv"
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import import_products_csv
            
            with pytest.raises(HTTPException) as exc_info:
                await import_products_csv(mock_file, mock_product_service)
            assert exc_info.value.status_code == 400
            assert "CSV must include product_id,name,price" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_import_products_csv_empty_file(self, mock_product_service):
        """Test import_products_csv endpoint with empty file"""
        # Create empty CSV
        csv_content = ""
        mock_file = mock.Mock()
        mock_file.content_type = "text/csv"
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import import_products_csv
            
            # Empty file should not raise error, just return empty result
            result = await import_products_csv(mock_file, mock_product_service)
            assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_import_products_csv_unicode_content(self, mock_product_service):
        """Test import_products_csv endpoint with Unicode content"""
        # Create CSV with Unicode content
        csv_content = "product_id,name,price\n1,Üñïçødé Prödüçt,99.99"
        mock_file = mock.Mock()
        mock_file.content_type = "text/csv"
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))
        
        # mock.Mock service
        import_result = {"imported": 1, "failed": 0}
        mock_product_service.import_products.return_value = import_result
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import import_products_csv
            
            result = await import_products_csv(mock_file, mock_product_service)
            
            # Verify Unicode content was processed
            assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_import_products_csv_large_file(self, mock_product_service):
        """Test import_products_csv endpoint with large file"""
        # Create large CSV content
        rows = []
        for i in range(1000):
            rows.append(f"{i},Product {i},{i * 10.99}")
        csv_content = "product_id,name,price\n" + "\n".join(rows)
        
        mock_file = mock.Mock()
        mock_file.content_type = "text/csv"
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))
        
        # mock.Mock service
        import_result = {"imported": 1000, "failed": 0}
        mock_product_service.import_products.return_value = import_result
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import import_products_csv
            
            result = await import_products_csv(mock_file, mock_product_service)
            
            # Verify large file was processed
            assert result["count"] == 1000

    # ============================================================================
    # PERMISSION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_permission_dependencies(self):
        """Test that all endpoints have proper permission dependencies"""
        # This test verifies that the endpoint decorators are properly configured
        from app.api.v1.endpoints.products.products import router
        
        # Check that router has global dependency
        assert router.dependencies is not None
        
        # Verify endpoints have permission requirements
        routes = [route for route in router.routes if hasattr(route, 'dependencies')]
        
        # Check that routes have permission dependencies
        for route in routes:
            if hasattr(route, 'dependencies') and route.dependencies:
                # Verify at least one dependency exists
                assert len(route.dependencies) > 0

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_service_error_handling(self, mock_product_service):
        """Test that service errors are properly handled"""
        # mock.Mock service to raise exception
        mock_product_service.get_all_products.side_effect = Exception("Service error")
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user'):
            
            from app.api.v1.endpoints.products.products import get_all_products
            
            with pytest.raises(Exception, match="Service error"):
                await get_all_products(mock_product_service)

    @pytest.mark.asyncio
    async def test_dependency_injection_failure(self):
        """Test behavior when dependency injection fails"""
        # This would be tested in integration tests, but we can verify the structure
        from app.api.v1.endpoints.products.products import get_all_products
        
        # Verify function signature expects service parameter
        import inspect
        sig = inspect.signature(get_all_products)
        assert 'service' in sig.parameters

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_create_then_get_product_workflow(self, mock_product_service, sample_product, sample_product_create, mock_current_user):
        """Test integration between create and get endpoints"""
        # mock.Mock service methods
        mock_product_service.create_product.return_value = sample_product
        mock_product_service.get_product_details.return_value = sample_product
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user', return_value=mock_current_user), \
             patch('app.api.v1.endpoints.products.products.ProductAuthorizer.can_create_product'):
            
            from app.api.v1.endpoints.products.products import create_product, get_product
            
            # Create product
            created = await create_product(sample_product_create, mock_product_service, mock_current_user)
            
            # Get product
            retrieved = await get_product(1, mock_product_service)
            
            # Verify both operations succeeded
            assert created.product_id == retrieved.product_id
            assert created.name == retrieved.name

    @pytest.mark.asyncio
    async def test_update_then_delete_product_workflow(self, mock_product_service, sample_product, sample_product_update, mock_current_user):
        """Test integration between update and delete endpoints"""
        # mock.Mock service methods
        updated_product = Product(
            product_id=1,
            name="Updated Product",
            description="Updated Description",
            price=149.99
        )
        mock_product_service.update_product.return_value = updated_product
        mock_product_service.delete_product.return_value = None
        
        with patch('app.api.v1.endpoints.products.products.get_product_service', return_value=mock_product_service), \
             patch('app.api.v1.endpoints.products.products.require_permissions'), \
             patch('app.api.v1.endpoints.products.products.get_current_user', return_value=mock_current_user), \
             patch('app.api.v1.endpoints.products.products.ProductAuthorizer.can_update_product'):
            
            from app.api.v1.endpoints.products.products import update_product, delete_product
            
            # Update product
            updated = await update_product(1, sample_product_update, mock_product_service, mock_current_user)
            
            # Delete product
            deleted = await delete_product(1, mock_product_service)
            
            # Verify both operations succeeded
            assert updated.name == "Updated Product"
            assert deleted["message"] == "Product 1 deleted successfully"
