"""
Comprehensive Unit Tests for ProductService & Physical Dimensions / Multi-UOM
"""

import pytest
from unittest.mock import Mock

from app.modules.products.application.services.product_service import ProductService
from app.modules.products.domain.entities.product import Product, ProductUOM
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ValidationError,
)
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo


class TestProductService:
    """Test ProductService Application Service and Domain Logic."""

    @pytest.fixture
    def mock_product_repo(self):
        """Mock product repository"""
        repo = Mock(spec=IProductRepo)
        repo._store = {}

        def mock_get(pid):
            return repo._store.get(pid)

        def mock_save(prod):
            repo._store[prod.product_id] = prod

        def mock_get_all():
            return repo._store

        def mock_delete(pid):
            if pid in repo._store:
                del repo._store[pid]

        repo.get.side_effect = mock_get
        repo.save.side_effect = mock_save
        repo.get_all.side_effect = mock_get_all
        repo.delete.side_effect = mock_delete
        return repo

    @pytest.fixture
    def mock_inventory_repo(self):
        """Mock inventory repository"""
        repo = Mock(spec=IInventoryRepo)
        repo.get_quantity = Mock(return_value=50)
        return repo

    @pytest.fixture
    def product_service(self, mock_product_repo, mock_inventory_repo):
        """ProductService instance with mocked dependencies"""
        return ProductService(mock_product_repo, mock_inventory_repo)

    @pytest.fixture
    def sample_product(self):
        """Sample product for testing"""
        return Product(
            product_id=1,
            name="Test Product",
            price=99.99,
            description="Test Description",
            length_cm=50.0,
            width_cm=40.0,
            height_cm=30.0,
            gross_weight_kg=12.5,
            net_weight_kg=10.0,
            base_uom="EACH",
            uoms=[
                ProductUOM(uom_code="CARTON", conversion_factor=24.0, to_uom_code="EACH"),
                ProductUOM(uom_code="PALLET", conversion_factor=40.0, to_uom_code="CARTON"),
            ],
        )

    # ============================================================================
    # PHYSICAL DIMENSIONS & VOLUME COMPUTATION TESTS
    # ============================================================================

    def test_volume_cbm_automatic_calculation(self):
        """Test volume_cbm calculation: (50 * 40 * 30) / 1,000,000 = 0.06 CBM"""
        product = Product(
            product_id=1,
            name="Box A",
            length_cm=50.0,
            width_cm=40.0,
            height_cm=30.0,
        )
        assert product.volume_cbm == 0.06

    def test_volume_cbm_zero_when_missing_dimension(self):
        """Test volume_cbm is 0.0 if any dimension is 0"""
        product = Product(
            product_id=1,
            name="Flat Box",
            length_cm=50.0,
            width_cm=40.0,
            height_cm=0.0,
        )
        assert product.volume_cbm == 0.0

    # ============================================================================
    # MULTI-UOM CONVERSION TESTS
    # ============================================================================

    def test_uom_conversion_direct(self, sample_product):
        """Test 1 CARTON -> EACH (1 CARTON = 24 EACH)"""
        qty_each = sample_product.convert_uom_quantity(1.0, from_uom="CARTON", to_uom="EACH")
        assert qty_each == 24.0

    def test_uom_conversion_nested(self, sample_product):
        """Test 1 PALLET -> EACH (1 PALLET = 40 CARTONS = 960 EACH)"""
        qty_each = sample_product.convert_uom_quantity(1.0, from_uom="PALLET", to_uom="EACH")
        assert qty_each == 960.0

    def test_uom_conversion_between_non_base(self, sample_product):
        """Test 2 PALLETS -> CARTONS (2 PALLETS = 80 CARTONS)"""
        qty_cartons = sample_product.convert_uom_quantity(2.0, from_uom="PALLET", to_uom="CARTON")
        assert qty_cartons == 80.0

    def test_uom_conversion_invalid_uom(self, sample_product):
        """Test exception when requesting unknown UOM"""
        with pytest.raises(ValidationError, match="Unknown UOM 'CONTAINER'"):
            sample_product.convert_uom_quantity(1.0, from_uom="CONTAINER")

    # ============================================================================
    # SERVICE CREATE & UPDATE TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_create_product_with_dimensions_and_uoms(self, product_service):
        """Test creating product with full physical properties and UOMs"""
        uoms = [
            ProductUOM(uom_code="CARTON", conversion_factor=12.0, to_uom_code="EACH"),
        ]
        prod = await product_service.create_product(
            product_id=10,
            name="Physical Item",
            price=150.0,
            length_cm=100.0,
            width_cm=50.0,
            height_cm=20.0,
            gross_weight_kg=5.0,
            net_weight_kg=4.5,
            base_uom="EACH",
            uoms=uoms,
        )

        assert prod.product_id == 10
        assert prod.volume_cbm == 0.1  # (100 * 50 * 20) / 1,000,000 = 0.1 CBM
        assert prod.gross_weight_kg == 5.0
        assert len(prod.uoms) == 1
        assert prod.uoms[0].uom_code == "CARTON"

    @pytest.mark.asyncio
    async def test_create_product_duplicate_error(self, product_service, sample_product):
        """Test error when creating product with duplicate ID"""
        product_service.product_repo.save(sample_product)
        with pytest.raises(EntityAlreadyExistsError):
            await product_service.create_product(product_id=1, name="Duplicate Product")

    @pytest.mark.asyncio
    async def test_get_product_details_success(self, product_service, sample_product):
        """Test retrieving product details"""
        product_service.product_repo.save(sample_product)
        retrieved = await product_service.get_product_details(1)
        assert retrieved.name == "Test Product"
        assert retrieved.volume_cbm == 0.06

    @pytest.mark.asyncio
    async def test_get_product_details_not_found(self, product_service):
        """Test error when product does not exist"""
        with pytest.raises(EntityNotFoundError):
            await product_service.get_product_details(999)

    @pytest.mark.asyncio
    async def test_update_product_dimensions(self, product_service, sample_product):
        """Test updating product dimensions & weight"""
        product_service.product_repo.save(sample_product)
        updated = await product_service.update_product(
            product_id=1,
            length_cm=200.0,
            width_cm=100.0,
            height_cm=50.0,
            gross_weight_kg=25.0,
        )
        assert updated.length_cm == 200.0
        assert updated.volume_cbm == 1.0  # (200 * 100 * 50) / 1,000,000 = 1.0 CBM
        assert updated.gross_weight_kg == 25.0

    @pytest.mark.asyncio
    async def test_delete_product_success(self, product_service, sample_product):
        """Test deleting product"""
        product_service.product_repo.save(sample_product)
        await product_service.delete_product(1)
        with pytest.raises(EntityNotFoundError):
            await product_service.get_product_details(1)

    @pytest.mark.asyncio
    async def test_get_product_with_inventory(self, product_service, sample_product):
        """Test get_product_with_inventory"""
        product_service.product_repo.save(sample_product)
        result = await product_service.get_product_with_inventory(1)
        assert result["product"] == sample_product
        assert result["current_inventory"] == 50

    @pytest.mark.asyncio
    async def test_import_products_success(self, product_service):
        """Test import_products with CSV rows"""
        rows = [
            {
                "product_id": "100",
                "name": "Imported Item 1",
                "price": "29.99",
                "length_cm": "10",
                "width_cm": "10",
                "height_cm": "10",
            },
            {
                "product_id": "101",
                "name": "Imported Item 2",
                "price": "49.99",
            },
        ]
        res = await product_service.import_products(rows)
        assert res["created"] == 2
        p1 = await product_service.get_product_details(100)
        assert p1.volume_cbm == 0.001
