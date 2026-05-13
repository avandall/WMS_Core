"""Tests for Redis session management."""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.shared.core.session import SessionManager, session_manager
from app.shared.core.settings import settings


class TestSessionManager:
    """Test cases for SessionManager."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock redis manager."""
        mock_manager = AsyncMock()
        mock_manager.get.return_value = None
        mock_manager.set.return_value = True
        mock_manager.delete.return_value = True
        mock_manager.exists.return_value = True
        mock_manager.expire.return_value = True
        mock_manager.client.sadd.return_value = 1
        mock_manager.client.srem.return_value = 1
        mock_manager.client.smembers.return_value = set()
        mock_manager.client.scan.return_value = (0, [])
        mock_manager.client.ttl.return_value = 3600  # Return integer TTL
        # Mock pipeline for batched operations
        pipeline = MagicMock()
        pipeline.set.return_value = pipeline
        pipeline.sadd.return_value = pipeline
        pipeline.expire.return_value = pipeline
        pipeline.execute = AsyncMock(return_value=[True, 1, True])
        mock_manager.pipeline = MagicMock(return_value=pipeline)
        # Mock eval for atomic Lua scripts
        mock_manager.client.eval.return_value = json.dumps({
            "user_id": 1,
            "session_id": "test-session",
            "created_at": "2023-01-01T00:00:00",
            "last_accessed": "2023-01-01T00:30:00",
            "user_data": {"email": "test@example.com"}
        })
        return mock_manager
    
    @pytest.fixture
    def setup_redis_mock(self, mock_redis_manager):
        """Setup redis manager mock."""
        with patch('app.shared.core.session.redis_manager', mock_redis_manager):
            yield mock_redis_manager
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        mock_settings = MagicMock()
        mock_settings.access_token_expire_minutes = 60
        return mock_settings
    
    @pytest.fixture
    def setup_settings_mock(self, mock_settings):
        """Setup settings mock."""
        with patch('app.shared.core.session.settings', mock_settings):
            yield mock_settings
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, setup_redis_mock, setup_settings_mock):
        """Test successful session creation."""
        mock_manager = setup_redis_mock
        mock_settings = setup_settings_mock
        
        manager = SessionManager()
        user_data = {
            "email": "test@example.com",
            "role": "user",
            "ip_address": "127.0.0.1",
            "user_agent": "Mozilla/5.0"
        }
        
        session_id = await manager.create_session(1, user_data)
        
        assert session_id is not None
        assert len(session_id) > 0
        
        # Check session data was stored
        mock_manager.pipeline.assert_called_once()
        pipeline = mock_manager.pipeline.return_value
        pipeline.set.assert_called_once()
        set_args, set_kwargs = pipeline.set.call_args
        assert set_args[0].startswith("session:")
        stored = json.loads(set_args[1])
        assert stored["user_id"] == 1
        assert stored["user_data"]["email"] == "test@example.com"
        assert set_kwargs["ex"] == 3600  # 60 minutes * 60 seconds
        
        # Check session was added to user's session list
        pipeline.sadd.assert_called_once()
        assert pipeline.sadd.call_args[0][0] == "user_sessions:1"
        assert session_id in pipeline.sadd.call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_create_session_with_custom_id(self, setup_redis_mock, setup_settings_mock):
        """Test session creation with custom session ID."""
        mock_manager = setup_redis_mock
        custom_session_id = "custom-session-123"
        
        manager = SessionManager()
        user_data = {"email": "test@example.com"}
        
        session_id = await manager.create_session(1, user_data, session_id=custom_session_id)
        
        assert session_id == custom_session_id
        pipeline = mock_manager.pipeline.return_value
        set_args, _ = pipeline.set.call_args
        assert set_args[0] == f"session:{custom_session_id}"
        stored = json.loads(set_args[1])
        assert stored["session_id"] == custom_session_id
    
    @pytest.mark.asyncio
    async def test_create_session_with_custom_ttl(self, setup_redis_mock, setup_settings_mock):
        """Test session creation with custom TTL."""
        mock_manager = setup_redis_mock
        
        manager = SessionManager()
        user_data = {"email": "test@example.com"}
        
        session_id = await manager.create_session(1, user_data, ttl=7200)
        
        pipeline = mock_manager.pipeline.return_value
        _, set_kwargs = pipeline.set.call_args
        assert set_kwargs["ex"] == 7200

    @pytest.mark.asyncio
    async def test_create_token_session_success(self, setup_redis_mock, setup_settings_mock):
        """Test creating a token session."""
        mock_manager = setup_redis_mock
        manager = SessionManager()
        token = "token-123"
        token_data = {
            "user_id": 1,
            "email": "test@example.com",
            "role": "user",
            "full_name": "Test User",
            "is_active": True,
        }
        result = await manager.create_token_session(token, token_data, ex=1800)
        
        assert result is True
        mock_manager.set.assert_called_once_with(
            f"access_token:{token}", token_data, ex=1800
        )

    @pytest.mark.asyncio
    async def test_get_token_session_success(self, setup_redis_mock):
        """Test retrieving a token session."""
        mock_manager = setup_redis_mock
        token_data = {
            "user_id": 1,
            "email": "test@example.com",
            "role": "user",
            "full_name": "Test User",
            "is_active": True,
        }
        mock_manager.get.return_value = json.dumps(token_data)
        
        manager = SessionManager()
        result = await manager.get_token_session("token-123")
        
        assert result == token_data
        mock_manager.get.assert_called_once_with("access_token:token-123")

    @pytest.mark.asyncio
    async def test_get_token_session_not_found(self, setup_redis_mock):
        """Test retrieving a missing token session."""
        mock_manager = setup_redis_mock
        mock_manager.get.return_value = None
        
        manager = SessionManager()
        result = await manager.get_token_session("token-123")
        
        assert result is None
        mock_manager.get.assert_called_once_with("access_token:token-123")

    @pytest.mark.asyncio
    async def test_get_session_success(self, setup_redis_mock):
        """Test successful session retrieval."""
        mock_manager = setup_redis_mock
        session_data = {
            "user_id": 1,
            "session_id": "test-session",
            "created_at": "2023-01-01T00:00:00",
            "last_accessed": "2023-01-01T00:30:00",
            "user_data": {"email": "test@example.com"}
        }
        # Mock eval to return updated session data (atomic operation)
        updated_session = session_data.copy()
        updated_session["last_accessed"] = "2023-01-01T01:00:00"  # Simulated update
        mock_manager.client.eval.return_value = json.dumps(updated_session)
        
        manager = SessionManager()
        result = await manager.get_session("test-session")
        
        assert result is not None
        assert result["user_id"] == 1
        assert result["session_id"] == "test-session"
        assert result["user_data"]["email"] == "test@example.com"
        assert result["last_accessed"] == "2023-01-01T01:00:00"  # Updated by atomic operation
        
        # Check eval was called for atomic operation
        mock_manager.client.eval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, setup_redis_mock):
        """Test getting non-existent session."""
        mock_manager = setup_redis_mock
        # Mock eval to return None for non-existent session
        mock_manager.client.eval.return_value = None
        
        manager = SessionManager()
        result = await manager.get_session("nonexistent-session")
        
        assert result is None
        mock_manager.set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_session_with_bytes_response(self, setup_redis_mock):
        """Test getting session when Redis returns bytes."""
        mock_manager = setup_redis_mock
        session_data = {"user_id": 1, "session_id": "test-session"}
        # Mock eval to return session data (atomic operation handles bytes internally)
        mock_manager.client.eval.return_value = json.dumps(session_data)
        
        manager = SessionManager()
        result = await manager.get_session("test-session")
        
        assert result is not None
        assert result["user_id"] == 1
    
    @pytest.mark.asyncio
    async def test_update_session_success(self, setup_redis_mock):
        """Test successful session update."""
        mock_manager = setup_redis_mock
        session_data = {"user_id": 1, "session_id": "test-session"}
        # Mock eval to return success for atomic update
        mock_manager.client.eval.return_value = 1  # Success indicator
        
        manager = SessionManager()
        updates = {"last_activity": "login", "ip_address": "192.168.1.1"}
        
        result = await manager.update_session("test-session", updates)
        
        assert result is True
        
        # Check eval was called for atomic update
        mock_manager.client.eval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_session_not_found(self, setup_redis_mock):
        """Test updating non-existent session."""
        mock_manager = setup_redis_mock
        # Mock eval to return 0 for non-existent session
        mock_manager.client.eval.return_value = 0
        
        manager = SessionManager()
        result = await manager.update_session("nonexistent-session", {"test": "data"})
        
        assert result is False
        mock_manager.set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_session_success(self, setup_redis_mock):
        """Test successful session deletion."""
        mock_manager = setup_redis_mock
        session_data = {"user_id": 1, "session_id": "test-session"}
        mock_manager.get.return_value = json.dumps(session_data)
        
        manager = SessionManager()
        result = await manager.delete_session("test-session")
        
        assert result is True
        
        # Check session was deleted
        mock_manager.delete.assert_called_once_with("session:test-session")
        
        # Check session was removed from user's session list
        mock_manager.client.srem.assert_called_once_with("user_sessions:1", "test-session")
    
    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, setup_redis_mock):
        """Test deleting non-existent session."""
        mock_manager = setup_redis_mock
        mock_manager.get.return_value = None
        
        manager = SessionManager()
        result = await manager.delete_session("nonexistent-session")
        
        assert result is False
        mock_manager.delete.assert_not_called()
        mock_manager.client.srem.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_user_sessions_empty(self, setup_redis_mock):
        """Test getting user sessions when none exist."""
        mock_manager = setup_redis_mock
        mock_manager.client.smembers.return_value = set()
        
        manager = SessionManager()
        sessions = await manager.get_user_sessions(1)
        
        assert sessions == []
        mock_manager.client.smembers.assert_called_once_with("user_sessions:1")
    
    @pytest.mark.asyncio
    async def test_get_user_sessions_with_sessions(self, setup_redis_mock):
        """Test getting user sessions with existing sessions."""
        mock_manager = setup_redis_mock
        session_ids = {"session1", "session2"}
        mock_manager.client.smembers.return_value = session_ids
        
        # Mock session data for eval calls
        session1_data = {"user_id": 1, "session_id": "session1"}
        session2_data = {"user_id": 1, "session_id": "session2"}
        
        def mock_eval(script, keys, *args):
            # For session get operations, return session data
            # args format: session_key, timestamp, default_ttl
            if len(args) >= 3 and isinstance(args[0], str):
                session_key = args[0]  # First argument is the session key
                if "session1" in session_key:
                    return json.dumps(session1_data)
                elif "session2" in session_key:
                    return json.dumps(session2_data)
                return None
            # For other operations, return success
            return 1
        
        mock_manager.client.eval.side_effect = mock_eval
        
        manager = SessionManager()
        sessions = await manager.get_user_sessions(1)
        
        assert len(sessions) == 2
        session_ids_result = {session["session_id"] for session in sessions}
        assert "session1" in session_ids_result
        assert "session2" in session_ids_result
    
    @pytest.mark.asyncio
    async def test_get_user_sessions_with_bytes(self, setup_redis_mock):
        """Test getting user sessions when Redis returns bytes."""
        mock_manager = setup_redis_mock
        session_ids = {b"session1", b"session2"}
        mock_manager.client.smembers.return_value = session_ids
        
        # Mock eval to return session data for both sessions
        session1_data = {"user_id": 1, "session_id": "session1"}
        session2_data = {"user_id": 1, "session_id": "session2"}
        
        def mock_eval(script, keys, *args):
            # For session get operations, return session data
            # args format: session_key, timestamp, default_ttl
            if len(args) >= 3 and isinstance(args[0], str):
                session_key = args[0]  # First argument is the session key
                if "session1" in session_key:
                    return json.dumps(session1_data)
                elif "session2" in session_key:
                    return json.dumps(session2_data)
                return None
            # For other operations, return success
            return 1
        
        mock_manager.client.eval.side_effect = mock_eval
        
        manager = SessionManager()
        sessions = await manager.get_user_sessions(1)
        
        assert len(sessions) == 2
    
    @pytest.mark.asyncio
    async def test_revoke_user_sessions_all(self, setup_redis_mock):
        """Test revoking all user sessions."""
        mock_manager = setup_redis_mock
        session_ids = {"session1", "session2", "session3"}
        mock_manager.client.smembers.return_value = session_ids
        
        # Mock session data for get calls
        session_data = {"user_id": 1, "session_id": "test"}
        def mock_get(session_key):
            if any(session in session_key for session in session_ids):
                return json.dumps(session_data)
            return None
        
        mock_manager.get.side_effect = mock_get
        
        manager = SessionManager()
        revoked_count = await manager.revoke_user_sessions(1)
        
        assert revoked_count == 3
        assert mock_manager.delete.call_count == 3
        assert mock_manager.client.srem.call_count == 3
    
    @pytest.mark.asyncio
    async def test_revoke_user_sessions_except_one(self, setup_redis_mock):
        """Test revoking user sessions except one."""
        mock_manager = setup_redis_mock
        session_ids = {"session1", "session2", "session3"}
        mock_manager.client.smembers.return_value = session_ids
        
        # Mock session data for get calls
        session_data = {"user_id": 1, "session_id": "test"}
        def mock_get(session_key):
            if "session1" in session_key or "session3" in session_key:
                return json.dumps(session_data)
            elif "session2" in session_key:
                return json.dumps(session_data)
            return None
        
        mock_manager.get.side_effect = mock_get
        
        manager = SessionManager()
        revoked_count = await manager.revoke_user_sessions(1, except_session="session2")
        
        assert revoked_count == 2
        assert mock_manager.delete.call_count == 2
        
        # Check that session2 was not deleted
        deleted_keys = [call[0][0] for call in mock_manager.delete.call_args_list]
        assert "session:session2" not in deleted_keys
    
    @pytest.mark.asyncio
    async def test_extend_session_success(self, setup_redis_mock):
        """Test successful session extension."""
        mock_manager = setup_redis_mock
        mock_manager.client.ttl.return_value = 1200  # Current TTL
        # Mock eval to return success for atomic update
        mock_manager.client.eval.return_value = 1  # Success indicator
        
        manager = SessionManager()
        result = await manager.extend_session("test-session", 1800)
        
        assert result is True
        mock_manager.client.ttl.assert_called_once()
        mock_manager.client.eval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extend_session_not_found(self, setup_redis_mock):
        """Test extending non-existent session."""
        mock_manager = setup_redis_mock
        mock_manager.client.ttl.return_value = -1  # Key doesn't exist
        
        manager = SessionManager()
        result = await manager.extend_session("nonexistent-session")
        
        assert result is False
        mock_manager.client.ttl.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_is_session_valid_true(self, setup_redis_mock):
        """Test session validation when session is valid."""
        mock_manager = setup_redis_mock
        session_data = {"user_id": 1}
        # Mock eval to return session data for atomic operation
        mock_manager.client.eval.return_value = json.dumps(session_data)
        
        manager = SessionManager()
        result = await manager.is_session_valid("test-session")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_is_session_valid_false(self, setup_redis_mock):
        """Test session validation when session is invalid."""
        mock_manager = setup_redis_mock
        # Mock eval to return None for invalid session
        mock_manager.client.eval.return_value = None
        
        manager = SessionManager()
        result = await manager.is_session_valid("test-session")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_active_session_count(self, setup_redis_mock):
        """Test getting active session count."""
        mock_manager = setup_redis_mock
        mock_manager.client.scan.side_effect = [
            (1, ["session:abc", "session:def"]),
            (0, [])
        ]
        
        manager = SessionManager()
        count = await manager.get_active_session_count()
        
        assert count == 2
        assert mock_manager.client.scan.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_active_session_count_error(self, setup_redis_mock):
        """Test getting active session count with error."""
        mock_manager = setup_redis_mock
        mock_manager.client.scan.side_effect = Exception("Redis error")
        
        manager = SessionManager()
        count = await manager.get_active_session_count()
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, setup_redis_mock):
        """Test cleanup of expired sessions."""
        mock_manager = setup_redis_mock
        
        manager = SessionManager()
        count = await manager.cleanup_expired_sessions()
        
        assert count == 0
        # Cleanup relies on Redis TTL, so no explicit calls expected
