"""
Unit tests for UnitOfWork and RepositoryContainer implementation.
Tests cover lazy loading, read-only mode, audit event collection, and edge cases.
"""

import pytest
from sqlalchemy.orm import Session
from unittest.mock import Mock, MagicMock, patch

from app.shared.application.unit_of_work.unit_of_work import UnitOfWork, RepositoryContainer


# Mock implementation to avoid FastAPI dependency
class MockRepositoryContainerImpl(RepositoryContainer):
    """Mock implementation of RepositoryContainer for testing."""

    def __init__(self, session: Session):
        self._session = session
        self._repos = {}

    def __getattr__(self, name: str):
        """Dynamic lazy loading of repositories."""
        if name not in self._repos:
            repo = self._create_repository(name)
            if repo is None:
                raise AttributeError(f"Repository '{name}' not found")
            self._repos[name] = repo
        return self._repos[name]

    def _create_repository(self, name: str):
        """Create mock repository instance on-demand."""
        # Only return mock for known repo names
        known_repos = [
            "product_repo", "inventory_repo", "warehouse_repo",
            "document_repo", "customer_repo", "position_repo",
            "audit_event_repo", "user_repo"
        ]
        if name in known_repos:
            return Mock()
        return None


class TestRepositoryContainer:
    """Test RepositoryContainerImpl lazy loading and dynamic access."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        return Mock(spec=Session)

    @pytest.fixture
    def container(self, mock_session):
        """Create a RepositoryContainerImpl instance."""
        return MockRepositoryContainerImpl(mock_session)

    def test_init_creates_empty_repos_dict(self, container):
        """Test that initialization creates empty _repos dict."""
        assert hasattr(container, "_repos")
        assert container._repos == {}
        assert hasattr(container, "_session")

    def test_getattr_creates_product_repo_on_demand(self, container, mock_session):
        """Test that product_repo is created lazily when accessed."""
        # Before access, repo should not exist
        assert "product_repo" not in container._repos

        # Access the repo
        repo = container.product_repo

        # After access, repo should be cached
        assert "product_repo" in container._repos
        assert repo is container._repos["product_repo"]

        # Second access should return same instance
        repo2 = container.product_repo
        assert repo is repo2

    def test_getattr_creates_inventory_repo_on_demand(self, container):
        """Test that inventory_repo is created lazily when accessed."""
        assert "inventory_repo" not in container._repos

        repo = container.inventory_repo

        assert "inventory_repo" in container._repos
        assert repo is container._repos["inventory_repo"]

    def test_getattr_creates_warehouse_repo_on_demand(self, container):
        """Test that warehouse_repo is created lazily when accessed."""
        assert "warehouse_repo" not in container._repos

        repo = container.warehouse_repo

        assert "warehouse_repo" in container._repos
        assert repo is container._repos["warehouse_repo"]

    def test_getattr_creates_document_repo_on_demand(self, container):
        """Test that document_repo is created lazily when accessed."""
        assert "document_repo" not in container._repos

        repo = container.document_repo

        assert "document_repo" in container._repos
        assert repo is container._repos["document_repo"]

    def test_getattr_creates_customer_repo_on_demand(self, container):
        """Test that customer_repo is created lazily when accessed."""
        assert "customer_repo" not in container._repos

        repo = container.customer_repo

        assert "customer_repo" in container._repos
        assert repo is container._repos["customer_repo"]

    def test_getattr_creates_position_repo_on_demand(self, container):
        """Test that position_repo is created lazily when accessed."""
        assert "position_repo" not in container._repos

        repo = container.position_repo

        assert "position_repo" in container._repos
        assert repo is container._repos["position_repo"]

    def test_getattr_creates_audit_event_repo_on_demand(self, container):
        """Test that audit_event_repo is created lazily when accessed."""
        assert "audit_event_repo" not in container._repos

        repo = container.audit_event_repo

        assert "audit_event_repo" in container._repos
        assert repo is container._repos["audit_event_repo"]

    def test_getattr_creates_user_repo_on_demand(self, container):
        """Test that user_repo is created lazily when accessed."""
        assert "user_repo" not in container._repos

        repo = container.user_repo

        assert "user_repo" in container._repos
        assert repo is container._repos["user_repo"]

    def test_getattr_raises_attribute_error_for_unknown_repo(self, container):
        """Test that accessing unknown repository raises AttributeError."""
        with pytest.raises(AttributeError, match="Repository 'unknown_repo' not found"):
            _ = container.unknown_repo

    def test_multiple_repos_cached_independently(self, container):
        """Test that multiple repositories are cached independently."""
        # Access multiple repos
        product_repo = container.product_repo
        inventory_repo = container.inventory_repo
        warehouse_repo = container.warehouse_repo

        # All should be cached
        assert "product_repo" in container._repos
        assert "inventory_repo" in container._repos
        assert "warehouse_repo" in container._repos

        # All should be different instances
        assert product_repo is not inventory_repo
        assert inventory_repo is not warehouse_repo
        assert product_repo is not warehouse_repo


class TestUnitOfWork:
    """Test UnitOfWork transaction management and features."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        session = Mock(spec=Session)
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def mock_container(self):
        """Create a mock RepositoryContainer."""
        return Mock(spec=RepositoryContainer)

    @pytest.fixture
    def uow(self, mock_session, mock_container):
        """Create a UnitOfWork instance."""
        return UnitOfWork(mock_session, mock_container)

    def test_init_sets_attributes(self, uow, mock_session, mock_container):
        """Test that initialization sets all attributes correctly."""
        assert uow.session is mock_session
        assert uow._repositories is mock_container
        assert uow._committed is False
        assert uow._read_only is False
        assert uow._events == []

    def test_init_with_read_only_flag(self, mock_session, mock_container):
        """Test that read_only flag is set correctly."""
        uow = UnitOfWork(mock_session, mock_container, read_only=True)
        assert uow._read_only is True

    def test_repos_property_returns_container(self, uow, mock_container):
        """Test that repos property returns the repository container."""
        assert uow.repos is mock_container

    def test_context_manager_returns_uow(self, uow):
        """Test that context manager __enter__ returns self."""
        with uow as returned_uow:
            assert returned_uow is uow

    def test_commit_on_successful_exit(self, uow, mock_session):
        """Test that commit is called on successful exit."""
        with uow:
            pass

        mock_session.commit.assert_called_once()
        assert uow._committed is True

    def test_rollback_on_exception(self, uow, mock_session):
        """Test that rollback is called on exception."""
        with pytest.raises(ValueError):
            with uow:
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        assert uow._committed is False

    def test_session_close_on_exit(self, uow, mock_session):
        """Test that session is closed on exit."""
        with uow:
            pass

        mock_session.close.assert_called_once()

    def test_session_close_on_exception_exit(self, uow, mock_session):
        """Test that session is closed even on exception."""
        with pytest.raises(ValueError):
            with uow:
                raise ValueError("Test error")

        mock_session.close.assert_called_once()

    def test_commit_method(self, uow, mock_session):
        """Test explicit commit method."""
        uow.commit()

        mock_session.commit.assert_called_once()
        assert uow._committed is True

    def test_commit_on_exception_rolls_back(self, uow, mock_session):
        """Test that commit on exception rolls back and re-raises."""
        mock_session.commit.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            uow.commit()

        mock_session.rollback.assert_called_once()
        assert uow._committed is False

    def test_rollback_method(self, uow, mock_session):
        """Test explicit rollback method."""
        uow.rollback()

        mock_session.rollback.assert_called_once()

    def test_read_only_mode_no_commit_on_exit(self, mock_session, mock_container):
        """Test that read_only mode does not commit on exit."""
        uow = UnitOfWork(mock_session, mock_container, read_only=True)

        with uow:
            pass

        mock_session.commit.assert_not_called()
        assert uow._committed is False

    def test_read_only_mode_rollback_on_exception(self, mock_session, mock_container):
        """Test that read_only mode still rolls back on exception."""
        uow = UnitOfWork(mock_session, mock_container, read_only=True)

        with pytest.raises(ValueError):
            with uow:
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()

    def test_add_event_collects_events(self, uow):
        """Test that add_event collects events."""
        event1 = {"action": "create", "entity": "product"}
        event2 = {"action": "update", "entity": "inventory"}

        uow.add_event(event1)
        uow.add_event(event2)

        assert len(uow._events) == 2
        assert event1 in uow._events
        assert event2 in uow._events

    def test_add_event_appends_to_list(self, uow):
        """Test that add_event appends events in order."""
        uow.add_event({"id": 1})
        uow.add_event({"id": 2})
        uow.add_event({"id": 3})

        assert uow._events == [{"id": 1}, {"id": 2}, {"id": 3}]

    def test_manual_commit_prevents_auto_commit(self, uow, mock_session):
        """Test that manual commit prevents auto-commit on exit."""
        with uow:
            uow.commit()

        mock_session.commit.assert_called_once()  # Only from manual commit
        assert uow._committed is True


