from fastapi import APIRouter, WebSocket
import asyncio
from app.services.websocket import redis_client
router = APIRouter()

@router.websocket("/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"user:{user_id}")

    try:
        # Set 3-minute timeout for WebSocket connections
        timeout_seconds = 180  # 3 minutes
        
        async def listen_with_timeout():
            last_activity = asyncio.get_event_loop().time()
            heartbeat_interval = 30  # Send heartbeat every 30 seconds
            
            async for message in pubsub.listen():
                current_time = asyncio.get_event_loop().time()
                
                if message['type'] == 'message':
                    try:
                        # Send message with timeout to detect closed connections
                        await asyncio.wait_for(
                            websocket.send_text(message["data"]), 
                            timeout=5.0
                        )
                        last_activity = current_time
                    except asyncio.TimeoutError:
                        print(f"WebSocket send timeout for user {user_id}, closing connection")
                        break
                    except Exception as e:
                        print(f"WebSocket error for user {user_id}: {e}")
                        break
                
                # Send heartbeat if no activity for 30 seconds
                elif current_time - last_activity > heartbeat_interval:
                    try:
                        await asyncio.wait_for(
                            websocket.send_text('{"type":"heartbeat"}'), 
                            timeout=5.0
                        )
                        last_activity = current_time
                    except:
                        print(f"Heartbeat failed for user {user_id}, closing connection")
                        break
        
        # Run the listening loop with a 3-minute timeout
        await asyncio.wait_for(listen_with_timeout(), timeout=timeout_seconds)
        
    except asyncio.TimeoutError:
        print(f"WebSocket connection timed out after {timeout_seconds} seconds for user {user_id}")
    except Exception as e:
        print(f"WebSocket connection error for user {user_id}: {e}")
    finally:
        await pubsub.unsubscribe(f"user:{user_id}")
        try:
            await websocket.close()
        except:
            pass  # Connection might already be closed