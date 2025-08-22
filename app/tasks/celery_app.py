from celery import Celery
from app.core.config import settings
import logging
import ssl

logger = logging.getLogger(__name__)

# Log the Redis URLs being used
logger.info(f"🔧 Celery Broker URL: {settings.CELERY_BROKER_URL}")
logger.info(f"🔧 Celery Result Backend: {settings.CELERY_RESULT_BACKEND}")

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
    # Optimize Redis usage to reduce reads
    result_expires=3600,  # Results expire after 1 hour
    task_ignore_result=False,  # Keep results for status checking
    task_store_eager_result=True,  # Store results immediately
    # Reduce Celery polling frequency
    broker_transport_options={
        'visibility_timeout': 3600,  # 1 hour
        'fanout_prefix': True,
        'fanout_patterns': True,
    },
    # Optimize worker polling behavior
    worker_disable_rate_limits=True,
    task_acks_late=True,  # Acknowledge tasks only after completion
    worker_send_task_events=False,  # Disable task events to reduce Redis writes
    task_send_sent_event=False,  # Don't send task-sent events
    broker_connection_retry_on_startup=True,  # Suppress deprecation warning and retain retry behavior
    # Use threads instead of fork to avoid macOS Objective-C runtime issues
    worker_pool='threads',
    worker_concurrency=4,  # Number of threads
    # SSL configuration for rediss:// URLs (Upstash Redis)
    broker_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE,
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
        'ssl_check_hostname': False,
    },
    redis_backend_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE,
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
        'ssl_check_hostname': False,
    },
)