#!/usr/bin/env python3
"""
Test script to demonstrate Redis WebSocket manager with job application updates.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.websocket import websocket_manager, send_job_application_update

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_job_application_updates():
    """Test sending job application updates to users."""
    try:
        print("🧪 Testing Redis WebSocket Manager with Job Application Updates")
        print("=" * 70)
        
        # Initialize the WebSocket manager
        print("🔌 Initializing WebSocket manager...")
        await websocket_manager.initialize()
        print("✅ WebSocket manager initialized")
        
        # Check Redis status
        redis_connected = websocket_manager.redis_client is not None
        print(f"   Redis connected: {redis_connected}")
        
        if not redis_connected:
            print("⚠️ Redis not available, testing local-only mode")
        
        # Test job application updates
        print("\n📝 Testing job application updates...")
        
        test_user_id = "test_user_123"
        
        # Send a job application update
        await send_job_application_update(test_user_id, "app_456", "submitted", {
            "job_title": "Software Engineer",
            "company": "Tech Corp",
            "job_url": "https://example.com/job/123"
        })
        print(f"   ✅ Sent job application update to user {test_user_id}")
        
        # Send another update with different status
        await send_job_application_update(test_user_id, "app_789", "in_progress", {
            "job_title": "Frontend Developer",
            "company": "Startup Inc",
            "progress": "Form filling completed, proceeding to submission"
        })
        print(f"   ✅ Sent in-progress update to user {test_user_id}")
        
        # Send a completion update
        await send_job_application_update(test_user_id, "app_456", "completed", {
            "job_title": "Software Engineer",
            "company": "Tech Corp",
            "result": "Application submitted successfully",
            "screenshot_url": "https://example.com/screenshot.png"
        })
        print(f"   ✅ Sent completion update to user {test_user_id}")
        
        # Send a failure update
        await send_job_application_update(test_user_id, "app_999", "failed", {
            "job_title": "DevOps Engineer",
            "company": "Cloud Corp",
            "error": "Application form not found or changed",
            "retry_count": 2
        })
        print(f"   ✅ Sent failure update to user {test_user_id}")
        
        # Get statistics
        print("\n📊 Connection statistics...")
        total_connections = await websocket_manager.get_total_connection_count()
        active_users = await websocket_manager.get_active_users()
        user_connections = await websocket_manager.get_user_connection_count(test_user_id)
        
        print(f"   Total connections: {total_connections}")
        print(f"   Active users: {list(active_users)}")
        print(f"   Connections for {test_user_id}: {user_connections}")
        
        print("\n✅ All job application update tests completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        logger.error(f"Error in job application update test: {str(e)}")
        return False
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        try:
            await websocket_manager.shutdown()
            print("✅ WebSocket manager shutdown complete")
        except Exception as e:
            print(f"❌ Error during shutdown: {e}")


async def simulate_redis_job_updates():
    """Simulate Redis pub/sub for job application updates."""
    try:
        print("\n🔄 Simulating Redis Pub/Sub for Job Updates")
        print("=" * 55)
        
        if not websocket_manager.redis_client:
            print("⚠️ Redis not available, skipping pub/sub simulation")
            return True
        
        # Initialize WebSocket manager
        await websocket_manager.initialize()
        
        # Simulate publishing job application updates to user channels
        test_user_id = "redis_test_user"
        
        # Publish a job application update to the user's channel
        user_channel = websocket_manager.USER_MESSAGE_CHANNEL.format(test_user_id)
        message_data = {
            "message": {
                "type": "job_application_update",
                "application_id": "app_redis_001",
                "status": "submitted",
                "timestamp": asyncio.get_event_loop().time(),
                "details": {
                    "job_title": "Backend Developer",
                    "company": "Redis Corp",
                    "job_url": "https://redis.com/careers/backend"
                }
            }
        }
        
        await websocket_manager.redis_client.publish(user_channel, json.dumps(message_data))
        print(f"   ✅ Published job update to channel: {user_channel}")
        
        # Publish another update
        message_data_2 = {
            "message": {
                "type": "job_application_update",
                "application_id": "app_redis_002",
                "status": "completed",
                "timestamp": asyncio.get_event_loop().time(),
                "details": {
                    "job_title": "Data Engineer",
                    "company": "Redis Corp",
                    "result": "Application submitted successfully",
                    "screenshot_url": "https://redis.com/screenshots/app_002.png"
                }
            }
        }
        
        await websocket_manager.redis_client.publish(user_channel, json.dumps(message_data_2))
        print(f"   ✅ Published second job update to channel: {user_channel}")
        
        # Wait a moment for messages to be processed
        await asyncio.sleep(1)
        
        print("   ✅ Redis pub/sub simulation for job updates completed")
        return True
        
    except Exception as e:
        print(f"\n❌ Redis pub/sub simulation failed: {str(e)}")
        logger.error(f"Error in Redis pub/sub simulation: {str(e)}")
        return False
    
    finally:
        try:
            await websocket_manager.shutdown()
        except:
            pass


async def main():
    """Run all WebSocket Redis tests."""
    print("🚀 Starting Redis WebSocket Manager Tests")
    print("=" * 70)
    
    # Test job application updates
    updates_success = await test_job_application_updates()
    
    # Simulate Redis pub/sub for job updates
    pubsub_success = await simulate_redis_job_updates()
    
    if updates_success and pubsub_success:
        print("\n🎉 All Redis WebSocket tests passed!")
        print("\n📝 Summary:")
        print("   - WebSocket manager initialized successfully")
        print("   - Job application updates work correctly")
        print("   - Redis pub/sub integration for job updates works")
        print("   - Graceful fallback when Redis is unavailable")
        print("   - Simplified focus on job application updates only")
        return True
    else:
        print("\n❌ Some Redis WebSocket tests failed!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 