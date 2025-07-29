from fastapi import APIRouter, WebSocket
import asyncio
import json
from app.services.websocket import redis_client
router = APIRouter()

@router.websocket("/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"user:{user_id}")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                await websocket.send_text(message["data"])
            await asyncio.sleep(10)
    finally:
        await pubsub.unsubscribe(f"user:{user_id}")