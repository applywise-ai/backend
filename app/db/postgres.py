import os
import logging
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import boto3

logger = logging.getLogger(__name__)

def get_db_token():
    """Generate a token for IAM authentication"""
    try:
        rds = boto3.client('rds')
        token = rds.generate_db_auth_token(
            DBHostname=settings.POSTGRES_HOST,
            Port=settings.POSTGRES_PORT,
            DBUsername=settings.POSTGRES_USER,
            Region=settings.AWS_REGION
        )
        return token
    except Exception as e:
        logger.error(f"Failed to generate IAM auth token: {e}")
        raise

def get_db_url():
    """Get database URL with password or IAM token"""
    if settings.POSTGRES_PASSWORD:
        # Use regular password authentication
        logger.info("Using password authentication for PostgreSQL")
        return f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    else:
        # Fall back to IAM authentication
        logger.info("Using IAM authentication for PostgreSQL")
        token = get_db_token()
        return f"postgresql://{settings.POSTGRES_USER}:{token}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

class PostgresManager:
    """Manages PostgreSQL database operations"""
    
    def __init__(self):
        """Initialize PostgreSQL connection with IAM authentication"""
        logger.info("🐘 Starting PostgreSQL initialization...")
        try:
            logger.info(f"📡 Connecting to PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
            
            # Configure connection args based on auth method
            connect_args = {'connect_timeout': 10}
            if not settings.POSTGRES_PASSWORD:
                # IAM auth requires SSL
                connect_args['sslmode'] = 'require'
            else:
                # Password auth can use SSL but doesn't require it
                connect_args['sslmode'] = 'prefer'
            
            self.engine = create_engine(
                get_db_url(),
                connect_args=connect_args,
                pool_pre_ping=True,  # Enable connection health checks
                pool_recycle=3600,   # Recycle connections every hour
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.metadata = MetaData()
            auth_method = "password" if settings.POSTGRES_PASSWORD else "IAM"
            logger.info(f"✅ PostgreSQL connection initialized with {auth_method} auth")
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

    def get_job_by_id(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job details by ID using ORM"""
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
                
        except SQLAlchemyError as e:
            logger.error(f"Database error getting job {job_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting job {job_id}: {e}")
            raise
        finally:
            session.close()
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'engine') and self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL connection closed")

    def get_jobs_by_company(self, company_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get jobs by company name"""
        from app.db.models import Job
        
        session = self.SessionLocal()
        try:
            jobs = session.query(Job).filter(
                Job.company.ilike(f"%{company_name}%")
            ).limit(limit).all()
            
            return [self._job_to_dict(job) for job in jobs]
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting jobs for company {company_name}: {e}")
            raise
        finally:
            session.close()
    
    def search_jobs(self, title: str = None, location: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search jobs by title and/or location"""
        from app.db.models import Job
        
        session = self.SessionLocal()
        try:
            query = session.query(Job)
            
            if title:
                query = query.filter(Job.title.ilike(f"%{title}%"))
            
            if location:
                query = query.filter(Job.location.ilike(f"%{location}%"))
            
            jobs = query.limit(limit).all()
            return [self._job_to_dict(job) for job in jobs]
            
        except SQLAlchemyError as e:
            logger.error(f"Database error searching jobs: {e}")
            raise
        finally:
            session.close()
    
    def _job_to_dict(self, job) -> Dict[str, Any]:
        """Convert Job model to dictionary"""
        return {
            'id': job.id,
            'title': job.title,
            'company': job.company,
            'logo': job.logo,
            'location': job.location,
            'salary': job.salary,
            'salary_value': job.salary_value,
            'job_type': job.job_type,
            'description': job.description,
            'experience_level': job.experience_level,
            'specialization': job.specialization,
            'responsibilities': job.responsibilities,
            'requirements': job.requirements,
            'jobUrl': job.job_url,  # Map back to camelCase for consistency
            'score': job.score,
            'tags': job.tags,
            'short_responsibilities': job.short_responsibilities,
            'short_qualifications': job.short_qualifications,
            'is_verified': job.is_verified,
            'is_sponsored': job.is_sponsored,
            'provides_sponsorship': job.provides_sponsorship,
            'expired': job.expired,
            'created_at': job.created_at,
            'updated_at': job.updated_at
        }

# Global Postgres manager instance
postgres_manager = PostgresManager()

def get_db():
    """FastAPI dependency to get database session"""
    session = postgres_manager.SessionLocal()
    try:
        yield session
    finally:
        session.close() 