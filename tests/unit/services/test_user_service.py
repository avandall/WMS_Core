"""
Comprehensive Unit Tests for UserService
Covers all UserService methods, validation, edge cases, and business logic
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from app.modules.users.application.services.user_service import UserService
from app.modules.users.domain.entities.user import User
from app.shared.domain.business_exceptions import EntityNotFoundError, ValidationError
from app.modules.users.domain.interfaces.user_repo import IUserRepo


class TestUserService:
    """Test UserService Application Service"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_user_repo(self):
        """Mock user repository"""
        return Mock(spec=IUserRepo)

    @pytest.fixture
    def user_service(self, mock_user_repo):
        """UserService instance with mocked dependencies"""
        return UserService(mock_user_repo)

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing"""
        return User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            role="user",
            full_name="Test User",
            is_active=True
        )

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_user_service_initialization(self, mock_user_repo):
        """Test UserService initialization"""
        service = UserService(mock_user_repo)
        assert service.user_repo == mock_user_repo

    # ============================================================================
    # CREATE USER TESTS
    # ============================================================================

    @patch('app.modules.users.application.services.user_service.hash_password')
    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_hash, user_service, mock_user_repo, sample_user):
        """Test create user with valid data"""
        mock_hash.return_value = "hashed_password"
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.return_value = sample_user

        result = await user_service.create_user(
            email="test@example.com",
            password="password123",
            role="user",
            full_name="Test User"
        )

        mock_user_repo.get_by_email.assert_called_once_with("test@example.com")
        mock_hash.assert_called_once_with("password123")
        mock_user_repo.save.assert_called_once()
        assert result == sample_user

    @patch('app.modules.users.application.services.user_service.hash_password')
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, mock_hash, user_service, mock_user_repo, sample_user):
        """Test create user with duplicate email"""
        mock_hash.return_value = "hashed_password"
        mock_user_repo.get_by_email.return_value = sample_user

        with pytest.raises(ValidationError, match="User already exists"):
            await user_service.create_user(
                email="test@example.com",
                password="password123"
            )

        mock_user_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_user_default_role(self, user_service, mock_user_repo):
        """Test create user with default role"""
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.return_value = Mock()

        with patch('app.modules.users.application.services.user_service.hash_password'):
            await user_service.create_user(
                email="test@example.com",
                password="password123"
            )

            # Check that the saved user has default role
            saved_user = mock_user_repo.save.call_args[0][0]
            assert saved_user.role == "user"

    # ============================================================================
    # AUTHENTICATE TESTS
    # ============================================================================

    @patch('app.modules.users.application.services.user_service.create_token')
    @patch('app.modules.users.application.services.user_service.verify_password')
    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_verify, mock_create, user_service, mock_user_repo, sample_user):
        """Test authenticate with valid credentials"""
        mock_user_repo.get_by_email.return_value = sample_user
        mock_verify.return_value = True
        mock_create.side_effect = ["access_token", "refresh_token"]

        result = await user_service.authenticate("test@example.com", "password123")

        assert result["access_token"] == "access_token"
        assert result["refresh_token"] == "refresh_token"
        assert result["token_type"] == "bearer"
        assert result["user"] == sample_user

    @pytest.mark.asyncio
    async def test_authenticate_invalid_email(self, user_service, mock_user_repo):
        """Test authenticate with invalid email"""
        mock_user_repo.get_by_email.return_value = None

        with pytest.raises(ValidationError, match="Invalid credentials"):
            await user_service.authenticate("wrong@example.com", "password123")

    @patch('app.modules.users.application.services.user_service.verify_password')
    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, mock_verify, user_service, mock_user_repo, sample_user):
        """Test authenticate with invalid password"""
        mock_user_repo.get_by_email.return_value = sample_user
        mock_verify.return_value = False

        with pytest.raises(ValidationError, match="Invalid credentials"):
            await user_service.authenticate("test@example.com", "wrong_password")

    @patch('app.modules.users.application.services.user_service.verify_password')
    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, mock_verify, user_service, mock_user_repo):
        """Test authenticate with inactive user"""
        inactive_user = Mock()
        inactive_user.is_active = False
        mock_user_repo.get_by_email.return_value = inactive_user
        mock_verify.return_value = True

        with pytest.raises(ValidationError, match="User is inactive"):
            await user_service.authenticate("test@example.com", "password123")

    # ============================================================================
    # GET USER TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_user_found(self, user_service, mock_user_repo, sample_user):
        """Test get user when found"""
        mock_user_repo.get.return_value = sample_user

        result = await user_service.get_user(1)

        assert result == sample_user
        mock_user_repo.get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, user_service, mock_user_repo):
        """Test get user when not found"""
        mock_user_repo.get.return_value = None

        with pytest.raises(EntityNotFoundError, match="User not found"):
            await user_service.get_user(999)

    # ============================================================================
    # LIST USERS TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_list_users(self, user_service, mock_user_repo, sample_user):
        """Test list users"""
        mock_user_repo.get_all.return_value = {1: sample_user}

        result = await user_service.list_users()

        assert result == {1: sample_user}
        mock_user_repo.get_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_users_empty(self, user_service, mock_user_repo):
        """Test list users with no users"""
        mock_user_repo.get_all.return_value = {}

        result = await user_service.list_users()

        assert result == {}

    # ============================================================================
    # UPDATE ROLE TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_update_role(self, user_service, mock_user_repo, sample_user):
        """Test update user role"""
        mock_user_repo.get.return_value = sample_user
        mock_user_repo.save.return_value = sample_user

        result = await user_service.update_role(1, "admin")

        mock_user_repo.get.assert_called_once_with(1)
        mock_user_repo.save.assert_called_once()
        saved_user = mock_user_repo.save.call_args[0][0]
        assert saved_user.role == "admin"

    @pytest.mark.asyncio
    async def test_update_role_user_not_found(self, user_service, mock_user_repo):
        """Test update role when user not found"""
        mock_user_repo.get.return_value = None

        with pytest.raises(EntityNotFoundError, match="User not found"):
            await user_service.update_role(999, "admin")

    # ============================================================================
    # CHANGE PASSWORD TESTS
    # ============================================================================

    @pytest.mark.asyncio
    @patch('app.modules.users.application.services.user_service.verify_password')
    @patch('app.modules.users.application.services.user_service.hash_password')
    async def test_change_password_success(self, mock_hash, mock_verify, user_service, mock_user_repo, sample_user):
        """Test change password with valid data"""
        mock_user_repo.get.return_value = sample_user
        mock_verify.return_value = True
        mock_hash.return_value = "new_hashed_password"
        mock_user_repo.save.return_value = sample_user

        result = await user_service.change_password(1, "old_password", "new_password123")

        mock_verify.assert_called_once_with("old_password", sample_user.hashed_password)
        mock_hash.assert_called_once_with("new_password123")
        mock_user_repo.save.assert_called_once()
        assert result == sample_user

    @pytest.mark.asyncio
    @patch('app.modules.users.application.services.user_service.verify_password')
    async def test_change_password_invalid_old_password(self, mock_verify, user_service, mock_user_repo, sample_user):
        """Test change password with invalid old password"""
        mock_user_repo.get.return_value = sample_user
        mock_verify.return_value = False

        with pytest.raises(ValidationError, match="Current password is incorrect"):
            await user_service.change_password(1, "wrong_old_password", "new_password123")

        mock_user_repo.save.assert_not_called()

    @pytest.mark.asyncio
    @patch('app.modules.users.application.services.user_service.verify_password')
    async def test_change_password_short_new_password(self, mock_verify, user_service, mock_user_repo, sample_user):
        """Test change password with short new password"""
        mock_user_repo.get.return_value = sample_user
        mock_verify.return_value = True

        with pytest.raises(ValidationError, match="New password must be at least 6 characters"):
            await user_service.change_password(1, "old_password", "short")

        mock_user_repo.save.assert_not_called()

    # ============================================================================
    # DELETE USER TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_delete_user(self, user_service, mock_user_repo, sample_user):
        """Test delete user"""
        mock_user_repo.get.return_value = sample_user

        await user_service.delete_user(1)

        mock_user_repo.get.assert_called_once_with(1)
        mock_user_repo.delete.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_service, mock_user_repo):
        """Test delete user when not found"""
        mock_user_repo.get.return_value = None

        with pytest.raises(EntityNotFoundError, match="User not found"):
            await user_service.delete_user(999)

        mock_user_repo.delete.assert_not_called()
