"""WebSocket endpoints for real-time updates."""

import json
import asyncio
from typing import Dict, Set, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from app.api.auth_deps import get_current_user_ws

from app.shared.core.pubsub import pubsub_manager, EventType
from app.shared.core.logging import get_logger
from app.shared.core.permissions import Permission, role_has_permissions
from app.shared.core.permissions_store import get_user_overrides
from app.shared.core.settings import settings

logger = get_logger(__name__)

# Channel permission mapping - only allow specific channels with required permissions
CHANNEL_PERMISSIONS = {
    "general": None,  # No permissions required for general channel
    "stock_changes": Permission.VIEW_INVENTORY,
    "inventory": Permission.VIEW_INVENTORY,
    "warehouse_updates": Permission.VIEW_WAREHOUSES,
    "document_status": Permission.VIEW_DOCUMENTS,
    "system_alerts": Permission.VIEW_REPORTS,
}

router = APIRouter()


def has_channel_permission(user, channel: str) -> bool:
    """Check if user has permission to subscribe to a channel."""
    if channel.startswith("user_"):
        # Users can always subscribe to their own user channel
        try:
            user_id = int(channel.split("_")[1])
            return user.user_id == user_id
        except (ValueError, IndexError):
            return False
    
    if channel not in CHANNEL_PERMISSIONS:
        return False
    
    required_permission = CHANNEL_PERMISSIONS[channel]
    if required_permission is None:
        return True  # No permission required
    
    if user.role == "admin":
        return True
    
    # Check user overrides first
    overrides = get_user_overrides(user.user_id)
    if overrides and required_permission in overrides:
        return True
    
    # Check role permissions
    return role_has_permissions(user.role, {required_permission})


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        self._connection_lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: int, channels: List[str]):
        """Accept WebSocket connection and subscribe to channels."""
        await websocket.accept()
        
        async with self._connection_lock:
            # Add to general connections
            if "general" not in self.active_connections:
                self.active_connections["general"] = set()
            self.active_connections["general"].add(websocket)
            
            # Add to user-specific connections
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
            
            # Add to channel-specific connections
            for channel in channels:
                if channel not in self.active_connections:
                    self.active_connections[channel] = set()
                self.active_connections[channel].add(websocket)
        
        logger.info(f"WebSocket connected for user {user_id}, channels: {channels}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove WebSocket connection."""
        # Remove from all connection sets
        for channel_connections in self.active_connections.values():
            channel_connections.discard(websocket)
        
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    def _cleanup_connection(self, websocket: WebSocket, user_id: int = None):
        """Remove connection from all registries to prevent stale references."""
        # Remove from all channel connections
        for channel_connections in self.active_connections.values():
            channel_connections.discard(websocket)
        
        # Remove from user connections if user_id provided
        if user_id is not None and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    async def send_personal_message(self, message: str, user_id: int):
        """Send message to specific user."""
        if user_id in self.user_connections:
            # Create a copy to avoid mutation during iteration
            connections = list(self.user_connections[user_id])
            disconnected = set()
            for connection in connections:
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.add(connection)
            
            # Clean up disconnected connections from all registries
            for conn in disconnected:
                self._cleanup_connection(conn, user_id)
    
    async def broadcast_to_channel(self, message: str, channel: str):
        """Broadcast message to all connections in a channel."""
        if channel in self.active_connections:
            # Create a copy to avoid mutation during iteration
            connections = list(self.active_connections[channel])
            disconnected = set()
            for connection in connections:
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.add(connection)
            
            # Clean up disconnected connections from all registries
            for conn in disconnected:
                self._cleanup_connection(conn)
    
    async def broadcast_to_all(self, message: str):
        """Broadcast message to all connected clients."""
        # Create a copy to avoid mutation during iteration
        connections = list(self.active_connections.get("general", set()))
        disconnected = set()
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected connections from all registries
        for conn in disconnected:
            self._cleanup_connection(conn)


manager = ConnectionManager()

# Global pub/sub event handlers to prevent per-connection duplication
async def handle_stock_change(data):
    message = json.dumps({
        "type": "stock_change",
        "data": data,
        "timestamp": data.get("timestamp")
    })
    task = asyncio.create_task(manager.broadcast_to_channel(message, "stock_changes"))
    # Store task reference to prevent garbage collection
    if not hasattr(manager, '_tasks'):
        manager._tasks = set()
    manager._tasks.add(task)
    # Add cleanup callback
    task.add_done_callback(manager._tasks.discard)

async def handle_inventory_update(data):
    message = json.dumps({
        "type": "inventory_update", 
        "data": data,
        "timestamp": data.get("timestamp")
    })
    task = asyncio.create_task(manager.broadcast_to_channel(message, "inventory"))
    if not hasattr(manager, '_tasks'):
        manager._tasks = set()
    manager._tasks.add(task)
    # Add cleanup callback
    task.add_done_callback(manager._tasks.discard)

async def handle_system_alert(data):
    message = json.dumps({
        "type": "system_alert",
        "data": data,
        "timestamp": data.get("timestamp")
    })
    task = asyncio.create_task(manager.broadcast_to_all(message))
    if not hasattr(manager, '_tasks'):
        manager._tasks = set()
    manager._tasks.add(task)
    # Add cleanup callback
    task.add_done_callback(manager._tasks.discard)

# Subscribe to events once at module level
pubsub_manager.subscribe(EventType.STOCK_CHANGE, handle_stock_change)
pubsub_manager.subscribe(EventType.INVENTORY_UPDATE, handle_inventory_update)
pubsub_manager.subscribe(EventType.SYSTEM_ALERT, handle_system_alert)
pubsub_manager.subscribe(EventType.CRITICAL_STOCK_CHANGE, handle_stock_change)
pubsub_manager.subscribe(EventType.CRITICAL_INVENTORY_UPDATE, handle_inventory_update)


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, current_user = Depends(get_current_user_ws)):
    """WebSocket endpoint for real-time updates."""
    # Validate user authorization
    if current_user.user_id != user_id:
        await websocket.close(code=1008, reason="Unauthorized: Cannot access another user's WebSocket")
        return
    
    # Start with default channels that user has permission for
    default_channels = ["general", f"user_{user_id}"]
    allowed_channels = []
    
    for channel in default_channels:
        if has_channel_permission(current_user, channel):
            allowed_channels.append(channel)
        else:
            logger.warning(f"User {user_id} denied access to channel {channel}")
    
    try:
        await manager.connect(websocket, user_id, allowed_channels)
        
        # Send welcome message with allowed channels
        await websocket.send_text(json.dumps({
            "type": "connection",
            "message": "Connected to WMS real-time updates",
            "user_id": user_id,
            "channels": allowed_channels
        }))
        
        # Keep connection alive
        while True:
            try:
                # Receive client messages (could be for subscription changes)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "subscribe":
                    # Handle dynamic subscription changes with permission validation
                    new_channels = message.get("channels", [])
                    added_channels = []
                    
                    async with manager._connection_lock:
                        for channel in new_channels:
                            # Validate channel name format
                            if not channel.replace("_", "").isalnum():
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": f"Invalid channel name: {channel}"
                                }))
                                continue
                            
                            # Check if user has permission for this channel
                            if not has_channel_permission(current_user, channel):
                                await websocket.send_text(json.dumps({
                                    "type": "error", 
                                    "message": f"Permission denied for channel: {channel}"
                                }))
                                logger.warning(f"User {user_id} denied subscription to channel {channel}")
                                continue
                            
                            # Limit number of channels per connection
                            if len(allowed_channels) >= 20:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": "Channel limit reached"
                                }))
                                break
                            
                            if channel not in allowed_channels:
                                allowed_channels.append(channel)
                                added_channels.append(channel)
                                if channel not in manager.active_connections:
                                    manager.active_connections[channel] = set()
                                manager.active_connections[channel].add(websocket)
                    
                    if added_channels:
                        await websocket.send_text(json.dumps({
                            "type": "subscription_updated",
                            "added_channels": added_channels,
                            "channels": allowed_channels
                        }))
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error for user {user_id}: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, user_id)


