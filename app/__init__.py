import logging
import sys

# Configure logging early in the import process
# This ensures startup logs from modules like firestore.py are captured
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Ensure logs go to stdout
        logging.FileHandler('app.log', mode='a')  # Also log to file
    ]
)

# Set specific loggers to INFO level
logging.getLogger('app').setLevel(logging.INFO)
logging.getLogger('app.api').setLevel(logging.INFO)
logging.getLogger('app.tasks').setLevel(logging.INFO)
logging.getLogger('app.db').setLevel(logging.INFO)
logging.getLogger('app.services').setLevel(logging.INFO)

# Reduce noise from other libraries
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('google.auth').setLevel(logging.WARNING)
logging.getLogger('google.cloud').setLevel(logging.WARNING)
logging.getLogger('firebase_admin').setLevel(logging.WARNING)

# Create a logger for this module
logger = logging.getLogger(__name__)
logger.info("Logging configuration initialized")

# Import managers in the correct order to ensure proper Firebase app initialization
# Firestore Manager must be imported first to create the Firebase app
try:
    from app.db.firestore import firestore_manager
    logger.info("✅ Firestore Manager initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize Firestore Manager: {e}")

try:
    from app.services.storage import storage_manager
    logger.info("✅ Storage Manager initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize Storage Manager: {e}") 