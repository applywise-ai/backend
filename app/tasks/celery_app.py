from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "applywise",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.job_application"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,  # Suppress deprecation warning and retain retry behavior
    # Use threads instead of fork to avoid macOS Objective-C runtime issues
    worker_pool='threads',
    worker_concurrency=4,  # Number of threads
)