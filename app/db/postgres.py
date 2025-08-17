import os
import logging
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings
from sqlalchemy import create_engine, MetaData, URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import boto3
import json
import numpy as np
import pandas as pd


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

def get_db_credentials():
    """Get database credentials from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client(
            'secretsmanager',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # Get the secret from Secrets Manager
        secret_name = settings.DB_SECRET_NAME
        response = secrets_client.get_secret_value(SecretId=secret_name)
        
        # Parse the secret JSON
        secret = json.loads(response['SecretString'])
        
        return {
            'username': secret['username'],
            'password': secret['password']
        }
    except Exception as e:
        logger.error(f"Failed to get database credentials from Secrets Manager: {e}")
        raise

def get_db_url():
    """Get database URL using credentials from Secrets Manager and settings"""
    try:
        credentials = get_db_credentials()
        
        logger.info("Using Secrets Manager authentication for PostgreSQL")
        return URL.create(
            drivername="postgresql",
            username=credentials['username'],
            password=credentials['password'],
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB
        )
    except Exception as e:
        logger.error(f"Failed to construct database URL: {e}")
        raise
class PostgresManager:
    """Manages PostgreSQL database operations"""
    
    def __init__(self):
        """Initialize PostgreSQL connection with Secrets Manager authentication"""
        logger.info("🐘 Starting PostgreSQL initialization...")
        try:
            logger.info("📡 Connecting to PostgreSQL using Secrets Manager credentials")
            
            # Get database URL from Secrets Manager
            db_url = get_db_url()
            
            # Configure connection args
            connect_args = {
                'connect_timeout': 10,
                'sslmode': 'require'  # Require SSL for security
            }
            
            self.engine = create_engine(
                db_url,
                connect_args=connect_args,
                pool_pre_ping=True,  # Enable connection health checks
                pool_recycle=3600,   # Recycle connections every hour
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.metadata = MetaData()
            
            logger.info("✅ PostgreSQL connection initialized with Secrets Manager auth")
        except Exception as e:
            logger.error(f"❌ Failed to initialize PostgreSQL connection: {e}")
            raise

    def get_session(self):
        """Get a new database session"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def cleanup(self):
        """Cleanup database connections and engine"""
        try:
            logger.info("🧹 Cleaning up PostgreSQL connections...")
            if hasattr(self, 'engine') and self.engine is not None:
                # Close all sessions first
                if hasattr(self, 'SessionLocal'):
                    try:
                        # Force close any open sessions
                        logger.info("Closing database sessions...")
                    except Exception as e:
                        logger.warning(f"Error closing sessions: {e}")
                
                # Dispose the engine to close all connections
                self.engine.dispose()
                logger.info("✅ PostgreSQL connections closed")
            else:
                logger.info("No PostgreSQL engine to clean up")
        except Exception as e:
            logger.error(f"❌ Error cleaning up PostgreSQL connections: {e}")

    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by its ID"""
        from app.db.models import Job
        
        session = self.SessionLocal()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            
            if job:
                logger.debug(f"Found job {job_id}: {job.title} at {job.company}")
                return self._job_to_dict(job)
            else:
                logger.warning(f"Job with ID {job_id} not found")
                return None
                
        except Exception as e:
            logger.error(f"Database error getting job {job_id}: {e}")
            return None
        finally:
            session.close()
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'engine') and self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL connection closed")
    
    def _job_to_dict(self, job) -> Dict[str, Any]:
        """Convert a Job model instance to a dictionary"""
        return {
            'id': job.id,
            'title': job.title,
            'company': job.company,
            'company_url': job.company_url,
            'logo': job.logo,
            'location': job.location,
            'salary_min_range': job.salary_min_range,
            'salary_max_range': job.salary_max_range,
            'salary_currency': job.salary_currency,
            'job_type': job.job_type,
            'description': job.description,
            'company_description': job.company_description,
            'company_size': job.company_size,
            'experience_level': job.experience_level,
            'specialization': job.specialization,
            'responsibilities': job.responsibilities,
            'requirements': job.requirements,
            'skills': job.skills,
            'job_url': job.job_url,
            'score': job.score,
            'tags': job.tags,
            'short_responsibilities': job.short_responsibilities,
            'short_qualifications': job.short_qualifications,
            'is_verified': job.is_verified,
            'is_sponsored': job.is_sponsored,
            'provides_sponsorship': job.provides_sponsorship,
            'expired': job.expired,
            'is_remote': job.is_remote,
            'posted_date': job.posted_date,
            'created_at': job.created_at,
            'updated_at': job.updated_at
        }
    
    def upload_jobs_dataframe(self, jobs_df, column_mapping: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Upload a pandas DataFrame to the jobs table using column mapping.
        
        Args:
            jobs_df: pandas DataFrame containing job data
            column_mapping: Dictionary mapping DataFrame columns to database columns
            
        Returns:
            Dict containing upload statistics
        """
        from app.db.models import Job
        import pandas as pd
        import uuid
        
        session = self.SessionLocal()
        stats = {
            'total_rows': len(jobs_df),
            'successful_uploads': 0,
            'failed_uploads': 0,
            'skipped_duplicates': 0,
            'errors': []
        }
        
        try:
            logger.info(f"Starting upload of {len(jobs_df)} jobs to database")
            
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
            
            # Get all job IDs that we want to insert
            job_ids_to_insert = [job['id'] for job in jobs_to_insert]
            
            # Get existing job IDs in one query
            logger.info("Checking for existing job IDs...")
            existing_job_ids = set(
                session.query(Job.id)
                .filter(Job.id.in_(job_ids_to_insert))
                .all()
            )
            existing_job_ids = {job_id[0] for job_id in existing_job_ids}  # Extract from tuples
            
            # Filter out duplicates
            unique_jobs = []
            for job_data in jobs_to_insert:
                if job_data['id'] in existing_job_ids:
                    stats['skipped_duplicates'] += 1
                else:
                    unique_jobs.append(job_data)
            
            logger.info(f"Found {len(existing_job_ids)} existing jobs, {len(unique_jobs)} new jobs to insert")
            
            # Bulk insert unique jobs
            if unique_jobs:
                logger.info(f"Inserting {len(unique_jobs)} new jobs...")
                for job_data in unique_jobs:
                    try:
                        job = Job(**job_data)
                        session.add(job)
                        stats['successful_uploads'] += 1
                    except Exception as e:
                        error_msg = f"Error inserting job {job_data.get('id', 'unknown')}: {str(e)}"
                        logger.error(error_msg)
                        stats['failed_uploads'] += 1
                        stats['errors'].append(error_msg)
                        continue
                
                # Commit all changes
                session.commit()
                logger.info(f"Successfully uploaded {stats['successful_uploads']} jobs to database")
            else:
                logger.info("No new jobs to insert")
            
            if stats['skipped_duplicates'] > 0:
                logger.info(f"Skipped {stats['skipped_duplicates']} duplicate jobs")
            
        except Exception as e:
            session.rollback()
            error_msg = f"Database error during upload: {str(e)}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            raise
        
        finally:
            session.close()
        
        return stats

# Global Postgres manager instance
postgres_manager = PostgresManager()

def get_db():
    """FastAPI dependency to get database session"""
    session = postgres_manager.SessionLocal()
    try:
        yield session
    finally:
        session.close() 