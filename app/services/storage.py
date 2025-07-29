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
        self.resume_path = "resumes"
        self.cover_letter_path = "cover-letters"
        self.screenshot_path = "screenshots"

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
    
    def upload_screenshot(self, file_path: str, user_id: str, application_id: str) -> Optional[str]:
        """Upload a screenshot to storage - stores one screenshot per application ID"""
        # Use consistent filename format: screenshots/{user_id}/{application_id}.png
        filename = f"{self.screenshot_path}/{user_id}/{application_id}.png"
        return self._upload_file(file_path, filename)
    
    def delete_screenshot(self, user_id: str, application_id: str) -> Optional[str]:
        """Delete a screenshot from storage and return the URL that was deleted"""
        try:
            # Ensure storage is initialized when we actually need it
            self._ensure_storage_initialized()
            
            if not self.firebase_bucket:
                logger.error("Firebase Storage not initialized")
                return None
            
            # Use consistent filename format: screenshots/{user_id}/{application_id}.png
            filename = f"{self.screenshot_path}/{user_id}/{application_id}.png"
            blob = self.firebase_bucket.blob(filename)
            
            if blob.exists():
                # Get the URL before deleting
                url = blob.public_url
                # Delete the blob
                blob.delete()
                logger.info(f"Deleted screenshot from Firebase: {url}")
            else:
                logger.info(f"Screenshot not found for deletion: {filename}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to delete screenshot: {e}")
            return None
    
    def upload_cover_letter(self, file_path: str, user_id: str, application_id: str) -> Optional[str]:
        """Upload a cover letter to storage - stores one cover letter per application ID"""
        # Use consistent filename format: cover-letters/{user_id}/{application_id}.pdf
        filename = f"{self.cover_letter_path}/{user_id}/{application_id}.pdf"
        return self._upload_file(file_path, filename)

    def _upload_file(self, file_path: str, filename: str) -> Optional[str]:
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
    
    def get_download_info(self, path: str) -> tuple[str, str]:
        """
        Get a download URL and original filename for a file in Firebase Storage
        
        Returns:
            tuple: (download_url, original_filename) or (None, None) if not found
        """
        try:
            # Ensure storage is initialized when we actually need it
            self._ensure_storage_initialized()
            
            if not self.firebase_bucket:
                logger.error("Firebase Storage not initialized")
                return None, None
            
            blob = self.firebase_bucket.blob(path)
            if not blob.exists():
                logger.error(f"File does not exist: {path}")
                return None, None
                
            # Get the download URL
            blob.make_public()  # Optional: only if you're not using signed URLs
            download_url = blob.public_url
            
            # Get the original filename from metadata
            original_filename = None
            try:
                metadata = blob.metadata
                if metadata and 'customMetadata' in metadata:
                    custom_metadata = metadata['customMetadata']
                    if 'originalName' in custom_metadata:
                        original_filename = custom_metadata['originalName']
            except Exception as e:
                logger.warning(f"Could not retrieve original filename from metadata: {e}")
                # Fallback: extract filename from path
                original_filename = path.split('/')[-1] if '/' in path else path
            
            return download_url, original_filename
            
        except Exception as e:
            logger.error(f"Failed to get download URL: {e}")
            return None, None
    
    def get_cover_letter(self, user_id: str, application_id: str) -> tuple[str, str]:
        """
        Get a download URL and original filename for a cover letter in Firebase Storage
        
        Returns:
            tuple: (download_url, original_filename) or (None, None) if not found
        """
        filename = f"{self.cover_letter_path}/{user_id}/{application_id}.pdf"
        return self.get_download_info(filename)

    def get_resume(self, user_id: str, application_id: str) -> tuple[str, str]:
        """
        Get a download URL and original filename for a resume in Firebase Storage
        
        Returns:
            tuple: (download_url, original_filename) or (None, None) if not found
        """
        filename = f"{self.resume_path}/{user_id}/{application_id}.pdf"
        return self.get_download_info(filename)


# Global storage manager instance
storage_manager = StorageManager() 