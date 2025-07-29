from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Set, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings
from sqlalchemy import create_engine, MetaData, URL, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import boto3
import json
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from app.db.postgres import get_db
from app.db.models import Job
from app.schemas.job import JobResponse, JobFilters, JobsPaginatedResponse, JobsCountResponse, JobsSearchResponse
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def convert_job_to_response(job: Job) -> JobResponse:
    """Convert SQLAlchemy Job model to Pydantic JobResponse"""
    try:
        # Convert to dict and handle None values for list fields
        job_dict = {
            'id': job.id,
            'title': job.title,
            'company': job.company,
            'company_url': job.company_url,
            'logo': job.logo,
            'company_description': job.company_description,
            'location': job.location,
            'salary_min_range': job.salary_min_range,
            'salary_max_range': job.salary_max_range,
            'salary_currency': job.salary_currency,
            'job_type': job.job_type,
            'description': job.description,
            'posted_date': job.posted_date,
            'experience_level': job.experience_level,
            'specialization': job.specialization,
            'responsibilities': job.responsibilities if job.responsibilities else [],
            'requirements': job.requirements if job.requirements else [],
            'job_url': job.job_url,
            'skills': job.skills if job.skills else [],
            'short_responsibilities': job.short_responsibilities,
            'short_qualifications': job.short_qualifications,
            'is_remote': job.is_remote,
            'is_verified': job.is_verified,
            'is_sponsored': job.is_sponsored,
            'provides_sponsorship': job.provides_sponsorship,
            'expired': job.expired,
            'created_at': job.created_at,
            'updated_at': job.updated_at
        }
        return JobResponse.model_validate(job_dict)
    except Exception as e:
        logger.error(f"Error converting job {job.id if job else 'None'} to response: {e}")
        raise e

def convert_jobs_to_response(jobs: List[Job]) -> List[JobResponse]:
    """Convert list of SQLAlchemy Job models to Pydantic JobResponse models"""
    try:
        logger.info(f"Converting {len(jobs)} jobs to response format")
        result = [convert_job_to_response(job) for job in jobs]
        logger.info(f"Successfully converted {len(result)} jobs")
        return result
    except Exception as e:
        logger.error(f"Error converting jobs list to response: {e}")
        raise e

