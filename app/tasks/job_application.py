import os
import tempfile
import uuid
from typing import Dict, Any
from celery import current_task
import logging
import asyncio

from app.tasks.celery_app import celery_app
from app.services.browser import browser_pool
from app.services.storage import storage_manager
from app.db.firestore import firestore_manager
from app.db.postgres import postgres_manager
from app.schemas.application import ApplicationStatus
from app.services.websocket import websocket_manager
from app.services.job_application import JobApplicationService

logger = logging.getLogger(__name__)


def log_to_firestore(user_id: str, application_id: str, level: str, message: str):
    """Helper function to log messages to Firestore"""
    try:
        firestore_manager.add_application_log(user_id, application_id, level, message)
    except Exception as e:
        logger.error(f"Failed to log to Firestore: {e}")


@celery_app.task(bind=True)
def apply_to_job(self, application_data: Dict[str, Any]):
    """Main task to apply to a job"""
    worker_id = f"worker_{current_task.request.hostname}_{os.getpid()}"
    
    user_id = application_data['user_id']
    application_id = application_data['application_id']
    job_id = application_data['job_id']
    should_submit = application_data.get('should_submit', False)
    form_questions = application_data.get('form_questions', None)
    override_form_questions = application_data.get('override_form_questions', False)
    
    logger.info(f"Starting job application task for job {job_id}, application {application_id}")
    
    driver = None
    
    try:
        # Get user profile
        profile = firestore_manager.get_profile(user_id)
        if not profile:
            raise Exception(f"User profile not found for user ID {user_id}")
        
        # Get job details from PostgreSQL
        job = postgres_manager.get_job_by_id(int(job_id))
        if not job:
            raise Exception(f"Job with ID {job_id} not found")
            
        job_url = job.get('jobUrl')
        if not job_url:
            raise Exception(f"Job URL not found for job ID {job_id}")
        
        # Update status to processing (combine with initial log)
        firestore_manager.update_application_status(
            user_id,
            application_id,
            ApplicationStatus.PROCESSING
        )
        
        # Get browser driver from pool
        driver = browser_pool.get_driver(worker_id)
        
        # Navigate to job URL with reduced timeout
        driver.set_page_load_timeout(10)  # Reduce from default 30s to 10s
        driver.get(job_url)
        
        # Apply based on job site and whether this is a preparation or submission
        success = False
        final_status = ApplicationStatus.FAILED
        form_questions = None
        screenshot, screenshot_url = None, None

        # Create job application service with profile
        job_service = JobApplicationService(driver, profile)
        
        # Add profile and job data to application_data for reference
        application_data['profile'] = profile
        application_data['job'] = job
        
        if should_submit:
            # This is a submission request - actually apply and submit
            success = job_service.apply(job_url)
            final_status = ApplicationStatus.APPLIED if success else ApplicationStatus.FAILED
        else:
            # This is just a preparation/save request - apply but don't submit
            # TODO: Implement preparation mode (form detection without submission)
            
            # For now, we'll still call apply but in preparation mode
            success = job_service.apply(job_url)
            final_status = ApplicationStatus.DRAFT if success else ApplicationStatus.FAILED
            
        # Take screenshot and upload in background (don't wait)
        screenshot_url = None
        try:
            screenshot = take_screenshot(driver, application_id)
            if screenshot:
                # Upload asynchronously - don't block task completion
                screenshot_url = storage_manager.upload_screenshot(screenshot, application_id)
                # Cleanup immediately
                try:
                    os.remove(screenshot)
                except:
                    pass
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")

        # Single Firestore update with all data
        log_message = "Job application submitted successfully" if (success and should_submit) else \
                     "Job application prepared successfully" if success else \
                     "Job application failed"
        
        firestore_manager.update_application_status(
            user_id,
            application_id,
            final_status,
            form_questions=form_questions,
            screenshot=screenshot_url,
            error_message=None if success else "Application process failed"
        )
        
        if success:
            logger.info(f"Task completed successfully for job {job_id}")
        else:
            logger.error(f"Task failed for job {job_id}: {log_message}")
        
        # Send WebSocket notification (fire-and-forget, don't block)
        try:
            asyncio.create_task(websocket_manager.broadcast_to_user(user_id, {
                "type": "application_update",
                "application_id": application_id,
                "status": final_status,
                "message": log_message,
                "screenshot_url": screenshot_url
            }))
        except Exception:
            # If asyncio fails, try sync version but don't block long
            try:
                asyncio.run(websocket_manager.broadcast_to_user(user_id, {
                    "type": "application_update",
                    "application_id": application_id,
                    "status": final_status,
                    "message": log_message,
                    "screenshot_url": screenshot_url
                }))
            except Exception as e:
                logger.error(f"WebSocket notification failed: {e}")
        
        return {
            "status": final_status,
            "screenshot_url": screenshot_url,
            "message": log_message
        }
        
    except Exception as e:
        error_message = f"Application failed: {str(e)}"
        logger.error(f"Task failed for job {job_id}: {error_message}")
        
        # Single Firestore update for failure
        try:
            firestore_manager.update_application_status(
                user_id,
                application_id,
                ApplicationStatus.FAILED,
                error_message=error_message
            )
        except Exception as firestore_error:
            logger.error(f"Failed to update application status to FAILED: {firestore_error}")
        
        # Send failure WebSocket notification (fire-and-forget)
        try:
            asyncio.create_task(websocket_manager.broadcast_to_user(user_id, {
                "type": "application_update",
                "application_id": application_id,
                "status": ApplicationStatus.FAILED,
                "message": error_message
            }))
        except Exception:
            try:
                asyncio.run(websocket_manager.broadcast_to_user(user_id, {
                    "type": "application_update",
                    "application_id": application_id,
                    "status": ApplicationStatus.FAILED,
                    "message": error_message
                }))
            except Exception as ws_error:
                logger.error(f"Failure WebSocket notification failed: {ws_error}")
        
        raise
        
    finally:
        if driver:
            try:
                browser_pool.release_driver(worker_id)
            except Exception as e:
                logger.error(f"Error releasing driver: {e}")
                # If release fails, try to close the driver completely
                try:
                    browser_pool.close_driver(worker_id)
                except:
                    pass


def take_screenshot(driver, application_id: str) -> str:
    """Take a screenshot of the current page"""
    try:
        # Use temp directory for faster I/O
        filename = f"screenshot_{application_id}_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        
        # Take screenshot with minimal quality for speed
        driver.save_screenshot(filepath)
        return filepath
        
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return None

