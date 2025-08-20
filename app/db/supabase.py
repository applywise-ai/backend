import logging
from typing import Dict, Any, Optional
from app.core.config import settings
import numpy as np
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import uuid


def is_effectively_empty(val):
    """
    Safely check if a value is null, empty, or effectively empty.
    
    Args:
        val: Value to check
        
    Returns:
        bool: True if the value is effectively empty, False otherwise
    """
    if isinstance(val, (list, tuple, set, dict, np.ndarray, pd.Series)):
        return len(val) == 0
    return pd.isna(val) or val is None or val == ""

logger = logging.getLogger(__name__)

class SupabaseManager:
    """Manages Supabase database operations using native Supabase client"""
    
    def __init__(self):
        """Initialize Supabase client"""
        logger.info("🚀 Starting Supabase initialization...")
        try:
            if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be provided")
            
            logger.info("📡 Connecting to Supabase")
            
            # Create client with simple initialization
            self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            
            # Test the connection
            try:
                # Simple test query to verify connection
                result = self.client.table('jobs').select('id').limit(1).execute()
                logger.info("✅ Supabase connection initialized successfully")
            except Exception as e:
                logger.warning("Connection test failed, but client initialized: %s", e)
                logger.info("✅ Supabase client initialized (table may not exist yet)")
                
        except Exception as e:
            logger.error("❌ Failed to initialize Supabase connection: %s", e)
            raise

    def get_session(self):
        """Get a database session - for compatibility with SQLAlchemy interface"""
        # Since Supabase doesn't use sessions like SQLAlchemy, we'll return the client
        # This is mainly for compatibility with existing FastAPI dependency injection
        class MockSession:
            def __init__(self, client):
                self.client = client
            
            def close(self):
                pass  # Supabase client doesn't need explicit closing
        
        try:
            yield MockSession(self.client)
        finally:
            pass

    def cleanup(self):
        """Cleanup database connections"""
        try:
            logger.info("🧹 Cleaning up Supabase connections...")
            # Supabase client handles connection pooling automatically
            logger.info("✅ Supabase connections cleaned up")
        except Exception as e:
            logger.error("❌ Error cleaning up Supabase connections: %s", e)

    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by its ID"""
        try:
            logger.debug("Fetching job with ID: %s", job_id)
            
            result = self.client.table('jobs').select('*').eq('id', job_id).execute()
            
            if result.data and len(result.data) > 0:
                job_data = result.data[0]
                logger.debug("Found job %s: %s at %s", job_id, job_data.get('title'), job_data.get('company'))
                return job_data
            else:
                logger.warning("Job with ID %s not found", job_id)
                return None
                
        except Exception as e:
            logger.error("Database error getting job %s: %s", job_id, e)
            return None
    
    def close(self):
        """Close the database connection - for compatibility"""
        # Supabase client handles connections automatically
        logger.info("Supabase connection closed")
    
    def upload_jobs_dataframe(self, jobs_df, column_mapping: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Upload a pandas DataFrame to the jobs table using column mapping.
        
        Args:
            jobs_df: pandas DataFrame containing job data
            column_mapping: Dictionary mapping DataFrame columns to database columns
            
        Returns:
            Dict containing upload statistics
        """
        stats = {
            'total_rows': len(jobs_df),
            'successful_uploads': 0,
            'failed_uploads': 0,
            'skipped_duplicates': 0,
            'errors': []
        }
        
        try:
            logger.info("Starting upload of %d jobs to Supabase database", len(jobs_df))
            
            # Prepare job data for all rows
            jobs_to_insert = []
            
            for index, row in jobs_df.iterrows():
                try:
                    # Create job data dictionary using column mapping
                    job_data = {}
                    
                    # Map columns according to the mapping
                    for df_col, db_col in column_mapping.items():
                        if df_col in jobs_df.columns:
                            value = row[df_col]
                            # Safely check if value is not null/na
                            if not is_effectively_empty(value):
                                job_data[db_col] = value
                    
                    # Handle special cases and defaults
                    if 'id' not in job_data:
                        job_data['id'] = str(uuid.uuid4())
                    
                    # Ensure required fields have defaults
                    if 'title' not in job_data or is_effectively_empty(job_data['title']):
                        job_data['title'] = f"Job {index + 1}"
                    
                    if 'company' not in job_data or is_effectively_empty(job_data['company']):
                        job_data['company'] = "Unknown Company"
                    
                    # Handle JSON fields
                    json_fields = ['responsibilities', 'requirements', 'skills', 'tags']
                    for field in json_fields:
                        if field in job_data and is_effectively_empty(job_data[field]):
                            job_data[field] = []
                        elif field in job_data and not isinstance(job_data[field], list):
                            # Convert to string first to handle pandas objects
                            job_data[field] = [str(job_data[field])]
                    
                    # Handle boolean fields
                    boolean_fields = ['provides_sponsorship', 'is_remote', 'is_sponsored', 'expired']
                    for field in boolean_fields:
                        if field in job_data:
                            if is_effectively_empty(job_data[field]):
                                job_data[field] = False
                            else:
                                # Convert pandas/numpy types to Python bool
                                job_data[field] = bool(job_data[field])
                    
                    # Handle is_verified field
                    if 'is_verified' in job_data:
                        job_data['is_verified'] = True # For now we are setting all jobs to verified

                    # Handle numeric fields
                    numeric_fields = ['salary_min_range', 'salary_max_range']
                    for field in numeric_fields:
                        if field in job_data:
                            try:
                                if is_effectively_empty(job_data[field]):
                                    job_data[field] = None
                                else:
                                    # Convert pandas/numpy types to Python float
                                    job_data[field] = float(job_data[field])
                            except (ValueError, TypeError):
                                job_data[field] = None
                    
                    # Handle datetime fields - Supabase expects ISO format
                    datetime_fields = ['posted_date', 'created_at', 'updated_at']
                    for field in datetime_fields:
                        if field in job_data and job_data[field] is not None:
                            if isinstance(job_data[field], str):
                                # If it's already a string, keep it
                                pass
                            elif hasattr(job_data[field], 'isoformat'):
                                # If it's a datetime object, convert to ISO format
                                job_data[field] = job_data[field].isoformat()
                            else:
                                # If it's something else, set to current time
                                job_data[field] = datetime.now().isoformat()
                    
                    # Set default timestamps if not provided
                    current_time = datetime.now().isoformat()
                    if 'created_at' not in job_data:
                        job_data['created_at'] = current_time
                    if 'updated_at' not in job_data:
                        job_data['updated_at'] = current_time
                    
                    jobs_to_insert.append(job_data)
                    
                except Exception as e:
                    error_msg = f"Error processing job at index {index}: {str(e)}"
                    logger.error(error_msg)
                    stats['failed_uploads'] += 1
                    stats['errors'].append(error_msg)
                    continue
            
            if not jobs_to_insert:
                logger.warning("No valid jobs to insert")
                return stats
            
            # Get all job IDs that we want to insert to check for duplicates
            job_ids_to_insert = [job['id'] for job in jobs_to_insert]
            
            # Check for existing job IDs using Supabase
            logger.info("Checking for existing job IDs...")
            try:
                existing_result = self.client.table('jobs').select('id').in_('id', job_ids_to_insert).execute()
                existing_job_ids = {job['id'] for job in existing_result.data}
            except Exception as e:
                logger.warning("Could not check for existing jobs, proceeding with all inserts: %s", e)
                existing_job_ids = set()
            
            # Filter out duplicates
            unique_jobs = []
            for job_data in jobs_to_insert:
                if job_data['id'] in existing_job_ids:
                    stats['skipped_duplicates'] += 1
                else:
                    unique_jobs.append(job_data)
            
            logger.info("Found %d existing jobs, %d new jobs to insert", len(existing_job_ids), len(unique_jobs))
            
            # Insert unique jobs using Supabase
            if unique_jobs:
                logger.info("Inserting %d new jobs...", len(unique_jobs))
                
                # Insert in batches to avoid hitting Supabase limits
                batch_size = 100
                for i in range(0, len(unique_jobs), batch_size):
                    batch = unique_jobs[i:i + batch_size]
                    try:
                        result = self.client.table('jobs').insert(batch).execute()
                        if result.data:
                            stats['successful_uploads'] += len(result.data)
                            logger.info("Successfully inserted batch of %d jobs", len(result.data))
                        else:
                            # If no data returned but no error, assume success
                            stats['successful_uploads'] += len(batch)
                            logger.info("Inserted batch of %d jobs", len(batch))
                    except Exception as e:
                        error_msg = f"Error inserting batch starting at index {i}: {str(e)}"
                        logger.error(error_msg)
                        stats['failed_uploads'] += len(batch)
                        stats['errors'].append(error_msg)
                        continue
                
                logger.info("Successfully uploaded %d jobs to Supabase database", stats['successful_uploads'])
            else:
                logger.info("No new jobs to insert")
            
            if stats['skipped_duplicates'] > 0:
                logger.info("Skipped %d duplicate jobs", stats['skipped_duplicates'])
            
        except Exception as e:
            error_msg = f"Database error during upload: {str(e)}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            raise
        
        return stats

# Global Supabase manager instance
supabase_manager = SupabaseManager()

def get_db():
    """FastAPI dependency to get database session"""
    # For compatibility with existing FastAPI dependencies
    session = next(supabase_manager.get_session())
    try:
        yield session
    finally:
        session.close()