class TestUnitOfWorkIntegration:
    """Integration tests for UnitOfWork with RepositoryContainer."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        session = Mock(spec=Session)
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session

    def test_uow_with_container_lazy_loading(self, mock_session):
        """Test that UnitOfWork works with lazy-loaded container."""
        container = MockRepositoryContainerImpl(mock_session)
        uow = UnitOfWork(mock_session, container)

        # Before access, no repos should be created
        assert len(container._repos) == 0

        # Access repos through uow
        with uow:
            _ = uow.repos.product_repo
            _ = uow.repos.inventory_repo

        # After access, repos should be cached
        assert len(container._repos) == 2
        assert "product_repo" in container._repos
        assert "inventory_repo" in container._repos

    def test_uow_read_only_with_container(self, mock_session):
        """Test read-only mode with container."""
        container = MockRepositoryContainerImpl(mock_session)
        uow = UnitOfWork(mock_session, container, read_only=True)

        with uow:
            _ = uow.repos.product_repo

        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_uow_events_with_container(self, mock_session):
        """Test event collection with container."""
        container = MockRepositoryContainerImpl(mock_session)
        uow = UnitOfWork(mock_session, container)

        with uow:
            uow.add_event({"action": "test"})
            _ = uow.repos.product_repo

        assert len(uow._events) == 1
        assert uow._events[0] == {"action": "test"}
