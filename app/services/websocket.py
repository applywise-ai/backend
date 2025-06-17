from typing import Dict, Set
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str):
        """Connect a new WebSocket client"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"WebSocket connected for user {user_id}")
        
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Disconnect a WebSocket client"""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")
        
    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast a message to all connections of a specific user"""
        if user_id not in self.active_connections:
            return
            
        disconnected = set()
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")
                disconnected.add(connection)
                
        # Clean up disconnected sockets
        for connection in disconnected:
            self.disconnect(connection, user_id)

# Create a global instance
websocket_manager = WebSocketManager() 