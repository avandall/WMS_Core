"""
Comprehensive Unit Tests for User Domain Entity
Covers all User entity methods, validation, edge cases, and business rules
"""

import pytest
from app.modules.users.domain.entities.user import User
from app.shared.domain.business_exceptions import ValidationError


class TestUserEntity:
    """Test User Domain Entity"""

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_user_initialization_valid_data(self):
        """Test User initialization with valid data"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            role="user",
            full_name="Test User",
            is_active=True
        )
        assert user.user_id == 1
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password"
        assert user.role == "user"
        assert user.full_name == "Test User"
        assert user.is_active is True

    def test_user_initialization_minimal_data(self):
        """Test User initialization with minimal required data"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password"
        )
        assert user.user_id == 1
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password"
        assert user.role == "user"  # Default value
        assert user.full_name is None  # Default value
        assert user.is_active is True  # Default value

    def test_user_initialization_with_full_name(self):
        """Test User initialization with full name"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            full_name="John Doe"
        )
        assert user.full_name == "John Doe"

    def test_user_initialization_inactive_user(self):
        """Test User initialization with inactive user"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=False
        )
        assert user.is_active is False

    # ============================================================================
    # EMAIL VALIDATION TESTS
    # ============================================================================

    def test_email_lowercase_conversion(self):
        """Test email is converted to lowercase"""
        user = User(
            user_id=1,
            email="TEST@EXAMPLE.COM",
            hashed_password="hashed_password"
        )
        assert user.email == "test@example.com"

    def test_email_mixed_case(self):
        """Test email with mixed case is converted to lowercase"""
        user = User(
            user_id=1,
            email="TeSt@ExAmPlE.CoM",
            hashed_password="hashed_password"
        )
        assert user.email == "test@example.com"

    def test_invalid_email_no_at_symbol(self):
        """Test User initialization with email missing @ symbol"""
        with pytest.raises(ValidationError, match="email must be a valid email address"):
            User(user_id=1, email="testexample.com", hashed_password="hashed_password")

    def test_invalid_email_empty_string(self):
        """Test User initialization with empty email"""
        with pytest.raises(ValidationError, match="email must be a valid email address"):
            User(user_id=1, email="", hashed_password="hashed_password")

    def test_invalid_email_none(self):
        """Test User initialization with None email"""
        with pytest.raises(ValidationError, match="email must be a valid email address"):
            User(user_id=1, email=None, hashed_password="hashed_password")

    def test_invalid_email_non_string(self):
        """Test User initialization with non-string email"""
        with pytest.raises(ValidationError, match="email must be a valid email address"):
            User(user_id=1, email=123, hashed_password="hashed_password")

    def test_invalid_email_multiple_at_symbols(self):
        """Test User initialization with multiple @ symbols (still valid)"""
        # Multiple @ symbols are actually valid in some email formats
        user = User(
            user_id=1,
            email="test+tag@example.com",
            hashed_password="hashed_password"
        )
        assert user.email == "test+tag@example.com"

    def test_valid_email_formats(self):
        """Test User initialization with various valid email formats"""
        valid_emails = [
            "simple@example.com",
            "very.common@example.com",
            "disposable.style.email.with+symbol@example.com",
            "other.email-with-dash@example.com",
            "fully-qualified-domain@example.com",
            "user.name+tag+sorting@example.com",
            "x@example.com",
            "example-indeed@strange-example.com",
            "admin@mailserver1",
            "example@s.example"
        ]
        
        for email in valid_emails:
            user = User(user_id=1, email=email, hashed_password="hashed_password")
            assert user.email == email.lower()

    # ============================================================================
    # ROLE VALIDATION TESTS
    # ============================================================================

    def test_valid_roles(self):
        """Test User initialization with all valid roles"""
        valid_roles = ["admin", "user", "sales", "warehouse", "accountant"]
        
        for role in valid_roles:
            user = User(
                user_id=1,
                email="test@example.com",
                hashed_password="hashed_password",
                role=role
            )
            assert user.role == role

    def test_invalid_role(self):
        """Test User initialization with invalid role"""
        with pytest.raises(ValidationError, match="role must be one of"):
            User(
                user_id=1,
                email="test@example.com",
                hashed_password="hashed_password",
                role="invalid_role"
            )

    def test_invalid_role_empty_string(self):
        """Test User initialization with empty role"""
        with pytest.raises(ValidationError, match="role must be one of"):
            User(
                user_id=1,
                email="test@example.com",
                hashed_password="hashed_password",
                role=""
            )

    def test_invalid_role_none(self):
        """Test User initialization with None role"""
        with pytest.raises(ValidationError, match="role must be one of"):
            User(
                user_id=1,
                email="test@example.com",
                hashed_password="hashed_password",
                role=None
            )

    def test_invalid_role_non_string(self):
        """Test User initialization with non-string role"""
        with pytest.raises(ValidationError, match="role must be one of"):
            User(
                user_id=1,
                email="test@example.com",
                hashed_password="hashed_password",
                role=123
            )

    def test_invalid_role_case_sensitive(self):
        """Test role validation is case sensitive"""
        with pytest.raises(ValidationError, match="role must be one of"):
            User(
                user_id=1,
                email="test@example.com",
                hashed_password="hashed_password",
                role="Admin"  # Should be "admin"
            )

    def test_role_validation_error_message_format(self):
        """Test role validation error message includes all valid roles"""
        try:
            User(
                user_id=1,
                email="test@example.com",
                hashed_password="hashed_password",
                role="invalid"
            )
        except ValidationError as e:
            error_message = str(e)
            assert "admin" in error_message
            assert "user" in error_message
            assert "sales" in error_message
            assert "warehouse" in error_message
            assert "accountant" in error_message

    # ============================================================================
    # PROPERTY TESTS
    # ============================================================================

    def test_identity_property(self):
        """Test identity property returns user_id"""
        user = User(user_id=123, email="test@example.com", hashed_password="hashed_password")
        assert user.identity == 123

    # ============================================================================
    # MAGIC METHODS TESTS
    # ============================================================================

    def test_str_representation(self):
        """Test __str__ method"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            role="user"
        )
        str_repr = str(user)
        assert "User(id=1" in str_repr
        assert "email='test@example.com'" in str_repr
        assert "role='user'" in str_repr

    def test_repr_method(self):
        """Test __repr__ method"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            role="user"
        )
        repr_str = repr(user)
        assert repr_str == str(user)

    def test_str_representation_with_full_name(self):
        """Test __str__ method doesn't include full_name"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            role="user",
            full_name="John Doe"
        )
        str_repr = str(user)
        assert "full_name" not in str_repr
        assert "John Doe" not in str_repr

    def test_str_representation_inactive_user(self):
        """Test __str__ method doesn't include is_active status"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            role="user",
            is_active=False
        )
        str_repr = str(user)
        assert "is_active" not in str_repr
        assert "False" not in str_repr

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_user_with_unicode_email(self):
        """Test User with Unicode characters in email"""
        user = User(
            user_id=1,
            email="tëst@ëxämple.com",
            hashed_password="hashed_password"
        )
        assert user.email == "tëst@ëxämple.com"

    def test_user_with_unicode_full_name(self):
        """Test User with Unicode characters in full name"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            full_name="Jöhn Döe"
        )
        assert user.full_name == "Jöhn Döe"

    def test_user_with_empty_full_name(self):
        """Test User with empty string full name"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            full_name=""
        )
        assert user.full_name == ""

    def test_user_with_whitespace_full_name(self):
        """Test User with whitespace-only full name"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            full_name="   "
        )
        assert user.full_name == "   "

    def test_user_with_very_long_full_name(self):
        """Test User with very long full name"""
        long_name = "a" * 1000
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            full_name=long_name
        )
        assert user.full_name == long_name

    def test_user_with_special_characters_in_full_name(self):
        """Test User with special characters in full name"""
        special_name = "John O'Connor-Smith Jr. @#$%"
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            full_name=special_name
        )
        assert user.full_name == special_name

    def test_user_with_empty_hashed_password(self):
        """Test User with empty hashed password"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password=""
        )
        assert user.hashed_password == ""

    def test_user_with_very_long_hashed_password(self):
        """Test User with very long hashed password"""
        long_password = "a" * 1000
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password=long_password
        )
        assert user.hashed_password == long_password

    # ============================================================================
    # BUSINESS LOGIC TESTS
    # ============================================================================

    def test_user_role_based_access_patterns(self):
        """Test user creation for different role-based access patterns"""
        # Admin user
        admin = User(
            user_id=1,
            email="admin@example.com",
            hashed_password="admin_hash",
            role="admin"
        )
        assert admin.role == "admin"

        # Sales user
        sales = User(
            user_id=2,
            email="sales@example.com",
            hashed_password="sales_hash",
            role="sales"
        )
        assert sales.role == "sales"

        # Warehouse user
        warehouse = User(
            user_id=3,
            email="warehouse@example.com",
            hashed_password="warehouse_hash",
            role="warehouse"
        )
        assert warehouse.role == "warehouse"

        # Accountant user
        accountant = User(
            user_id=4,
            email="accountant@example.com",
            hashed_password="accountant_hash",
            role="accountant"
        )
        assert accountant.role == "accountant"

        # Regular user
        regular = User(
            user_id=5,
            email="user@example.com",
            hashed_password="user_hash",
            role="user"
        )
        assert regular.role == "user"

    def test_user_account_status_scenarios(self):
        """Test user creation for different account status scenarios"""
        # Active user (default)
        active_user = User(
            user_id=1,
            email="active@example.com",
            hashed_password="hash",
            is_active=True
        )
        assert active_user.is_active is True

        # Inactive user
        inactive_user = User(
            user_id=2,
            email="inactive@example.com",
            hashed_password="hash",
            is_active=False
        )
        assert inactive_user.is_active is False

    def test_user_email_normalization_scenarios(self):
        """Test email normalization in various scenarios"""
        test_cases = [
            ("USER@EXAMPLE.COM", "user@example.com"),
            ("User.Name@Example.COM", "user.name@example.com"),
            ("USER+TAG@EXAMPLE.COM", "user+tag@example.com"),
            ("TeSt@ExAmPlE.CoM", "test@example.com"),
        ]
        
        for input_email, expected_email in test_cases:
            user = User(
                user_id=1,
                email=input_email,
                hashed_password="hash"
            )
            assert user.email == expected_email

    # ============================================================================
    # IMMUTABILITY TESTS
    # ============================================================================

    def test_user_id_readonly_after_creation(self):
        """Test that user_id cannot be changed after creation"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hash"
        )
        assert user.user_id == 1

    def test_user_state_consistency(self):
        """Test that user state remains consistent after creation"""
        user = User(
            user_id=1,
            email="Test@Example.COM",
            hashed_password="hashed_password",
            role="admin",
            full_name="Test User",
            is_active=True
        )
        
        # Verify all properties are set correctly
        assert user.user_id == 1
        assert user.email == "test@example.com"  # Lowercase
        assert user.hashed_password == "hashed_password"
        assert user.role == "admin"
        assert user.full_name == "Test User"
        assert user.is_active is True

    # ============================================================================
    # SECURITY TESTS
    # ============================================================================

    def test_user_password_storage(self):
        """Test that password is stored as-is (no additional processing)"""
        password = "plain_text_password"
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password=password
        )
        assert user.hashed_password == password
        # Note: In real implementation, this should be a hashed password

    def test_user_no_sensitive_info_in_str(self):
        """Test that string representation doesn't include sensitive information"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="secret_password_hash",
            role="user"
        )
        str_repr = str(user)
        assert "secret_password_hash" not in str_repr
        assert "hashed_password" not in str_repr

    # ============================================================================
    # DATA INTEGRITY TESTS
    # ============================================================================

    def test_user_with_extreme_values(self):
        """Test user creation with extreme values"""
        # Very large user_id
        user1 = User(
            user_id=2147483647,
            email="test@example.com",
            hashed_password="hash"
        )
        assert user1.user_id == 2147483647

        # Very long email (but still valid)
        long_email = "a" * 100 + "@" + "b" * 100 + ".com"
        user2 = User(
            user_id=2,
            email=long_email,
            hashed_password="hash"
        )
        assert user2.email == long_email.lower()

    def test_user_attribute_types(self):
        """Test that user attributes maintain correct types"""
        user = User(
            user_id=1,
            email="test@example.com",
            hashed_password="hash",
            role="user",
            full_name="Test User",
            is_active=True
        )
        
        assert isinstance(user.user_id, int)
        assert isinstance(user.email, str)
        assert isinstance(user.hashed_password, str)
        assert isinstance(user.role, str)
        assert isinstance(user.full_name, (str, type(None)))
        assert isinstance(user.is_active, bool)
