from fastapi import APIRouter, HTTPException, Depends
from ...schemas.application import (
    PrepareJobRequest,
    ApplyJobRequest, 
    ApplyJobResponse, 
    ApplicationStatus,
    SaveFormRequest,
    SaveFormResponse,
    GenerateCoverLetterRequest,
    GenerateCoverLetterResponse,
    GenerateCustomAnswerRequest,
    GenerateCustomAnswerResponse
)
from ...db.firestore import firestore_manager
from ...db.supabase import supabase_manager
from ...tasks.job_application import apply_to_job
from ..dependencies import get_user_id
from ...services.storage import storage_manager
from ...services.ai_assistant import AIAssistant
from ...schemas.application import QuestionType
from ...services.pdf_generator import pdf_generator
import logging
import tempfile
import os
from datetime import datetime
from app.services.job_application.utils import validate_and_convert_form_questions

router = APIRouter()
logger = logging.getLogger(__name__)

def check_celery_connection():
    """Check if Celery broker is available and workers are running
    Optimized to reduce Redis reads by limiting inspection calls
    """
    try:
        from celery import current_app
        
        # Simplified check - just ping workers (fewer Redis operations)
        inspect = current_app.control.inspect(timeout=1.0)  # Short timeout
        
        # Use ping instead of active() - much lighter on Redis
        pong = inspect.ping()
        
        if not pong:
            return False, "No Celery workers are responding to ping"
            
        worker_count = len(pong)
        return True, f"Celery is running with {worker_count} worker(s)"
        
    except Exception as e:
        return False, f"Celery broker connection failed: {str(e)}"



