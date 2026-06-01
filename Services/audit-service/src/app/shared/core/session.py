"""Redis-based session management for WMS."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.shared.core.redis import redis_manager
from app.shared.core.settings import settings
from app.shared.core.logging import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Manages user sessions using Redis."""
    
    def __init__(self):
        self.session_prefix = "session:"
        self.user_sessions_prefix = "user_sessions:"
        self.token_prefix = "access_token:"
        self.default_ttl = settings.access_token_expire_minutes * 60  # Convert to seconds
    
    async def create_session(
        self, 
        user_id: int, 
        user_data: Dict[str, Any],
        session_id: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> str:
        """Create a new session for user."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        session_key = f"{self.session_prefix}{session_id}"
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        
        # Session data
        session_data = {
            "user_id": user_id,
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat(),
            "user_data": user_data,
            "ip_address": user_data.get("ip_address"),
            "user_agent": user_data.get("user_agent"),
        }

        # Store session data and index user sessions in a single Redis round trip.
        session_ttl = ttl or self.default_ttl
        try:
            pipeline = redis_manager.pipeline()
            pipeline.set(session_key, json.dumps(session_data, default=str), ex=session_ttl)
            pipeline.sadd(user_sessions_key, session_id)
            pipeline.expire(user_sessions_key, session_ttl)
            await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to create session pipeline for {session_id}: {e}")
            raise

        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by session ID with atomic update."""
        session_key = f"{self.session_prefix}{session_id}"
        
        # Use atomic Lua script to get and update session
        lua_script = """
        local session_data = redis.call('GET', KEYS[1])
        if session_data == false then
            return nil
        end
        
        -- Parse JSON and update last_accessed
        local data = cjson.decode(session_data)
        data['last_accessed'] = ARGV[1]
        
        -- Get current TTL and preserve it
        local current_ttl = redis.call('TTL', KEYS[1])
        local ttl_to_use = current_ttl > 0 and current_ttl or tonumber(ARGV[2])
        
        -- Update session with preserved TTL
        redis.call('SET', KEYS[1], cjson.encode(data), 'EX', ttl_to_use)
        
        return cjson.encode(data)
        """
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            result = await redis_manager.client.eval(
                lua_script, 1, session_key, now, self.default_ttl
            )
            
            if result is None:
                return None
            
            # Parse result and refresh user session index TTL
            if isinstance(result, bytes):
                result = result.decode('utf-8')
            session_data = json.loads(result)
            
            # Refresh user session index TTL
            user_id = session_data.get("user_id")
            if user_id:
                user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
                await redis_manager.expire(user_sessions_key, self.default_ttl)
            
            return session_data
            
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data with atomic operations."""
        session_key = f"{self.session_prefix}{session_id}"
        
        # Use atomic Lua script to update session
        lua_script = """
        local session_data = redis.call('GET', KEYS[1])
        if session_data == false then
            return 0
        end
        
        -- Parse JSON and apply updates
        local data = cjson.decode(session_data)
        local updates = cjson.decode(ARGV[1])
        
        -- Apply all updates to session data
        for key, value in pairs(updates) do
            data[key] = value
        end
        
        -- Update last_accessed
        data['last_accessed'] = ARGV[2]
        
        -- Get current TTL and preserve it
        local current_ttl = redis.call('TTL', KEYS[1])
        local ttl_to_use = current_ttl > 0 and current_ttl or tonumber(ARGV[3])
        
        -- Update session with preserved TTL
        redis.call('SET', KEYS[1], cjson.encode(data), 'EX', ttl_to_use)
        
        return 1
        """
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            updates_json = json.dumps(updates)
            result = await redis_manager.client.eval(
                lua_script, 1, session_key, updates_json, now, self.default_ttl
            )
            
            if result:
                logger.debug(f"Updated session {session_id}")
                return True
            else:
                logger.debug(f"Session {session_id} not found for update")
                return False
                
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_key = f"{self.session_prefix}{session_id}"
        session_data = await redis_manager.get(session_key)
        
        if session_data is None:
            return False
        
        if isinstance(session_data, str):
            session_data = json.loads(session_data)
        
        user_id = session_data.get("user_id")
        
        # Remove session
        await redis_manager.delete(session_key)
        
        # Remove from user's session list
        if user_id:
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            await redis_manager.client.srem(user_sessions_key, session_id)
        
        logger.info(f"Deleted session {session_id} for user {user_id}")
        return True
    
    async def create_token_session(
        self, token: str, token_data: Dict[str, Any], ex: Optional[int] = None
    ) -> bool:
        """Create a token-backed session for access token caching."""
        token_key = f"{self.token_prefix}{token}"
        ttl = ex if ex is not None else self.default_ttl
        try:
            return await redis_manager.set(token_key, token_data, ex=ttl)
        except Exception as e:
            logger.error(f"Error creating token session for token '{token}': {e}")
            return False
    
    async def get_token_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Get cached data for an access token."""
        token_key = f"{self.token_prefix}{token}"
        try:
            token_data = await redis_manager.get(token_key)
            if token_data is None:
                return None
            if isinstance(token_data, bytes):
                token_data = token_data.decode("utf-8")
            if isinstance(token_data, str):
                return json.loads(token_data)
            return token_data
        except Exception as e:
            logger.error(f"Error retrieving token session for token '{token}': {e}")
            return None
    
    async def delete_token_session(self, token: str) -> bool:
        """Delete a cached access token session."""
        token_key = f"{self.token_prefix}{token}"
        try:
            return await redis_manager.delete(token_key)
        except Exception as e:
            logger.error(f"Error deleting token session for token '{token}': {e}")
            return False
    
    async def get_user_sessions(self, user_id: int) -> list:
        """Get all active sessions for a user."""
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        session_ids = await redis_manager.client.smembers(user_sessions_key)
        
        sessions = []
        for session_id in session_ids:
            if isinstance(session_id, bytes):
                session_id = session_id.decode('utf-8')
            session_data = await self.get_session(session_id)
            if session_data:
                sessions.append(session_data)
        
        return sessions
    
    async def revoke_user_sessions(self, user_id: int, except_session: Optional[str] = None) -> int:
        """Revoke all sessions for a user except optionally one session."""
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        session_ids = await redis_manager.client.smembers(user_sessions_key)
        
        revoked_count = 0
        for session_id in session_ids:
            if isinstance(session_id, bytes):
                session_id = session_id.decode('utf-8')
            
            if except_session and session_id == except_session:
                continue
            
            await self.delete_session(session_id)
            revoked_count += 1
        
        logger.info(f"Revoked {revoked_count} sessions for user {user_id}")
        return revoked_count
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (maintenance task)."""
        # This would typically be run as a background task
        # For now, we rely on Redis TTL for automatic cleanup
        logger.debug("Session cleanup relies on Redis TTL")
        return 0
    
    async def extend_session(self, session_id: str, ttl_seconds: Optional[int] = None) -> bool:
        """Extend session TTL with validation and edge case handling."""
        session_key = f"{self.session_prefix}{session_id}"
        
        # Get current TTL to validate against shrinking
        current_ttl = await redis_manager.client.ttl(session_key)
        if current_ttl < 0:  # Key doesn't exist or has no expiry
            return False
        
        # Determine final TTL
        final_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        
        # Prevent shrinking existing session
        if ttl_seconds is not None and ttl_seconds < current_ttl:
            logger.debug(f"Rejected TTL shrink for session {session_id}: {ttl_seconds} < {current_ttl}")
            return False
        
        # Handle invalid TTL values
        if final_ttl <= 0:
            # Delete session and remove from user_sessions index
            session_data = await redis_manager.get(session_key)
            if session_data:
                if isinstance(session_data, str):
                    session_data = json.loads(session_data)
                elif isinstance(session_data, bytes):
                    session_data = json.loads(session_data.decode('utf-8'))
                
                user_id = session_data.get("user_id")
                if user_id:
                    user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
                    await redis_manager.client.srem(user_sessions_key, session_id)
            
            await redis_manager.delete(session_key)
            logger.info(f"Deleted session {session_id} due to zero/negative TTL")
            return True
        
        # Use atomic Lua script to update session with new TTL
        lua_script = """
        local session_data = redis.call('GET', KEYS[1])
        if session_data == false then
            return 0
        end
        
        -- Parse JSON and update last_accessed
        local data = cjson.decode(session_data)
        data['last_accessed'] = ARGV[1]
        
        -- Update session with new TTL
        redis.call('SET', KEYS[1], cjson.encode(data), 'EX', ARGV[2])
        
        return 1
        """
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            result = await redis_manager.client.eval(
                lua_script, 1, session_key, now, final_ttl
            )
            
            if result:
                logger.debug(f"Extended session {session_id} to TTL {final_ttl} seconds")
                return True
            else:
                logger.debug(f"Session {session_id} not found for extension")
                return False
                
        except Exception as e:
            logger.error(f"Error extending session {session_id}: {e}")
            return False
    
    async def is_session_valid(self, session_id: str) -> bool:
        """Check if session is valid and not expired."""
        session_data = await self.get_session(session_id)
        return session_data is not None
    
    async def get_active_session_count(self) -> int:
        """Get count of active sessions (for monitoring)."""
        try:
            # This is a rough estimate - counts all session keys
            cursor = 0
            count = 0
            pattern = f"{self.session_prefix}*"
            
            while True:
                cursor, keys = await redis_manager.client.scan(
                    cursor, match=pattern, count=100
                )
                count += len(keys)
                
                if cursor == 0:
                    break
            
            return count
        except Exception as e:
            logger.error(f"Error counting active sessions: {e}")
            return 0


# Global session manager instance
session_manager = SessionManager()