@router.get("/ws-test", response_class=HTMLResponse)
async def websocket_test_page():
    """Simple WebSocket test page."""
    if not settings.debug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WMS WebSocket Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .messages { 
                border: 1px solid #ccc; 
                height: 300px; 
                overflow-y: scroll; 
                padding: 10px; 
                margin: 10px 0;
                background-color: #f9f9f9;
            }
            .message { 
                margin: 5px 0; 
                padding: 5px;
                border-radius: 3px;
            }
            .stock-change { background-color: #e3f2fd; }
            .inventory-update { background-color: #f3e5f5; }
            .system-alert { background-color: #fff3e0; }
            .connection { background-color: #e8f5e8; }
        </style>
    </head>
    <body>
        <h1>WMS Real-time Updates Test</h1>
        <div>
            <label>User ID: </label>
            <input type="number" id="userId" value="1" min="1">
            <label>Token: </label>
            <input type="text" id="tokenInput" value="your-jwt-token-here" style="width: 300px;">
            <button onclick="connect()">Connect</button>
            <button onclick="disconnect()">Disconnect</button>
        </div>
        <div id="messages" class="messages"></div>
        <div>
            <input type="text" id="messageInput" placeholder="Type a message..." style="width: 300px;">
            <button onclick="sendMessage()">Send Test Message</button>
        </div>
        
        <script>
            let ws = null;
            let userId = 1;
            
            function connect() {
                userId = document.getElementById('userId').value;
                const token = document.getElementById('tokenInput').value || 'your-jwt-token-here';
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const host = window.location.host;
                // Note: Using token in URL for demo purposes, but Authorization header is preferred
                const wsUrl = `${protocol}//${host}/api/v1/ws/${userId}?token=${encodeURIComponent(token)}`;
                
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function(event) {
                    addMessage('Connected to WebSocket', 'connection');
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    addMessage(JSON.stringify(data, null, 2), data.type);
                };
                
                ws.onclose = function(event) {
                    addMessage('Disconnected from WebSocket', 'connection');
                };
                
                ws.onerror = function(error) {
                    addMessage('WebSocket Error: ' + error, 'error');
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                }
            }
            
            function sendMessage() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    const message = document.getElementById('messageInput').value;
                    ws.send(JSON.stringify({ type: 'client_message', data: message }));
                    document.getElementById('messageInput').value = '';
                } else {
                    addMessage('WebSocket not connected', 'error');
                }
            }
            
            function addMessage(message, type = 'info') {
                const messages = document.getElementById('messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}`;
                
                const ts = document.createElement('strong');
                ts.textContent = new Date().toLocaleTimeString();
                messageDiv.appendChild(ts);
                messageDiv.appendChild(document.createElement('br'));
                const body = document.createElement('span');
                body.textContent = message;
                messageDiv.appendChild(body);
                
                messages.appendChild(messageDiv);
                messages.scrollTop = messages.scrollHeight;
            }
            
            // Auto-connect on page load
            window.onload = function() {
                connect();
            };
        </script>
    </body>
    </html>
    """
