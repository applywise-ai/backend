import os
import uuid
from typing import Optional, List
from datetime import datetime
import logging
import firebase_admin
from firebase_admin import storage, credentials

logger = logging.getLogger(__name__)

# Check if Firebase Admin SDK is available
try:
    from firebase_admin import storage
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("Firebase Admin SDK not available")

from app.core.config import settings


class StorageManager:
    """Manages file uploads to Firebase Storage"""
    
    def __init__(self):
        """Initialize storage client"""
        self.firebase_bucket = None
        self._bucket_initialized = False
    
    def _get_firebase_app(self):
        """Get an existing Firebase app or return None"""
        try:
            # Try to get any existing Firebase app
            apps = firebase_admin._apps
            if apps:
                # Return the first available app
                return list(apps.values())[0]
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting Firebase app: {e}")
            return None
    
    def _ensure_storage_initialized(self):
        """Lazy initialization of Firebase Storage"""
        if self._bucket_initialized:
            return
            
        logger.info("🗄️ Lazy-loading Firebase Storage...")
        try:
            if not FIREBASE_AVAILABLE:
                logger.warning("Firebase Admin SDK not available")
                self._bucket_initialized = True
                return
                
            if not settings.FIREBASE_STORAGE_BUCKET:
                logger.warning("Firebase Storage bucket not configured")
                self._bucket_initialized = True
                return
            
            # Get existing Firebase app
            app = self._get_firebase_app()
            if app:
                self.firebase_bucket = storage.bucket(settings.FIREBASE_STORAGE_BUCKET, app=app)
                logger.info("✅ Firebase Storage initialized successfully using existing app")
            else:
                logger.warning("⚠️ No Firebase app available for Storage initialization")
                self.firebase_bucket = None
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firebase Storage: {e}")
            self.firebase_bucket = None
        finally:
            self._bucket_initialized = True
    
    def upload_screenshot(self, file_path: str, application_id: str) -> Optional[str]:
        """Upload a screenshot to storage"""
        try:
            # Ensure storage is initialized when we actually need it
            self._ensure_storage_initialized()
            
            if not self.firebase_bucket:
                logger.error("Firebase Storage not initialized")
                return None
                
            if not os.path.exists(file_path):
                logger.error(f"Screenshot file not found: {file_path}")
                return None
            
            # Generate unique filename with timestamp
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"screenshots/{application_id}/{timestamp}_{uuid.uuid4().hex[:8]}.png"
            
            # Upload file
            blob = self.firebase_bucket.blob(filename)
            blob.upload_from_filename(file_path)
            
            # Make the blob publicly readable
            blob.make_public()
            
            logger.info(f"📸 Screenshot uploaded successfully: {filename}")
            return blob.public_url
            
        except Exception as e:
            logger.error(f"Failed to upload screenshot: {e}")
            return None
    
    def _upload_to_firebase(self, file_path: str, filename: str) -> Optional[str]:
        """Upload file to Firebase Storage"""
        try:
            # Ensure storage is initialized when we actually need it
            self._ensure_storage_initialized()
            
            if not self.firebase_bucket:
                logger.error("Firebase Storage not initialized")
                return None
                
            blob = self.firebase_bucket.blob(filename)
            blob.upload_from_filename(file_path)
            blob.make_public()
            
            url = blob.public_url
            logger.info(f"Uploaded to Firebase: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Firebase upload failed: {e}")
            return None


# Global storage manager instance
storage_manager = StorageManager() 