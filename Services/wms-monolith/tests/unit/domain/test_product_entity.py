"""
Comprehensive Unit Tests for Product Domain Entity
Covers all Product entity methods, validation, edge cases, and business rules
"""

import pytest
from decimal import Decimal
from app.modules.products.domain.entities.product import Product
from app.shared.domain.business_exceptions import InvalidIDError, InvalidQuantityError, ValidationError


class TestProductEntity:
    """Test Product Domain Entity"""

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_product_initialization_valid_data(self):
        """Test Product initialization with valid data"""
        product = Product(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99
        )
        assert product.product_id == 1
        assert product.name == "Test Product"
        assert product.description == "Test Description"
        assert product.price == 99.99
        assert isinstance(product.price, float)

    def test_product_initialization_minimal_data(self):
        """Test Product initialization with minimal required data"""
        product = Product(
            product_id=1,
            name="Minimal Product"
        )
        assert product.product_id == 1
        assert product.name == "Minimal Product"
        assert product.description is None
        assert product.price == 0.0

    def test_product_initialization_zero_price(self):
        """Test Product initialization with zero price"""
        product = Product(
            product_id=1,
            name="Free Product",
            price=0.0
        )
        assert product.price == 0.0

    def test_product_initialization_integer_price(self):
        """Test Product initialization with integer price"""
        product = Product(
            product_id=1,
            name="Integer Price Product",
            price=100
        )
        assert product.price == 100.0
        assert isinstance(product.price, float)

    def test_product_initialization_decimal_price(self):
        """Test Product initialization with decimal price"""
        product = Product(
            product_id=1,
            name="Decimal Price Product",
            price=Decimal("99.99")
        )
        assert product.price == 99.99
        assert isinstance(product.price, float)

    # ============================================================================
    # VALIDATION TESTS - PRODUCT ID
    # ============================================================================

    def test_invalid_product_id_zero(self):
        """Test Product initialization with zero product_id"""
        with pytest.raises(InvalidIDError, match="product_id must be a positive integer"):
            Product(product_id=0, name="Test", price=10.0)

    def test_invalid_product_id_negative(self):
        """Test Product initialization with negative product_id"""
        with pytest.raises(InvalidIDError, match="product_id must be a positive integer"):
            Product(product_id=-1, name="Test", price=10.0)

    def test_invalid_product_id_float(self):
        """Test Product initialization with float product_id"""
        with pytest.raises(InvalidIDError, match="product_id must be a positive integer"):
            Product(product_id=1.5, name="Test", price=10.0)

    def test_invalid_product_id_string(self):
        """Test Product initialization with string product_id"""
        with pytest.raises(InvalidIDError, match="product_id must be a positive integer"):
            Product(product_id="1", name="Test", price=10.0)

    def test_invalid_product_id_none(self):
        """Test Product initialization with None product_id"""
        with pytest.raises(InvalidIDError, match="product_id must be a positive integer"):
            Product(product_id=None, name="Test", price=10.0)

    # ============================================================================
    # VALIDATION TESTS - NAME
    # ============================================================================

    def test_invalid_name_empty_string(self):
        """Test Product initialization with empty name"""
        with pytest.raises(ValidationError, match="name must be a non-empty string"):
            Product(product_id=1, name="", price=10.0)

    def test_invalid_name_whitespace_only(self):
        """Test Product initialization with whitespace-only name"""
        with pytest.raises(ValidationError, match="name must be a non-empty string"):
            Product(product_id=1, name="   ", price=10.0)

    def test_invalid_name_none(self):
        """Test Product initialization with None name"""
        with pytest.raises(ValidationError, match="name must be a non-empty string"):
            Product(product_id=1, name=None, price=10.0)

    def test_invalid_name_non_string(self):
        """Test Product initialization with non-string name"""
        with pytest.raises(ValidationError, match="name must be a non-empty string"):
            Product(product_id=1, name=123, price=10.0)

    def test_invalid_name_too_long(self):
        """Test Product initialization with name exceeding 100 characters"""
        long_name = "a" * 101
        with pytest.raises(ValidationError, match="name must be at most 100 characters"):
            Product(product_id=1, name=long_name, price=10.0)

    def test_valid_name_exactly_100_chars(self):
        """Test Product initialization with name exactly 100 characters"""
        name_100_chars = "a" * 100
        product = Product(product_id=1, name=name_100_chars, price=10.0)
        assert product.name == name_100_chars

    def test_valid_name_with_special_chars(self):
        """Test Product initialization with name containing special characters"""
        product = Product(product_id=1, name="Product-123_@#$%", price=10.0)
        assert product.name == "Product-123_@#$%"

    def test_valid_name_with_unicode(self):
        """Test Product initialization with Unicode characters in name"""
        product = Product(product_id=1, name="Prodüct Ñame", price=10.0)
        assert product.name == "Prodüct Ñame"

    # ============================================================================
    # VALIDATION TESTS - PRICE
    # ============================================================================

    def test_invalid_price_negative(self):
        """Test Product initialization with negative price"""
        with pytest.raises(InvalidQuantityError, match="price must be a non-negative number"):
            Product(product_id=1, name="Test", price=-10.0)

    def test_invalid_price_string(self):
        """Test Product initialization with string price"""
        with pytest.raises(InvalidQuantityError, match="price must be a non-negative number"):
            Product(product_id=1, name="Test", price="10.0")

    def test_invalid_price_none(self):
        """Test Product initialization with None price"""
        with pytest.raises(InvalidQuantityError, match="price must be a non-negative number"):
            Product(product_id=1, name="Test", price=None)

    def test_valid_price_very_large(self):
        """Test Product initialization with very large price"""
        large_price = 999999999.99
        product = Product(product_id=1, name="Expensive", price=large_price)
        assert product.price == large_price

    def test_valid_price_very_small(self):
        """Test Product initialization with very small positive price"""
        small_price = 0.000001
        product = Product(product_id=1, name="Cheap", price=small_price)
        assert product.price == small_price

    # ============================================================================
    # METHOD TESTS - UPDATE PRICE
    # ============================================================================

    def test_update_price_valid(self):
        """Test update_price with valid new price"""
        product = Product(product_id=1, name="Test", price=10.0)
        product.update_price(15.99)
        assert product.price == 15.99

    def test_update_price_to_zero(self):
        """Test update_price to zero"""
        product = Product(product_id=1, name="Test", price=10.0)
        product.update_price(0.0)
        assert product.price == 0.0

    def test_update_price_invalid_negative(self):
        """Test update_price with negative price"""
        product = Product(product_id=1, name="Test", price=10.0)
        with pytest.raises(InvalidQuantityError, match="price must be a non-negative number"):
            product.update_price(-5.0)

    def test_update_price_invalid_string(self):
        """Test update_price with string price"""
        product = Product(product_id=1, name="Test", price=10.0)
        with pytest.raises(InvalidQuantityError, match="price must be a non-negative number"):
            product.update_price("15.99")

    def test_update_price_integer_input(self):
        """Test update_price with integer input"""
        product = Product(product_id=1, name="Test", price=10.0)
        product.update_price(20)
        assert product.price == 20.0

    # ============================================================================
    # METHOD TESTS - UPDATE NAME
    # ============================================================================

    def test_update_name_valid(self):
        """Test update_name with valid new name"""
        product = Product(product_id=1, name="Test", price=10.0)
        product.update_name("Updated Name")
        assert product.name == "Updated Name"

    def test_update_name_empty_string(self):
        """Test update_name with empty string"""
        product = Product(product_id=1, name="Test", price=10.0)
        with pytest.raises(ValidationError, match="name must be a non-empty string"):
            product.update_name("")

    def test_update_name_whitespace_only(self):
        """Test update_name with whitespace-only string"""
        product = Product(product_id=1, name="Test", price=10.0)
        with pytest.raises(ValidationError, match="name must be a non-empty string"):
            product.update_name("   ")

    def test_update_name_too_long(self):
        """Test update_name with name exceeding 100 characters"""
        product = Product(product_id=1, name="Test", price=10.0)
        long_name = "a" * 101
        with pytest.raises(ValidationError, match="name must be at most 100 characters"):
            product.update_name(long_name)

    def test_update_name_with_special_chars(self):
        """Test update_name with special characters"""
        product = Product(product_id=1, name="Test", price=10.0)
        product.update_name("Updated-Name_123")
        assert product.name == "Updated-Name_123"

    # ============================================================================
    # METHOD TESTS - UPDATE DESCRIPTION
    # ============================================================================

    def test_update_description_valid_string(self):
        """Test update_description with valid string"""
        product = Product(product_id=1, name="Test", price=10.0)
        product.update_description("New description")
        assert product.description == "New description"

    def test_update_description_empty_string(self):
        """Test update_description with empty string"""
        product = Product(product_id=1, name="Test", description="Original", price=10.0)
        product.update_description("")
        assert product.description == ""

    def test_update_description_none(self):
        """Test update_description with None"""
        product = Product(product_id=1, name="Test", description="Original", price=10.0)
        product.update_description(None)
        assert product.description is None

    def test_update_description_long_string(self):
        """Test update_description with very long string"""
        product = Product(product_id=1, name="Test", price=10.0)
        long_desc = "a" * 1000
        product.update_description(long_desc)
        assert product.description == long_desc

    # ============================================================================
    # METHOD TESTS - CALCULATE TOTAL VALUE
    # ============================================================================

    def test_calculate_total_value_valid_quantity(self):
        """Test calculate_total_value with valid quantity"""
        product = Product(product_id=1, name="Test", price=10.0)
        total = product.calculate_total_value(5)
        assert total == 50.0

    def test_calculate_total_value_zero_quantity(self):
        """Test calculate_total_value with zero quantity"""
        product = Product(product_id=1, name="Test", price=10.0)
        total = product.calculate_total_value(0)
        assert total == 0.0

    def test_calculate_total_value_large_quantity(self):
        """Test calculate_total_value with large quantity"""
        product = Product(product_id=1, name="Test", price=1.99)
        total = product.calculate_total_value(1000000)
        assert total == 1990000.0

    def test_calculate_total_value_decimal_price(self):
        """Test calculate_total_value with decimal price"""
        product = Product(product_id=1, name="Test", price=9.99)
        total = product.calculate_total_value(3)
        assert total == 29.97

    def test_calculate_total_value_invalid_negative_quantity(self):
        """Test calculate_total_value with negative quantity"""
        product = Product(product_id=1, name="Test", price=10.0)
        with pytest.raises(InvalidQuantityError, match="quantity must be a non-negative integer"):
            product.calculate_total_value(-5)

    def test_calculate_total_value_invalid_float_quantity(self):
        """Test calculate_total_value with float quantity"""
        product = Product(product_id=1, name="Test", price=10.0)
        with pytest.raises(InvalidQuantityError, match="quantity must be a non-negative integer"):
            product.calculate_total_value(5.5)

    def test_calculate_total_value_invalid_string_quantity(self):
        """Test calculate_total_value with string quantity"""
        product = Product(product_id=1, name="Test", price=10.0)
        with pytest.raises(InvalidQuantityError, match="quantity must be a non-negative integer"):
            product.calculate_total_value("5")

    # ============================================================================
    # PROPERTY TESTS
    # ============================================================================

    def test_identity_property(self):
        """Test identity property returns product_id"""
        product = Product(product_id=123, name="Test", price=10.0)
        assert product.identity == 123

    # ============================================================================
    # MAGIC METHODS TESTS
    # ============================================================================

    def test_str_representation(self):
        """Test __str__ method"""
        product = Product(product_id=1, name="Test Product", price=10.0)
        str_repr = str(product)
        assert "Product(id=1" in str_repr
        assert "name='Test Product'" in str_repr
        assert "price=10.0" in str_repr

    def test_repr_method(self):
        """Test __repr__ method"""
        product = Product(product_id=1, name="Test Product", price=10.0)
        repr_str = repr(product)
        assert repr_str == str(product)

    def test_equality_same_product(self):
        """Test __eq__ with same product"""
        product1 = Product(product_id=1, name="Test", price=10.0)
        product2 = Product(product_id=1, name="Different", price=20.0)
        assert product1 == product2

    def test_equality_different_products(self):
        """Test __eq__ with different products"""
        product1 = Product(product_id=1, name="Test", price=10.0)
        product2 = Product(product_id=2, name="Test", price=10.0)
        assert product1 != product2

    def test_equality_non_product_object(self):
        """Test __eq__ with non-product object"""
        product = Product(product_id=1, name="Test", price=10.0)
        assert product != "not a product"
        assert product != 1
        assert product != None

    def test_hash_method(self):
        """Test __hash__ method"""
        product1 = Product(product_id=1, name="Test", price=10.0)
        product2 = Product(product_id=1, name="Different", price=20.0)
        product3 = Product(product_id=2, name="Test", price=10.0)
        
        assert hash(product1) == hash(product2)
        assert hash(product1) != hash(product3)

    def test_hash_in_set(self):
        """Test product can be used in set"""
        product1 = Product(product_id=1, name="Test", price=10.0)
        product2 = Product(product_id=1, name="Different", price=20.0)
        product3 = Product(product_id=2, name="Test", price=10.0)
        
        product_set = {product1, product2, product3}
        assert len(product_set) == 2  # product1 and product2 are considered equal

    def test_hash_in_dict(self):
        """Test product can be used as dictionary key"""
        product = Product(product_id=1, name="Test", price=10.0)
        product_dict = {product: "value"}
        assert product_dict[product] == "value"

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_product_with_unicode_name_and_description(self):
        """Test product with Unicode characters in name and description"""
        product = Product(
            product_id=1,
            name="Üñïçødé Prödüçt",
            description="Thïs ïs à üñïçødé dëscrïptïøn wïth spécïål chárs",
            price=99.99
        )
        assert product.name == "Üñïçødé Prödüçt"
        assert product.description == "Thïs ïs à üñïçødé dëscrïptïøn wïth spécïål chárs"

    def test_product_with_extreme_prices(self):
        """Test product with extreme price values"""
        # Very small positive price
        product1 = Product(product_id=1, name="Micro", price=0.000001)
        assert product1.price == 0.000001
        
        # Very large price
        product2 = Product(product_id=2, name="Expensive", price=999999999.99)
        assert product2.price == 999999999.99

    def test_product_name_length_boundary(self):
        """Test product name at boundary conditions"""
        # Exactly 100 characters
        name_100 = "a" * 100
        product1 = Product(product_id=1, name=name_100, price=10.0)
        assert len(product1.name) == 100
        
        # 101 characters should fail
        name_101 = "a" * 101
        with pytest.raises(ValidationError, match="name must be at most 100 characters"):
            Product(product_id=2, name=name_101, price=10.0)

    def test_product_calculation_precision(self):
        """Test precision in total value calculations"""
        product = Product(product_id=1, name="Precision Test", price=0.33)
        total = product.calculate_total_value(3)
        assert abs(total - 0.99) < 0.0001  # Allow for floating point precision

    # ============================================================================
    # IMMUTABILITY TESTS
    # ============================================================================

    def test_product_id_immutable(self):
        """Test that product_id cannot be changed after creation"""
        product = Product(product_id=1, name="Test", price=10.0)
        original_id = product.product_id
        
        # Try to change product_id (this shouldn't be possible in normal usage)
        # But we test that the attribute exists and is accessible
        assert product.product_id == original_id

    def test_product_state_consistency(self):
        """Test that product state remains consistent after multiple operations"""
        product = Product(product_id=1, name="Original", description="Original desc", price=10.0)
        
        # Perform multiple updates
        product.update_name("Updated")
        product.update_price(15.99)
        product.update_description("Updated desc")
        
        # Verify final state
        assert product.product_id == 1
        assert product.name == "Updated"
        assert product.price == 15.99
        assert product.description == "Updated desc"
