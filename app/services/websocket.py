import redis.asyncio as aioredis
from app.core.config import settings
import json
import asyncio
from typing import List, Optional
from app.schemas.application import FormQuestion

redis_client = aioredis.from_url(settings.get_redis_url(db=1), decode_responses=True)

def check_able_to_submit(form_questions: Optional[List[FormQuestion]] = None) -> bool:
    """
    Check if all required form questions have non-None answers
    
    Args:
        form_questions: List of form questions to check
        
    Returns:
        True if all required questions have answers, False otherwise
    """
    if not form_questions:
        return True  # If no questions, can submit
    
    for question in form_questions:
        if question.get('required') and question.get('answer') is None:
            return False
    
    return True

async def send_job_application_update(user_id: str, application_id: str, status: str, details: dict = None, form_questions: Optional[List[FormQuestion]] = None):
    """
    Send a job application status update to a user via Redis pub/sub
    
    Args:
        user_id: The user ID to send the update to
        application_id: The application ID
        status: The new status (e.g., 'submitted', 'in_progress', 'completed', 'failed')
        details: Additional details about the application
        form_questions: List of form questions to check for able_to_submit
    """
    # Check if able to submit based on form questions
    able_to_submit = check_able_to_submit(form_questions)
    
    message = {
        "type": "job_application_update",
        "application_id": application_id,
        "status": status,
        "timestamp": asyncio.get_event_loop().time(),
        "details": details or {},
        "able_to_submit": able_to_submit
    }
    
    try:
        channel = f"user:{user_id}"
        await redis_client.publish(channel, json.dumps({"message": message}))
        print(f"Job application update sent to user {user_id} on channel {channel}")
    except Exception as e:
        print(f"Error sending job application update: {e}")