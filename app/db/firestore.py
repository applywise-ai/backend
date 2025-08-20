import logging
import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import firebase_admin
from firebase_admin import credentials
from app.core.config import settings
from app.schemas.application import ApplicationStatus

logger = logging.getLogger(__name__)


class FirestoreManager:
    """Manages Firestore operations for user applications"""
    
    def __init__(self):
        self.db = None
        self.app_name = self._get_app_name()
        self._initialize_firestore()
    
    def _get_app_name(self) -> str:
        """Generate a unique app name based on the process type"""
        # Check if we're running in a Celery worker
        if 'celery' in os.environ.get('_', '').lower() or 'worker' in os.environ.get('_', '').lower():
            return f"celery-{os.getpid()}"
        else:
            return f"api-{os.getpid()}"
    
    def _initialize_firestore(self):
        """Initialize Firestore client"""
        logger.info(f"🔥 Starting Firestore initialization for app: {self.app_name}")
        try:
            # Check if our specific app is already initialized
            try:
                app = firebase_admin.get_app(self.app_name)
                logger.info(f"✅ Firebase app '{self.app_name}' already initialized, reusing existing app")
            except ValueError:
                # Our app doesn't exist, so we can initialize it
                if settings.FIREBASE_CREDENTIALS:
                    logger.info("🔑 Loading Firebase credentials from environment variable")
                    try:
                        # Parse the JSON credentials from the environment variable
                        credentials_dict = json.loads(settings.FIREBASE_CREDENTIALS)
                        
                        # Handle potential private key formatting issues
                        if 'private_key' in credentials_dict:
                            # Replace literal \n with actual newlines if they exist
                            private_key = credentials_dict['private_key']
                            if '\\n' in private_key:
                                credentials_dict['private_key'] = private_key.replace('\\n', '\n')
                        
                        cred = credentials.Certificate(credentials_dict)
                        firebase_admin.initialize_app(cred, name=self.app_name)
                        logger.info(f"✅ Firebase Admin SDK initialized with service account credentials (app: {self.app_name})")
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON format in FIREBASE_CREDENTIALS: {e}"
                        logger.error(f"❌ {error_msg}")
                        raise Exception(error_msg)
                    except Exception as e:
                        error_msg = f"Failed to initialize Firebase with credentials: {e}"
                        logger.error(f"❌ {error_msg}")
                        raise Exception(error_msg)
                else:
                    logger.info("🔑 No Firebase credentials found, using default credentials")
                    firebase_admin.initialize_app(name=self.app_name)
                    logger.info(f"✅ Firebase Admin SDK initialized with default credentials (app: {self.app_name})")
            
            self.db = firestore.client(app=firebase_admin.get_app(self.app_name))
            logger.info("🎯 Firestore client created successfully")
            logger.info("✅ Firestore initialization completed successfully")
            
        except ValueError as e:
            error_msg = f"Invalid Firebase credentials format: {e}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firestore: {e}")
            raise
    
    def get_existing_application(self, user_id: str, job_id: str) -> Optional[Dict]:
        """
        Check if user already has an application for the given job
        """
        try:
            query = (
                self.db.collection('users')
                .document(user_id)
                .collection('applications')
                .where(filter=FieldFilter('jobId', '==', job_id))
                .limit(1)
            )
            
            results = query.get()
            
            for doc in results:
                app_data = doc.to_dict()
                app_data['id'] = doc.id
                return app_data
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to check for existing application: {e}")
            return None
    
    def update_application_status(
        self, 
        user_id: str, 
        application_id: str, 
        status: str,
        form_questions: Optional[Dict] = None,
        error_message: Optional[str] = None,
        screenshot: Optional[str] = None,
        submitted_screenshot: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> bool:
        """
        Update the status of an application
        """
        try:
            # Build update data
            update_data = {
                'status': status,
                'lastUpdated': datetime.utcnow()
            }
                
            if form_questions is not None:
                update_data['formQuestions'] = form_questions
                
            if error_message is not None:
                update_data['errorMessage'] = error_message
                
            if screenshot is not None:
                update_data['screenshot'] = screenshot
                
            if submitted_screenshot is not None:
                update_data['submittedScreenshot'] = submitted_screenshot
                
            if task_id is not None:
                update_data['taskId'] = task_id
            
            # Update the application in the user's subcollection
            app_ref = (self.db.collection('users')
                      .document(user_id)
                      .collection('applications')
                      .document(application_id))
            app_ref.update(update_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update application status: {e}")
            return False

    def update_application(
        self, 
        user_id: str, 
        application_id: str, 
        form_questions: Dict[str, Any]
    ) -> bool:
        """
        Update an application's form questions and last updated timestamp
        
        Args:
            user_id: The user ID
            application_id: The application ID
            form_questions: Dictionary containing the form questions to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            update_data = {
                'formQuestions': form_questions,
                'lastUpdated': datetime.utcnow()
            }
            
            # Update the application in the user's subcollection
            app_ref = (self.db.collection('users')
                      .document(user_id)
                      .collection('applications')
                      .document(application_id))
            
            app_ref.update(update_data)
            
            logger.info(f"Successfully updated application {application_id} form questions for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update application {application_id} for user {user_id}: {e}")
            return False

    def get_application(self, user_id: str, application_id: str) -> Optional[Dict[str, Any]]:
        """Get application by ID"""
        try:
            doc_ref = (self.db.collection('users')
                      .document(user_id)
                      .collection('applications')
                      .document(application_id))
            doc = doc_ref.get()
            
            if doc.exists:
                app_data = doc.to_dict()
                app_data['id'] = doc.id
                return app_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting application: {e}")
            return None
    
    def get_job_id_by_application_id(self, user_id: str, application_id: str) -> Optional[str]:
        """Get job_id by application_id"""
        try:
            application = self.get_application(user_id, application_id)
            if application:
                return application.get('jobId')
            return None
            
        except Exception as e:
            logger.error(f"Error getting job_id for application {application_id}: {e}")
            return None
    
    def add_application_log(self, user_id: str, application_id: str, level: str, message: str):
        """Add a log entry to an application"""
        try:
            log_data = {
                'level': level,
                'message': message,
                'timestamp': datetime.utcnow()
            }
            
            # Add to logs subcollection under the application
            logs_ref = (self.db.collection('users')
                       .document(user_id)
                       .collection('applications')
                       .document(application_id)
                       .collection('logs'))
            
            logs_ref.add(log_data)
            logger.debug(f"Added log to application {application_id}: {level} - {message}")
            
        except Exception as e:
            logger.error(f"Error adding application log: {e}")

    def get_profile(self, user_id: str) -> Optional[Dict]:
        """
        Get user profile data
        """
        try:
            doc_ref = self.db.collection('users').document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

    def update_profile(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update user profile data
        
        Args:
            user_id: The user ID
            update_data: Dictionary containing the fields to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Add lastUpdated timestamp
            update_data['lastUpdated'] = datetime.utcnow()
            
            # Update the user document
            user_ref = self.db.collection('users').document(user_id)
            user_ref.update(update_data)
            
            logger.info(f"Successfully updated profile for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update profile for user {user_id}: {e}")
            return False

    def deduct_ai_credit(self, user_id: str) -> bool:
        """
        Deduct one AI credit from user's profile
        
        Args:
            user_id: The user ID
            
        Returns:
            bool: True if deduction was successful, False otherwise
        """
        try:
            # Get current profile
            profile = self.get_profile(user_id)
            if not profile:
                logger.error(f"User profile not found for user {user_id}")
                return False
            
            # Get current AI credits
            current_credits = profile.get('aiCredits', 0)
            
            if current_credits <= 0:
                logger.warning(f"User {user_id} has no AI credits remaining")
                return False
            
            # Deduct one credit
            new_credits = current_credits - 1
            
            # Update the profile
            update_data = {'aiCredits': new_credits}
            success = self.update_profile(user_id, update_data)
            
            if success:
                logger.info(f"Successfully deducted AI credit for user {user_id}. Credits remaining: {new_credits}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to deduct AI credit for user {user_id}: {e}")
            return False

    def create_or_update_application(
        self,
        user_id: str,
        job_id: str,
    ) -> tuple[str, bool]:
        """
        Create a new application or return existing one for the same job
        Returns a tuple of (application_id, is_new_application)
        """
        try:
            # Check if application already exists for this job
            existing_app = self.get_existing_application(user_id, job_id)
            
            if existing_app:
                logger.info(f"Found existing application {existing_app['id']} for job {job_id}")
                return existing_app['id'], False
            
            # Create new application
            application_data = {
                'jobId': job_id,
                'status': ApplicationStatus.PENDING,
                'createdAt': datetime.utcnow(),
                'lastUpdated': datetime.utcnow()
            }
            
            # Add to user's applications subcollection
            app_ref = (self.db.collection('users')
                      .document(user_id)
                      .collection('applications')
                      .add(application_data))
            
            application_id = app_ref[1].id
            logger.info(f"Created new application {application_id} for job {job_id}")
            
            return application_id, True
            
        except Exception as e:
            logger.error(f"Failed to create/update application: {e}")
            raise

    def get_stripe_customer(self, user_id: str) -> Optional[str]:
        """Get Stripe customer ID from Firestore stripe_customers table"""
        try:
            doc_ref = self.db.collection('stripe_customers').document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return data.get('customer_id')
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving Stripe customer from Firestore: {e}")
            raise

    def store_stripe_customer(self, user_id: str, customer_id: str) -> None:
        """Store Stripe customer ID in Firestore stripe_customers table"""
        try:
            doc_ref = self.db.collection('stripe_customers').document(user_id)
            doc_ref.set({
                'customer_id': customer_id,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            })
            
            logger.info(f"Stored Stripe customer {customer_id} for user {user_id} in Firestore")
            
        except Exception as e:
            logger.error(f"Error storing Stripe customer in Firestore: {e}")
            raise

    def get_active_subscription_id(self, user_id: str) -> Optional[str]:
        """Get active subscription ID from Firestore stripe_customers table"""
        try:
            doc_ref = self.db.collection('stripe_customers').document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return data.get('activeSubscriptionId')
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving active subscription ID from Firestore: {e}")
            raise

    def update_subscription_id(self, user_id: str, subscription_id: Optional[str] = None) -> None:
        """Update active subscription ID in Firestore stripe_customers table"""
        try:
            doc_ref = self.db.collection('stripe_customers').document(user_id)
            
            # Get existing data to preserve it
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
            else:
                data = {}
            
            # Update subscription ID and timestamp
            data.update({
                'activeSubscriptionId': subscription_id,
                'updated_at': datetime.utcnow()
            })
            
            doc_ref.set(data)
            
            logger.info(f"Updated subscription ID for user {user_id}: {subscription_id}")
            
        except Exception as e:
            logger.error(f"Error updating subscription ID in Firestore: {e}")
            raise

    def set_pro_member_status(self, user_id: str, is_pro: bool) -> None:
        """Set isProMember status in users table"""
        try:
            # Update isProMember in users collection
            user_doc_ref = self.db.collection('users').document(user_id)
            user_doc_ref.update({
                'isProMember': is_pro,
                'updated_at': datetime.utcnow()
            })
            
            logger.info(f"Set isProMember to {is_pro} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error setting pro member status in Firestore: {e}")
            raise

    def get_user_by_customer_id(self, customer_id: str) -> Optional[str]:
        """Get user_id by Stripe customer_id"""
        try:
            # Query the stripe_customers collection to find the user with this customer_id
            query = self.db.collection('stripe_customers').where('customer_id', '==', customer_id).limit(1)
            docs = query.get()
            
            for doc in docs:
                return doc.id  # The document ID is the user_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by customer ID: {e}")
            raise

    def delete_stripe_customer(self, user_id: str) -> bool:
        """Delete Stripe customer record from Firestore"""
        try:
            doc_ref = self.db.collection('stripe_customers').document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_ref.delete()
                logger.info(f"Deleted Stripe customer record for user {user_id} from Firestore")
                return True
            else:
                logger.warning(f"No Stripe customer record found for user {user_id} in Firestore")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting Stripe customer from Firestore: {e}")
            raise

    def cleanup(self):
        """Clean up Firebase app resources"""
        try:
            if self.app_name:
                app = firebase_admin.get_app(self.app_name)
                firebase_admin.delete_app(app)
                logger.info(f"🧹 Firebase app '{self.app_name}' cleaned up successfully")
        except ValueError:
            # App doesn't exist, nothing to clean up
            pass
        except Exception as e:
            logger.error(f"❌ Error cleaning up Firebase app: {e}")


# Create global instance
firestore_manager = FirestoreManager() 