@router.post("/prepare", response_model=ApplyJobResponse)
async def prepare_application(
    job_request: PrepareJobRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Prepare a job application by extracting form fields.
    The application will be set to DRAFT status once processing is complete.
    
    Note: This endpoint will queue the task even if Celery workers are down.
    Use the /health endpoint to check system status, and /status/{application_id} 
    to monitor task progress.
    """
    try:
        logger.info(f"Prepare endpoint called for user: {user_id}, job: {job_request.job_id}")
        
        # Create or update application
        application_id, is_new_application = firestore_manager.create_or_update_application(
            user_id=user_id,
            job_id=job_request.job_id
        )
        
        logger.info(f"Created/updated application: {application_id} (new: {is_new_application})")
        
        # Deduct AI credit if this is a new application
        if is_new_application:
            credit_deducted = firestore_manager.deduct_ai_credit(user_id)
            if credit_deducted:
                logger.info(f"AI credit deducted for new application {application_id}")
            else:
                logger.warning(f"Failed to deduct AI credit for new application {application_id}")
        
        # Queue the task (will succeed even if Celery is down)
        task_data = {
            'user_id': user_id,
            'application_id': application_id,
            'job_id': job_request.job_id
        }
        
        logger.info(f"Queuing task with data: {task_data}")
        task = apply_to_job.delay(task_data)
        
        # Store task ID in the application for tracking
        firestore_manager.update_application_status(
            user_id,
            application_id,
            ApplicationStatus.PENDING,
            task_id=task.id
        )
        
        logger.info(f"Task queued successfully with ID: {task.id}")
        
        return ApplyJobResponse(
            application_id=application_id,
            status=ApplicationStatus.PENDING,
            message=f"Job application preparation started (Task ID: {task.id})"
        )
        
    except Exception as e:
        logger.error(f"Failed to prepare job application: {e}")
        if 'application_id' in locals():
            # Update application status to FAILED if we got far enough to create it
            firestore_manager.update_application_status(
                user_id,
                application_id,
                ApplicationStatus.FAILED,
                error_message=f"Failed to prepare application: {str(e)}"
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit", response_model=ApplyJobResponse)
async def submit_application(
    job_request: ApplyJobRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Submit a job application that was previously prepared.
    The application will be set to APPLIED status once processing is complete.
    """
    try:
        logger.info(f"Submit endpoint called for user: {user_id}, application: {job_request.application_id}")
        
        # Verify application exists and belongs to user
        application = firestore_manager.get_application(user_id, job_request.application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Get job_id from the application
        job_id = application.get('jobId')
        if not job_id:
            raise HTTPException(status_code=404, detail="Job ID not found in application")
        
        # Queue the task
        task_data = {
            'user_id': user_id,
            'application_id': job_request.application_id,
            'job_id': job_id,
            'form_questions': application.get('formQuestions', None),
            'should_submit': True  # Flag to indicate this is a submission
        }
        
        logger.info(f"Queuing submit task with data: {task_data}")
        task = apply_to_job.delay(task_data)
        
        # Update application with new task ID
        firestore_manager.update_application_status(
            user_id,
            job_request.application_id,
            ApplicationStatus.PENDING,
            task_id=task.id
        )
        
        logger.info(f"Submit task queued successfully with ID: {task.id}")
        
        return ApplyJobResponse(
            application_id=job_request.application_id,
            status=ApplicationStatus.PENDING,
            message=f"Job application submission started (Task ID: {task.id})"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit job application: {e}")
        # Update application status to FAILED
        firestore_manager.update_application_status(
            user_id,
            job_request.application_id,
            ApplicationStatus.FAILED,
            error_message=f"Failed to submit application: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/save", response_model=SaveFormResponse)
async def save_form_questions(
    save_request: SaveFormRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Save custom form questions for a job application.
    These questions will override the default form filling in the job application task.
    """
    try:
        # Convert FormQuestion objects to dictionaries for JSON serialization
        form_questions_dict = [question.dict() for question in save_request.form_questions]

        # If question is pruned and multi-select we need to split answer by commas
        for question in form_questions_dict:
            if question.get('pruned') and question.get('type') == QuestionType.MULTISELECT:
                question['answer'] = question['answer'].split(',')
        
        # Validate and convert form questions
        logger.info(f"Validating {len(form_questions_dict)} form questions for application {save_request.application_id}")
        validated_questions = validate_and_convert_form_questions(form_questions_dict)
        for question in validated_questions:
            logger.info(f"Validated question: {question.get('unique_label_id')} -> {question.get('answer')} type: {type(question.get('answer'))}")
        # Update application with validated form questions
        firestore_manager.update_application(
            user_id,
            save_request.application_id,
            form_questions=validated_questions
        )
        
        return SaveFormResponse(
            application_id=save_request.application_id,
            status=ApplicationStatus.DRAFT,
            message="Form questions saved and validated"
        )
        
    except Exception as e:
        logger.error(f"Failed to save form questions: {e}")
        # Update application status to FAILED
        firestore_manager.update_application_status(
            user_id,
            save_request.application_id,
            ApplicationStatus.FAILED,
            error_message=f"Failed to save form questions: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{application_id}", response_model=dict)
async def get_application_status(
    application_id: str,
    user_id: str = Depends(get_user_id)
):
    """
    Get the status of a job application and its associated task
    Optimized to reduce Redis reads by caching completed task results
    """
    try:
        # Get application from Firestore
        application = firestore_manager.get_application(user_id, application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        response = {
            "application_id": application_id,
            "status": application.get('status'),
            "last_updated": application.get('lastUpdated'),
            "created_at": application.get('createdAt'),
            "error_message": application.get('errorMessage'),
            "task_status": None,
            "task_result": None
        }
        
        # Check Celery task status if task_id exists
        task_id = application.get('taskId')
        if task_id:
            from celery.result import AsyncResult
            
            # Only check Redis if task is not in a final state
            app_status = application.get('status')
            if app_status in ['COMPLETED', 'APPLIED', 'FAILED']:
                # Task is done, use cached status from Firestore instead of Redis
                response.update({
                    "task_id": task_id,
                    "task_status": app_status,
                    "task_result": "Task completed - check application status",
                    "task_info": {
                        "ready": True,
                        "successful": app_status in ['COMPLETED', 'APPLIED'],
                        "failed": app_status == 'FAILED',
                    }
                })
            else:
                # Task still running, check Redis (but limit frequency)
                task_result = AsyncResult(task_id)
                
                response.update({
                    "task_id": task_id,
                    "task_status": task_result.status,
                    "task_result": task_result.result if task_result.ready() else None,
                    "task_info": {
                        "ready": task_result.ready(),
                        "successful": task_result.successful() if task_result.ready() else None,
                        "failed": task_result.failed() if task_result.ready() else None,
                    }
                })
                
                if task_result.failed():
                    response["task_error"] = str(task_result.result)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get application status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """
    Health check endpoint to monitor system status including Celery workers
    """
    try:
        # Check Celery status
        celery_ok, celery_message = check_celery_connection()
        
        # Check Firestore connection
        firestore_ok = True
        firestore_message = "Firestore connection healthy"
        try:
            # Simple test query to verify Firestore is accessible
            test_ref = firestore_manager.db.collection('_health_check').limit(1)
            list(test_ref.get())  # This will fail if Firestore is down
        except Exception as e:
            firestore_ok = False
            firestore_message = f"Firestore connection failed: {str(e)}"
        
        overall_status = "healthy" if (celery_ok and firestore_ok) else "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "celery": {
                    "status": "healthy" if celery_ok else "unhealthy",
                    "message": celery_message
                },
                "firestore": {
                    "status": "healthy" if firestore_ok else "unhealthy", 
                    "message": firestore_message
                }
            },
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "version": "1.0.0"
        } 


@router.post("/generate-cover-letter", response_model=GenerateCoverLetterResponse)
async def generate_cover_letter(
    request: GenerateCoverLetterRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Generate a cover letter using AI and upload it to storage
    
    Args:
        request: Cover letter generation request with job_id and optional prompt
        user_id: User ID from authentication
        
    Returns:
        GenerateCoverLetterResponse with cover letter text and URL
    """
    try:
        # Get user profile
        profile = firestore_manager.get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        # Check if user is pro member (required for cover letter generation)
        if not profile.get('isProMember', False):
            raise HTTPException(status_code=403, detail="Cover letter generation is only available for Pro members")
        
        # Get job description from postgres using job_id
        job_data = supabase_manager.get_job_by_id(request.job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_description = job_data.get('description', '')
        if not job_description:
            raise HTTPException(status_code=400, detail="Job description not available")
        
        # Get application from firestore using application_id
        application_id, _ = firestore_manager.create_or_update_application(
            user_id=user_id,
            job_id=request.job_id
        )

        # Initialize AI assistant with profile and job description
        ai_assistant = AIAssistant(profile, job_description)
        
        # Generate cover letter text with optional custom prompt
        cover_letter_text = ai_assistant.generate_cover_letter(request.prompt)

        if not cover_letter_text:
            raise HTTPException(status_code=500, detail="Failed to generate cover letter")
        
        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Create PDF from text
        if not pdf_generator.create_pdf_from_text(cover_letter_text, tmp_path, profile):
            os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail="Failed to create PDF")
        
        # Upload to storage
        cover_letter_path = storage_manager.upload_cover_letter(tmp_path, user_id, application_id)
        
        # Clean up temporary file
        os.unlink(tmp_path)
        
        if not cover_letter_path:
            raise HTTPException(status_code=500, detail="Failed to upload cover letter")
        
        logger.info(f"Cover letter generated successfully for user {user_id}, job {request.job_id}, application {application_id}")
        
        return GenerateCoverLetterResponse(
            application_id=application_id,
            cover_letter_path=cover_letter_path,
            message="Cover letter generated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating cover letter: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/generate-custom-answer", response_model=GenerateCustomAnswerResponse)
async def generate_custom_answer(
    request: GenerateCustomAnswerRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Generate a custom answer using AI assistant
    
    Args:
        request: Custom answer generation request with job_description, question, and optional prompt
        user_id: User ID from authentication
        
    Returns:
        GenerateCustomAnswerResponse with generated answer
    """
    try:
        # Get user profile
        profile = firestore_manager.get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        # Check if user is pro member (required for AI custom answer generation)
        if not profile.get('isProMember', False):
            raise HTTPException(status_code=403, detail="AI custom answer generation is only available for Pro members")
        
        # Use job description directly from request
        job_description = request.job_description
        if not job_description:
            raise HTTPException(status_code=400, detail="Job description is required")

        # Initialize AI assistant with profile and job description
        ai_assistant = AIAssistant(profile, job_description)
        
        # Generate custom answer with the question and optional custom prompt
        ai_result = ai_assistant.answer_question(
            question=request.question,
            field_type=QuestionType.TEXTAREA,
            custom_prompt=request.prompt
        )

        if not ai_result:
            raise HTTPException(status_code=500, detail="Failed to generate custom answer")
        
        # Unpack the tuple (answer, is_open_ended)
        answer, is_open_ended = ai_result
        
        logger.info(f"Custom answer generated successfully for user {user_id}, question: {request.question[:50]}...")
        
        return GenerateCustomAnswerResponse(
            answer=answer,
            message="Custom answer generated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating custom answer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 