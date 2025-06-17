from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ...services.websocket import websocket_manager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time updates"""
    try:
        await websocket_manager.connect(websocket, user_id)
        while True:
            # Keep connection alive and handle any client messages
            data = await websocket.receive_text()
            # We don't need to handle any client messages for now
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        websocket_manager.disconnect(websocket, user_id) 