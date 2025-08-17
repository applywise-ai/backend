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
from app.services.job_application.utils import validate_and_convert_form_questions, take_screenshot, cleanup_screenshot

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
        
        driver.set_page_load_timeout(30)
        driver.get(job_url)
        
        # Apply based on job site and whether this is a preparation or submission
        final_status = ApplicationStatus.FAILED
        form_questions = None
        screenshot, screenshot_path = None, None

        # We need to set the cover letter details based on application id
        cover_letter_path = f"cover-letters/{user_id}/{application_id}.pdf"
        if storage_manager.get_download_url_from_path(cover_letter_path):
            profile['coverLetterPath'] = cover_letter_path

        # We need to set the resume details based on application id
        resume_path = f"resumes/{user_id}/{application_id}.pdf"
        if storage_manager.get_download_url_from_path(resume_path):
            profile['resume'] = resume_path

        # We need to set the override answers based on the form questions
        overrided_answers = None
        if overrided_form_questions:
            # Validate and convert form questions before processing
            logger.info(f"Validating {len(overrided_form_questions)} form questions before processing")
            validated_questions = validate_and_convert_form_questions(overrided_form_questions)
            
            overrided_answers = {
                question['unique_label_id']: {
                    "answer": question.get('answer'),
                    "pruned": question.get('pruned')
                } for question in validated_questions
            }
            
            logger.info(f"Processed {len(overrided_answers)} validated override answers")

        # Create job application service with profile
        job_service = JobApplicationService(driver, profile, job.get('description'))
        
        # Add profile and job data to application_data for reference
        application_data['profile'] = profile
        application_data['job'] = job
        
        # Apply to the job (this fills out the form but doesn't submit)
        response = job_service.apply(job_url, overrided_answers=overrided_answers)
        if not response or not response[0]:
            final_status = ApplicationStatus.NOT_FOUND if not response else ApplicationStatus.FAILED
            log_message = "Job no longer exists." if not response else "Job application failed"

            # Send failure WebSocket notification (fire-and-forget)
            try:
                _run_async_websocket(send_job_application_update, user_id, application_id, final_status, {
                    "message": log_message
                })
            except Exception as ws_error:
                logger.error(f"Failure WebSocket notification failed: {ws_error}")

            firestore_manager.update_application_status(
                user_id,
                application_id,
                final_status,
                error_message=log_message
            )
            return {
                "status": final_status,
            }
        
        form_questions, portal_name = response
        
        # Take screenshot before submitting (if this is a submission)
        screenshot_path = None
        submitted_screenshot_path = None
        try:
            screenshot = take_screenshot(driver, application_id, portal_name)
            
            if screenshot:
                # Upload to screenshots folder (before submitting)
                screenshot_path = storage_manager.upload_screenshot(screenshot, user_id, application_id)
                # Cleanup immediately
                cleanup_screenshot(screenshot)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
        
        # Submit if this is a submission request
        if should_submit:
            submit_success = job_service.submit()
            if submit_success:
                final_status = ApplicationStatus.APPLIED
                logger.info(f"Successfully submitted application for job: {job_url}")
                
                # Take screenshot after successful submission
                try:
                    submitted_screenshot = take_screenshot(driver, application_id, portal_name, submit=True)
                    
                    if submitted_screenshot:
                        # Upload to submitted-screenshots folder
                        submitted_screenshot_path = storage_manager.upload_submit_screenshot(submitted_screenshot, user_id, application_id)
                        # Cleanup immediately
                        cleanup_screenshot(submitted_screenshot)
                except Exception as e:
                    logger.error(f"Submitted screenshot failed: {e}")
            else:
                final_status = ApplicationStatus.FAILED
                logger.warning(f"Application prepared but submission failed for job: {job_url}")
        else:
            final_status = ApplicationStatus.DRAFT
            logger.info(f"Successfully prepared application for job: {job_url}")

        # Clean up temporary files
        for file_path in job_service.temp_file_paths:
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to clean up temporary file: {e}")

        # Single Firestore update with all data
        log_message = "Job application submitted successfully" if (form_questions and should_submit and final_status == ApplicationStatus.APPLIED) else \
                     "Job application prepared successfully" if form_questions and final_status == ApplicationStatus.DRAFT else \
                     "Job application failed"
        
        firestore_manager.update_application_status(
            user_id,
            application_id,
            final_status,
            form_questions=form_questions,
            screenshot=screenshot_path,
            submitted_screenshot=submitted_screenshot_path,
            error_message="" if form_questions else "Application process failed"
        )
        
        # Send WebSocket notification (fire-and-forget, don't block)
        try:
            _run_async_websocket(send_job_application_update, user_id, application_id, final_status, {
                "message": log_message,
                "screenshot_path": screenshot_path
            })
        except Exception as e:
            logger.error(f"WebSocket notification failed: {e}")
        
        return {
            "status": final_status,
            "screenshot_path": screenshot_path,
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