@router.get("/paginated", response_model=Dict[str, Any])
async def get_jobs_paginated(
    limit: int = Query(9, ge=1, le=100, description="Number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip for pagination"),
    # Search query
    q: Optional[str] = Query(None, description="Search query for title, company, description, or skills"),
    # Sorting
    sort_by: str = Query("id", description="Sort by: id, created_at, salary_min_range, salary_max_range, score"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    # Filters
    location: Optional[str] = Query(None, description="Comma-separated list of locations to filter by"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level"),
    salary_min: Optional[float] = Query(None, description="Minimum salary value"),
    salary_max: Optional[float] = Query(None, description="Maximum salary value"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    title: Optional[str] = Query(None, description="Filter by job title"),
    specialization: Optional[str] = Query(None, description="Comma-separated list of specializations to filter by"),
    provides_sponsorship: Optional[bool] = Query(None, description="Filter by sponsorship availability"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    # Exclusions
    excluded_job_ids: Optional[str] = Query(None, description="Comma-separated list of job IDs to exclude"),
    db: Session = Depends(get_db)
):
    """
    Get paginated jobs with optional filters, search query, and sorting - matches jobsService.getJobsPaginated.
    Returns: { jobs: Job[], hasMore: boolean, lastJobId?: number }
    """
    try:
        query = db.query(Job).filter(Job.expired == False)
        
        # Apply search query (now includes skills)
        if q:
            search_filter = or_(
                Job.title.ilike(f"%{q}%"),
                Job.company.ilike(f"%{q}%"),
                Job.description.ilike(f"%{q}%"),
                # Search in skills array using JSONB containment
                Job.skills.cast(String).ilike(f"%{q}%")
            )
            query = query.filter(search_filter)
        
        # Apply filters
        if location:
            location_list = [loc.strip() for loc in location.split(",")]
            
            # Check if "remote" is in the location list
            has_remote = "remote" in location_list
            non_remote_locations = [loc for loc in location_list if loc != "remote"]
            
            # Build location conditions
            location_conditions = []
            
            # Add conditions for non-remote locations
            if non_remote_locations:
                location_conditions.extend([Job.location.ilike(f"%{loc}%") for loc in non_remote_locations])
            
            # Add condition for remote jobs if "remote" is in the list
            if has_remote:
                location_conditions.append(Job.is_remote == True)
            
            # Apply the combined filter
            if location_conditions:
                query = query.filter(or_(*location_conditions))
        
        if job_type:
            query = query.filter(Job.job_type.ilike(f"%{job_type}%"))
        
        if experience_level:
            # Split by comma for multiple experience levels
            experience_level_list = [level.strip() for level in experience_level.split(",")]
            experience_level_conditions = [Job.experience_level.ilike(f"%{level}%") for level in experience_level_list]
            query = query.filter(or_(*experience_level_conditions))
        
        # Check if any salary filters are active
        salary_filters_active = salary_min is not None or salary_max is not None
        
        # Check if sorting by salary is active
        salary_sorting_active = sort_by in ['salary_min_range', 'salary_max_range']
        
        # Filter out null salary values if salary filters or sorting are active
        if salary_filters_active or salary_sorting_active:
            query = query.filter(Job.salary_min_range.isnot(None))
            query = query.filter(Job.salary_max_range.isnot(None))
        
        if salary_min is not None:
            query = query.filter(Job.salary_min_range >= salary_min)
        
        if salary_max is not None:
            query = query.filter(Job.salary_max_range <= salary_max)
        
        if company:
            query = query.filter(Job.company.ilike(f"%{company}%"))
        
        if title:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        
        if specialization:
            specialization_list = [spec.strip() for spec in specialization.split(",")]
            specialization_conditions = [Job.specialization.ilike(f"%{spec}%") for spec in specialization_list]
            query = query.filter(or_(*specialization_conditions))
        
        if provides_sponsorship is not None:
            query = query.filter(Job.provides_sponsorship == provides_sponsorship)
        
        if is_verified is not None:
            query = query.filter(Job.is_verified == is_verified)
        
        # Exclude specific job IDs (for applied jobs)
        if excluded_job_ids:
            exclude_ids = [job_id.strip() for job_id in excluded_job_ids.split(",")]
            query = query.filter(~Job.id.in_(exclude_ids))
        
        # Apply sorting
        sort_column = getattr(Job, sort_by, Job.id)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column, Job.id)  # Always use id as secondary sort
        else:
            query = query.order_by(desc(sort_column), Job.id)  # Always use id as secondary sort
        
        # Apply offset pagination
        query = query.offset(offset).limit(limit + 1)  # Get one extra to check if there are more
        
        # Fetch jobs
        jobs = query.all()
        
        # Check if there are more results
        has_more = len(jobs) > limit
        if has_more:
            jobs = jobs[:limit]  # Remove the extra job
        
        # Get the last job ID for next pagination
        last_job_id = jobs[-1].id if jobs else None
        
        logger.info(f"Retrieved {len(jobs)} jobs with offset {offset}, hasMore: {has_more}, lastJobId: {last_job_id}")
        
        # Convert SQLAlchemy models to Pydantic models
        job_responses = convert_jobs_to_response(jobs)
        
        return {
            "jobs": job_responses,
            "hasMore": has_more,
            "lastJobId": last_job_id
        }
        
    except Exception as e:
        logger.error(f"Error fetching paginated jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs")

@router.get("/filtered-count")
async def get_filtered_jobs_count(
    # Search query
    q: Optional[str] = Query(None, description="Search query for title, company, description, or skills"),
    # Filters (same as paginated endpoint)
    location: Optional[str] = Query(None, description="Comma-separated list of locations to filter by"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level"),
    salary_min: Optional[float] = Query(None, description="Minimum salary value"),
    salary_max: Optional[float] = Query(None, description="Maximum salary value"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    title: Optional[str] = Query(None, description="Filter by job title"),
    specialization: Optional[str] = Query(None, description="Comma-separated list of specializations to filter by"),
    provides_sponsorship: Optional[bool] = Query(None, description="Filter by sponsorship availability"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    exclude_applied_count: int = Query(0, description="Number of applied jobs to subtract"),
    db: Session = Depends(get_db)
):
    """
    Get count of jobs matching the filters - matches jobsService.getFilteredJobsCount.
    """
    try:
        query = db.query(func.count(Job.id)).filter(Job.expired == False)
        
        # Apply search query (now includes skills)
        if q:
            search_filter = or_(
                Job.title.ilike(f"%{q}%"),
                Job.company.ilike(f"%{q}%"),
                Job.description.ilike(f"%{q}%"),
                # Search in skills array using JSONB containment
                Job.skills.cast(String).ilike(f"%{q}%")
            )
            query = query.filter(search_filter)
        
        # Apply same filters as pagination endpoint
        if location:
            location_list = [loc.strip() for loc in location.split(",")]
            
            # Check if "remote" is in the location list
            has_remote = "remote" in location_list
            non_remote_locations = [loc for loc in location_list if loc != "remote"]
            
            # Build location conditions
            location_conditions = []
            
            # Add conditions for non-remote locations
            if non_remote_locations:
                location_conditions.extend([Job.location.ilike(f"%{loc}%") for loc in non_remote_locations])
            
            # Add condition for remote jobs if "remote" is in the list
            if has_remote:
                location_conditions.append(Job.is_remote == True)
            
            # Apply the combined filter
            if location_conditions:
                query = query.filter(or_(*location_conditions))
        
        if job_type:
            query = query.filter(Job.job_type.ilike(f"%{job_type}%"))
        
        if experience_level:
            # Split by comma for multiple experience levels
            experience_level_list = [level.strip() for level in experience_level.split(",")]
            experience_level_conditions = [Job.experience_level.ilike(f"%{level}%") for level in experience_level_list]
            query = query.filter(or_(*experience_level_conditions))
        
        # Check if any salary filters are active
        salary_filters_active = salary_min is not None or salary_max is not None
        
        # Filter out null salary values if salary filters are active
        if salary_filters_active:
            query = query.filter(Job.salary_min_range.isnot(None))
            query = query.filter(Job.salary_max_range.isnot(None))
        
        if salary_min is not None:
            query = query.filter(Job.salary_min_range >= salary_min)
        
        if salary_max is not None:
            query = query.filter(Job.salary_max_range <= salary_max)
        
        if company:
            query = query.filter(Job.company.ilike(f"%{company}%"))
        
        if title:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        
        if specialization:
            specialization_list = [spec.strip() for spec in specialization.split(",")]
            specialization_conditions = [Job.specialization.ilike(f"%{spec}%") for spec in specialization_list]
            query = query.filter(or_(*specialization_conditions))
        
        if provides_sponsorship is not None:
            query = query.filter(Job.provides_sponsorship == provides_sponsorship)
        
        if is_verified is not None:
            query = query.filter(Job.is_verified == is_verified)
        
        job_count = query.scalar()
        available_count = max(0, job_count - exclude_applied_count)
        
        return available_count
        
    except Exception as e:
        logger.error(f"Error getting filtered jobs count: {e}")
        raise HTTPException(status_code=500, detail="Failed to get filtered jobs count")

@router.get("/total-available-count")
async def get_total_available_jobs_count(
    exclude_applied_count: int = Query(0, description="Number of applied jobs to subtract from total"),
    db: Session = Depends(get_db)
):
    """
    Get total count of available (non-expired) jobs - matches jobsService.getTotalAvailableJobsCount.
    """
    try:
        total_count = db.query(func.count(Job.id)).filter(Job.expired == False).scalar()
        available_count = max(0, total_count - exclude_applied_count)
        
        return available_count
        
    except Exception as e:
        logger.error(f"Error getting total available jobs count: {e}")
        raise HTTPException(status_code=500, detail="Failed to get total available jobs count")

@router.get("/bulk")
async def get_jobs_bulk(
    job_ids: str = Query(..., description="Comma-separated list of job IDs"),
    db: Session = Depends(get_db)
):
    """
    Get multiple jobs by their IDs - matches jobsService.getJobs.
    Returns jobs in the same order as requested, with null for missing/expired jobs.
    """
    try:
        job_id_list = [job_id.strip() for job_id in job_ids.split(",")]
        
        jobs = db.query(Job).filter(Job.id.in_(job_id_list)).all()
        
        # Create a mapping for quick lookup
        jobs_dict = {job.id: job for job in jobs}
        
        # Return jobs in the same order as requested, with None for missing/expired jobs
        result = []
        for job_id in job_id_list:
            job = jobs_dict.get(job_id)
            if job and not job.expired:
                result.append(convert_job_to_response(job))
            else:
                result.append(None)
        
        logger.info(f"Retrieved {len([j for j in result if j])} out of {len(job_id_list)} requested jobs")
        return result
        
    except ValueError as e:
        logger.error(f"Invalid job ID format: {e}")
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    except Exception as e:
        logger.error(f"Error fetching bulk jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs")

@router.get("/recommended", response_model=List[JobResponse])
async def get_recommended_jobs(
    experience_level: str = Query(..., description="Experience level (e.g., 'senior', 'director')"),
    specializations: str = Query(..., description="Comma-separated list of specializations (e.g., 'backend,frontend')"),
    requires_sponsorship: Optional[bool] = Query(None, description="Filter by sponsorship requirement (optional)"),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of jobs to return"),
    excluded_job_ids: Optional[str] = Query(None, description="Comma-separated list of job IDs to exclude"),
    db: Session = Depends(get_db)
):
    """
    Get recommended jobs filtered by experience level, specializations, and optional sponsorship requirements.
    Returns jobs created within the last 7 days.
    """
    try:
        from datetime import datetime, timedelta
        from app.services.job_application.types import expand_specializations
        
        logger.info(f"Starting recommended jobs query with experience_level={experience_level}, specializations={specializations}")
        
        # Calculate the date threshold (7 days)
        date_threshold = datetime.now() - timedelta(days=7)
        logger.info(f"Date threshold: {date_threshold}")
        
        # Build the query
        query = db.query(Job).filter(Job.expired == False)
        
        # Filter by creation date
        query = query.filter(Job.created_at >= date_threshold)
        
        # Filter by sponsorship requirement (only if parameter is provided)
        if requires_sponsorship is not None:
            query = query.filter(Job.provides_sponsorship == requires_sponsorship)
            logger.info(f"Filtering by sponsorship: {requires_sponsorship}")
        
        # Filter by experience level (single value)
        query = query.filter(Job.experience_level.ilike(f"%{experience_level}%"))
        logger.info(f"Filtering by experience level: {experience_level}")
        
        # Filter by specializations (including related ones)
        specialization_list = [spec.strip() for spec in specializations.split(",")]
        expanded_specializations = expand_specializations(specialization_list)
        logger.info(f"Original specializations: {specialization_list}")
        logger.info(f"Expanded specializations: {expanded_specializations}")
        
        # Safety check for expanded_specializations
        if not expanded_specializations:
            logger.warning("No expanded specializations found, using original list")
            expanded_specializations = specialization_list
        
        specialization_conditions = [Job.specialization.ilike(f"%{spec}%") for spec in expanded_specializations]
        query = query.filter(or_(*specialization_conditions))
        
        # Exclude specific job IDs (for disliked jobs)
        if excluded_job_ids:
            exclude_ids = [job_id.strip() for job_id in excluded_job_ids.split(",")]
            query = query.filter(~Job.id.in_(exclude_ids))
            logger.info(f"Excluding job IDs: {exclude_ids}")
        
        # Sort by creation date (newest first)
        query = query.order_by(desc(Job.created_at), Job.id)
        
        # Apply limit
        jobs = query.limit(limit).all()
        
        logger.info(f"Retrieved {len(jobs)} recommended jobs for experience level: {experience_level}, specializations: {specializations} (expanded to: {expanded_specializations})")
        
        # Convert SQLAlchemy models to Pydantic models
        job_responses = convert_jobs_to_response(jobs)
        logger.info(f"Converted {len(job_responses)} jobs to response format")
        
        # Ensure we return an empty list instead of None
        if job_responses is None:
            logger.warning("job_responses is None, returning empty list")
            job_responses = []
        
        # Final safety check - ensure we always return a list
        if not isinstance(job_responses, list):
            logger.error(f"job_responses is not a list: {type(job_responses)}")
            job_responses = []
        
        logger.info(f"Returning {len(job_responses)} jobs")
        return job_responses
        
    except Exception as e:
        logger.error(f"Error fetching recommended jobs: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to fetch recommended jobs")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a single job by ID - matches jobsService.getJob.
    """
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            return None  # Return null instead of 404 to match frontend expectations
        
        if job.expired:
            return None  # Return null for expired jobs
        
        logger.info(f"Retrieved job {job_id}: {job.title} at {job.company}")
        return convert_job_to_response(job)
        
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch job")