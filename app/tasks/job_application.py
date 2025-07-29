import os
import tempfile
from typing import Dict, Any
from celery import current_task
import logging
import asyncio
import base64

from app.tasks.celery_app import celery_app
from app.services.browser import browser_pool
from app.services.storage import storage_manager
from app.db.firestore import firestore_manager
from app.db.postgres import postgres_manager
from app.schemas.application import ApplicationStatus
from app.services.websocket import send_job_application_update
from app.services.job_application import JobApplicationService

logger = logging.getLogger(__name__)


def log_to_firestore(user_id: str, application_id: str, level: str, message: str):
    """Helper function to log messages to Firestore"""
    try:
        firestore_manager.add_application_log(user_id, application_id, level, message)
    except Exception as e:
        logger.error(f"Failed to log to Firestore: {e}")


def _run_async_websocket(func, *args, **kwargs):
    """Run an async WebSocket function in a separate thread"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(func(*args, **kwargs))
    except Exception as e:
        logger.error(f"WebSocket operation failed: {e}")
    finally:
        loop.close()


@celery_app.task(bind=True)
def apply_to_job(self, application_data: Dict[str, Any]):
    """Main task to apply to a job"""
    worker_id = f"worker_{current_task.request.hostname}_{os.getpid()}"
    
    user_id = application_data['user_id']
    application_id = application_data['application_id']
    job_id = application_data['job_id']
    should_submit = application_data.get('should_submit', False)
    overrided_form_questions = application_data.get('form_questions', None)
    
    logger.info(f"Starting job application task for job {job_id}, application {application_id}")
    
    driver = None
    
    try:
        # Get user profile
        profile = firestore_manager.get_profile(user_id)
        if not profile:
            raise Exception(f"User profile not found for user ID {user_id}")
        
        # Get job details from PostgreSQL
        logger.info(f"Getting job details for job ID {type(job_id)} {job_id}")
        job = postgres_manager.get_job_by_id(job_id)
        if not job:
            raise Exception(f"Job with ID {job_id} not found")

        job_url = job.get('job_url')
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
        driver.set_page_load_timeout(30)  # Reduce from default 30s to 10s
        driver.get(job_url)
        
        # Apply based on job site and whether this is a preparation or submission
        final_status = ApplicationStatus.FAILED
        form_questions = None
        screenshot, screenshot_url = None, None

        # We need to set the cover letter details based on application id
        cover_letter_url, cover_letter_filename = storage_manager.get_cover_letter(user_id, application_id)
        if cover_letter_url:
            profile['coverLetterUrl'] = cover_letter_url
            profile['coverLetterFilename'] = cover_letter_filename or "cover_letter.pdf"

        # We need to set the resume details based on application id
        resume_url, resume_filename = storage_manager.get_resume(user_id, application_id)
        if resume_url:
            profile['resumeUrl'] = resume_url
            profile['resumeFilename'] = resume_filename or "resume.pdf"

        # We need to set the override answers based on the form questions
        overrided_answers = None
        if overrided_form_questions:
            overrided_answers = {
                question['unique_label_id']: question.get('answer') for question in overrided_form_questions
            }

        # Create job application service with profile
        job_service = JobApplicationService(driver, profile, job.get('description'))
        
        # Add profile and job data to application_data for reference
        application_data['profile'] = profile
        application_data['job'] = job
        
        if should_submit:
            # This is a submission request - actually apply and submit
            form_questions = job_service.apply(job_url, submit=True, overrided_answers=overrided_answers)
            final_status = ApplicationStatus.APPLIED if form_questions else ApplicationStatus.FAILED
        else:
            # This is just a preparation/save request - apply but don't submit
            form_questions = job_service.apply(job_url, submit=False, overrided_answers=overrided_answers)
            final_status = ApplicationStatus.DRAFT if form_questions else ApplicationStatus.FAILED
            
        # Take screenshot and upload in background (don't wait)
        screenshot_url = None
        try:
            if should_submit:
                # Delete screenshot for submit
                storage_manager.delete_screenshot(user_id, application_id)
            else:
                # Take screenshot for draft/save
                screenshot = take_screenshot(driver, application_id)
                if screenshot:
                    # Upload asynchronously - don't block task completion
                    screenshot_url = storage_manager.upload_screenshot(screenshot, user_id, application_id)
                    # Cleanup immediately
                    try:
                        os.remove(screenshot)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")

        # Single Firestore update with all data
        log_message = "Job application submitted successfully" if (form_questions and should_submit) else \
                     "Job application prepared successfully" if form_questions else \
                     "Job application failed"
        
        firestore_manager.update_application_status(
            user_id,
            application_id,
            final_status,
            form_questions=form_questions,
            screenshot=screenshot_url,
            error_message="" if form_questions else "Application process failed"
        )
        
        if form_questions:
            logger.info(f"Task completed successfully for job {job_id}")
        else:
            logger.error(f"Task failed for job {job_id}: {log_message}")
        
        # Send WebSocket notification (fire-and-forget, don't block)
        try:
            _run_async_websocket(send_job_application_update, user_id, application_id, final_status, {
                "message": log_message,
                "screenshot_url": screenshot_url
            })
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
            _run_async_websocket(send_job_application_update, user_id, application_id, ApplicationStatus.FAILED, {
                "message": error_message
            })
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
    """Take a screenshot of the current page using CDP"""
    try:
        from Screenshot import Screenshot
        ss = Screenshot(driver)

        # Define temp filepath
        filename = f"screenshot_{application_id}.png"
        filepath = os.path.join(tempfile.gettempdir(), filename)

        # Take full page screenshot and save to temp dir
        ss.capture_full_page(
            output_path=filepath,
        )

        return filepath
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return None
