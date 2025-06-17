from fastapi import APIRouter, Request, HTTPException, Depends
from ...schemas.application import (
    PrepareJobRequest,
    ApplyJobRequest, 
    ApplyJobResponse, 
    ApplicationStatus,
    SaveFormRequest,
    SaveFormResponse
)
from ...services.websocket import websocket_manager
from ...db.firestore import firestore_manager
from ...tasks.job_application import apply_to_job
from ..dependencies import auth_required
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def check_celery_connection():
    """Check if Celery broker is available and workers are running"""
    try:
        from celery import current_app
        
        # Check broker connection
        inspect = current_app.control.inspect()
        
        # Get active workers - this will fail if broker is down
        active_workers = inspect.active()
        
        if not active_workers:
            return False, "No Celery workers are running"
        
        # Check if workers are responding
        stats = inspect.stats()
        if not stats:
            return False, "Celery workers are not responding"
            
        worker_count = len(stats)
        return True, f"Celery is running with {worker_count} worker(s)"
        
    except Exception as e:
        return False, f"Celery broker connection failed: {str(e)}"

def get_user_id(request: Request) -> str:
    """Extract user_id from Firebase token"""
    from firebase_admin import auth
    import firebase_admin
    
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="No authorization header")

    try:
        # Extract token
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        # Get the Firebase app from firestore_manager
        firebase_app = None
        if firestore_manager.app_name:
            try:
                firebase_app = firebase_admin.get_app(firestore_manager.app_name)
            except ValueError:
                pass
        
        if not firebase_app:
            # Fallback: try to get any available Firebase app
            apps = firebase_admin._apps
            if apps:
                firebase_app = list(apps.values())[0]
            else:
                raise HTTPException(status_code=500, detail="No Firebase app available for authentication")

        # Verify token with the specific Firebase app
        decoded_token = auth.verify_id_token(token, app=firebase_app)
        return decoded_token["uid"]

    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired")
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token revoked")
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=500, detail="Token verification failed")

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
        application_id = firestore_manager.create_or_update_application(
            user_id=user_id,
            job_id=job_request.job_id
        )
        
        logger.info(f"Created/updated application: {application_id}")
        
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
@auth_required()
async def submit_application(
    request: Request,
    job_request: ApplyJobRequest,
    user_id: str
):
    """
    Submit a job application that was previously prepared.
    The application will be set to APPLIED status once processing is complete.
    """
    try:
        logger.info(f"Submit endpoint called for user: {user_id}, application: {job_request.application_id}")
        
        # Check Celery connection before proceeding
        celery_ok, celery_message = check_celery_connection()
        if not celery_ok:
            logger.error(f"Celery check failed: {celery_message}")
            raise HTTPException(
                status_code=503, 
                detail=f"Task processing service unavailable: {celery_message}"
            )
        
        logger.info(f"Celery status: {celery_message}")
        
        # Verify application exists and belongs to user
        application = firestore_manager.get_application(user_id, job_request.application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Queue the task
        task_data = {
            'user_id': user_id,
            'application_id': job_request.application_id,
            'job_id': job_request.job_id,
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
@auth_required()
async def save_form_questions(
    request: Request,
    save_request: SaveFormRequest,
    user_id: str
):
    """
    Save custom form questions for a job application and process it.
    These questions will override the default form filling in the job application task.
    """
    try:
        # TODO: Validate form questions
        
        # Update application with form questions
        firestore_manager.update_application_status(
            user_id,
            save_request.application_id,
            ApplicationStatus.PENDING,
            form_questions=save_request.form_questions
        )
        
        # Queue the task with the custom form questions
        apply_to_job.delay({
            'user_id': user_id,
            'application_id': save_request.application_id,
            'job_id': save_request.job_id,
            'override_form_questions': True,
            'form_questions': save_request.form_questions
        })
        
        return SaveFormResponse(
            application_id=save_request.application_id,
            status=ApplicationStatus.PENDING,
            message="Form questions saved and processing started"
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
        from datetime import datetime
        
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