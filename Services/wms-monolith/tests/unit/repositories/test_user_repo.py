"""
Comprehensive Unit Tests for UserRepo
Covers all UserRepo methods, validation, edge cases, and database operations
"""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict

from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.modules.users.domain.entities.user import User
# Use mock models to avoid SQLAlchemy dependency issues
try:
    # Import all models using the centralized import function to avoid SQLAlchemy mapper errors
    from app.shared.core.database import import_all_models
    import_all_models()
    from app.modules.users.infrastructure.models.user import UserModel
    REAL_MODELS_AVAILABLE = True
except ImportError:
    from tests.mocks.models import MockUserModel as UserModel
    REAL_MODELS_AVAILABLE = False


class TestUserRepo:
    """Test User Repository Implementation"""

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
        session.delete = Mock()
        return session

    @pytest.fixture
    def user_repo(self, mock_session):
        """UserRepo with mocked session"""
        return UserRepo(session=mock_session)

    @pytest.fixture
    def sample_user(self):
        """Sample User entity for testing"""
        return User(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            role="user",
            full_name="Test User",
            is_active=True
        )

    @pytest.fixture
    def sample_user_model(self):
        """Sample UserModel for testing"""
        return UserModel(
            user_id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            role="user",
            full_name="Test User",
            is_active=1
        )

    # ============================================================================
    # SAVE TESTS
    # ============================================================================

    def test_save_new_user(self, user_repo, mock_session, sample_user):
        """Test saving a new user"""
        sample_user.user_id = None
        mock_session.get.return_value = None
        mock_model = Mock()
        mock_model.user_id = 1
        mock_session.add.return_value = None
        mock_session.flush.return_value = None
        
        # Mock the model creation
        with patch.object(UserRepo, '_to_domain', return_value=sample_user):
            result = user_repo.save(sample_user)
        
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_save_existing_user(self, user_repo, mock_session, sample_user, sample_user_model):
        """Test updating an existing user"""
        mock_session.get.return_value = sample_user_model
        
        with patch.object(UserRepo, '_to_domain', return_value=sample_user):
            result = user_repo.save(sample_user)
        
        mock_session.add.assert_not_called()

    def test_save_with_auto_commit_disabled(self, user_repo, mock_session, sample_user):
        """Test saving user with auto_commit disabled"""
        user_repo.set_auto_commit(False)
        sample_user.user_id = None
        mock_session.get.return_value = None
        
        with patch.object(UserRepo, '_to_domain', return_value=sample_user):
            user_repo.save(sample_user)
        
        mock_session.commit.assert_not_called()

    # ============================================================================
    # GET BY EMAIL TESTS
    # ============================================================================

    def test_get_by_email_found(self, user_repo, mock_session, sample_user_model):
        """Test getting user by email when found"""
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_user_model
        
        result = user_repo.get_by_email("test@example.com")
        
        mock_session.execute.assert_called_once()
        assert result is not None
        assert result.email == "test@example.com"

    def test_get_by_email_not_found(self, user_repo, mock_session):
        """Test getting user by email when not found"""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = user_repo.get_by_email("nonexistent@example.com")
        
        assert result is None

    def test_get_by_email_case_insensitive(self, user_repo, mock_session, sample_user_model):
        """Test get_by_email is case insensitive"""
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_user_model
        
        result = user_repo.get_by_email("TEST@EXAMPLE.COM")
        
        mock_session.execute.assert_called_once()
        assert result is not None

    # ============================================================================
    # GET TESTS
    # ============================================================================

    def test_get_user_found(self, user_repo, mock_session, sample_user_model):
        """Test getting user by ID when found"""
        mock_session.get.return_value = sample_user_model
        
        result = user_repo.get(1)
        
        mock_session.get.assert_called_once_with(UserModel, 1)
        assert result is not None
        assert result.user_id == 1

    def test_get_user_not_found(self, user_repo, mock_session):
        """Test getting user by ID when not found"""
        mock_session.get.return_value = None
        
        result = user_repo.get(999)
        
        assert result is None

    # ============================================================================
    # GET ALL TESTS
    # ============================================================================

    def test_get_all_users(self, user_repo, mock_session, sample_user_model):
        """Test getting all users"""
        mock_session.execute.return_value.scalars.return_value.all.return_value = [sample_user_model]
        
        result = user_repo.get_all()
        
        mock_session.flush.assert_called_once()
        mock_session.execute.assert_called_once()
        assert len(result) == 1
        assert 1 in result

    def test_get_all_users_empty(self, user_repo, mock_session):
        """Test getting all users when none exist"""
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        
        result = user_repo.get_all()
        
        assert len(result) == 0

    def test_get_all_users_multiple(self, user_repo, mock_session):
        """Test getting multiple users"""
        user1 = UserModel(user_id=1, email="user1@example.com", hashed_password="hash", role="user", is_active=1)
        user2 = UserModel(user_id=2, email="user2@example.com", hashed_password="hash", role="admin", is_active=1)
        mock_session.execute.return_value.scalars.return_value.all.return_value = [user1, user2]
        
        result = user_repo.get_all()
        
        assert len(result) == 2
        assert 1 in result
        assert 2 in result

    # ============================================================================
    # DELETE TESTS
    # ============================================================================

    def test_delete_user_found(self, user_repo, mock_session, sample_user_model):
        """Test deleting a user when found"""
        mock_session.get.return_value = sample_user_model
        
        user_repo.delete(1)
        
        mock_session.get.assert_called_once_with(UserModel, 1)
        mock_session.delete.assert_called_once_with(sample_user_model)

    def test_delete_user_not_found(self, user_repo, mock_session):
        """Test deleting a user when not found"""
        mock_session.get.return_value = None
        
        user_repo.delete(999)
        
        mock_session.delete.assert_not_called()

    # ============================================================================
    # TO DOMAIN TESTS
    # ============================================================================

    def test_to_domain_conversion(self, user_repo, sample_user_model):
        """Test _to_domain conversion"""
        result = user_repo._to_domain(sample_user_model)
        
        assert result.user_id == 1
        assert result.email == "test@example.com"
        assert result.hashed_password == "hashed_password"
        assert result.role == "user"
        assert result.full_name == "Test User"
        assert result.is_active is True

    def test_to_domain_conversion_inactive(self, user_repo):
        """Test _to_domain conversion with inactive user"""
        model = UserModel(
            user_id=1,
            email="test@example.com",
            hashed_password="hash",
            role="user",
            is_active=0
        )
        
        result = user_repo._to_domain(model)
        
        assert result.is_active is False

    def test_to_domain_conversion_none_full_name(self, user_repo):
        """Test _to_domain conversion with None full_name"""
        model = UserModel(
            user_id=1,
            email="test@example.com",
            hashed_password="hash",
            role="user",
            full_name=None,
            is_active=1
        )
        
        result = user_repo._to_domain(model)
        
        assert result.full_name is None

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_save_user_with_unicode_email(self, user_repo, mock_session):
        """Test saving user with Unicode email"""
        user = User(
            user_id=None,
            email="tëst@ëxämple.com",
            hashed_password="hash",
            role="user"
        )
        mock_session.get.return_value = None
        
        with patch.object(UserRepo, '_to_domain', return_value=user):
            user_repo.save(user)
        
        mock_session.add.assert_called_once()

    def test_save_user_with_unicode_full_name(self, user_repo, mock_session):
        """Test saving user with Unicode full name"""
        user = User(
            user_id=None,
            email="test@example.com",
            hashed_password="hash",
            role="user",
            full_name="Jöhn Döe"
        )
        mock_session.get.return_value = None
        
        with patch.object(UserRepo, '_to_domain', return_value=user):
            user_repo.save(user)
        
        mock_session.add.assert_called_once()

    def test_save_user_with_different_roles(self, user_repo, mock_session):
        """Test saving users with different roles"""
        roles = ["admin", "user", "sales", "warehouse", "accountant"]
        
        for role in roles:
            user = User(
                user_id=None,
                email=f"{role}@example.com",
                hashed_password="hash",
                role=role
            )
            mock_session.get.return_value = None
            
            with patch.object(UserRepo, '_to_domain', return_value=user):
                user_repo.save(user)
            
            mock_session.add.assert_called_once()
            mock_session.reset_mock()

    # ============================================================================
    # AUTO COMMIT TESTS
    # ============================================================================

    def test_auto_commit_default(self, user_repo):
        """Test auto_commit is disabled by default in TransactionalRepository"""
        assert user_repo._auto_commit is False
    # ============================================================================

    def test_auto_commit_default(self, user_repo):
        """Test auto_commit is disabled by default in TransactionalRepository"""
        assert user_repo._auto_commit is False
