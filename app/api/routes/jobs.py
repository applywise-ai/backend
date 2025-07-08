from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Set, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from app.db.postgres import get_db
from app.db.models import Job
from app.schemas.job import JobResponse, JobFilters, JobsPaginatedResponse, JobsCountResponse, JobsSearchResponse
from app.core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/paginated", response_model=Dict[str, Any])
async def get_jobs_paginated(
    limit: int = Query(9, ge=1, le=100, description="Number of jobs to return"),
    last_job_id: Optional[int] = Query(None, description="Last job ID for pagination"),
    # Filters
    location: Optional[str] = Query(None, description="Filter by location"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level"),
    salary_min: Optional[float] = Query(None, description="Minimum salary value"),
    salary_max: Optional[float] = Query(None, description="Maximum salary value"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    title: Optional[str] = Query(None, description="Filter by job title"),
    provides_sponsorship: Optional[bool] = Query(None, description="Filter by sponsorship availability"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tags to filter by"),
    # Exclusions
    exclude_job_ids: Optional[str] = Query(None, description="Comma-separated list of job IDs to exclude"),
    db: Session = Depends(get_db)
):
    """
    Get paginated jobs with optional filters - matches jobsService.getJobsPaginated.
    Returns: { jobs: Job[], hasMore: boolean, lastJobId?: number }
    """
    try:
        query = db.query(Job).filter(Job.expired == False)
        
        # Apply cursor pagination
        if last_job_id:
            query = query.filter(Job.id < last_job_id)
        
        # Apply filters
        if location:
            query = query.filter(Job.location.ilike(f"%{location}%"))
        
        if job_type:
            query = query.filter(Job.job_type.ilike(f"%{job_type}%"))
        
        if experience_level:
            query = query.filter(Job.experience_level.ilike(f"%{experience_level}%"))
        
        if salary_min is not None:
            query = query.filter(Job.salary_value >= salary_min)
        
        if salary_max is not None:
            query = query.filter(Job.salary_value <= salary_max)
        
        if company:
            query = query.filter(Job.company.ilike(f"%{company}%"))
        
        if title:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        
        if provides_sponsorship is not None:
            query = query.filter(Job.provides_sponsorship == provides_sponsorship)
        
        if is_verified is not None:
            query = query.filter(Job.is_verified == is_verified)
        
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",")]
            # Filter jobs that contain any of the specified tags
            tag_conditions = [Job.tags.op('?')(tag) for tag in tag_list]
            query = query.filter(or_(*tag_conditions))
        
        # Exclude specific job IDs (for applied jobs)
        if exclude_job_ids:
            exclude_ids = [int(job_id.strip()) for job_id in exclude_job_ids.split(",")]
            query = query.filter(~Job.id.in_(exclude_ids))
        
        # Order by ID descending for cursor pagination
        query = query.order_by(desc(Job.id))
        
        # Fetch limit + 1 to check if there are more results
        jobs = query.limit(limit + 1).all()
        
        # Check if there are more results
        has_more = len(jobs) > limit
        if has_more:
            jobs = jobs[:limit]  # Remove the extra job
        
        # Get the last job ID for next pagination
        last_job_id = jobs[-1].id if jobs else None
        
        logger.info(f"Retrieved {len(jobs)} jobs with filters applied, hasMore: {has_more}")
        
        return {
            "jobs": jobs,
            "hasMore": has_more,
            "lastJobId": last_job_id
        }
        
    except Exception as e:
        logger.error(f"Error fetching paginated jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs")

@router.get("/filtered-count")
async def get_filtered_jobs_count(
    # Filters (same as paginated endpoint)
    location: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    experience_level: Optional[str] = Query(None),
    salary_min: Optional[float] = Query(None),
    salary_max: Optional[float] = Query(None),
    company: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    provides_sponsorship: Optional[bool] = Query(None),
    is_verified: Optional[bool] = Query(None),
    tags: Optional[str] = Query(None),
    exclude_applied_count: int = Query(0, description="Number of applied jobs to subtract"),
    db: Session = Depends(get_db)
):
    """
    Get count of jobs matching the filters - matches jobsService.getFilteredJobsCount.
    """
    try:
        query = db.query(func.count(Job.id)).filter(Job.expired == False)
        
        # Apply same filters as pagination endpoint
        if location:
            query = query.filter(Job.location.ilike(f"%{location}%"))
        
        if job_type:
            query = query.filter(Job.job_type.ilike(f"%{job_type}%"))
        
        if experience_level:
            query = query.filter(Job.experience_level.ilike(f"%{experience_level}%"))
        
        if salary_min is not None:
            query = query.filter(Job.salary_value >= salary_min)
        
        if salary_max is not None:
            query = query.filter(Job.salary_value <= salary_max)
        
        if company:
            query = query.filter(Job.company.ilike(f"%{company}%"))
        
        if title:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        
        if provides_sponsorship is not None:
            query = query.filter(Job.provides_sponsorship == provides_sponsorship)
        
        if is_verified is not None:
            query = query.filter(Job.is_verified == is_verified)
        
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",")]
            tag_conditions = [Job.tags.op('?')(tag) for tag in tag_list]
            query = query.filter(or_(*tag_conditions))
        
        count = query.scalar()
        available_count = max(0, count - exclude_applied_count)
        
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
        job_id_list = [int(job_id.strip()) for job_id in job_ids.split(",")]
        
        jobs = db.query(Job).filter(Job.id.in_(job_id_list)).all()
        
        # Create a mapping for quick lookup
        jobs_dict = {job.id: job for job in jobs}
        
        # Return jobs in the same order as requested, with None for missing/expired jobs
        result = []
        for job_id in job_id_list:
            job = jobs_dict.get(job_id)
            if job and not job.expired:
                result.append(job)
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

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
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
        return job
        
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch job")

# Legacy endpoints for backward compatibility
@router.get("/", response_model=List[JobResponse])
async def get_jobs_list(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get jobs with offset-based pagination (legacy endpoint).
    """
    try:
        jobs = db.query(Job).filter(Job.expired == False).order_by(desc(Job.id)).offset(offset).limit(limit).all()
        return jobs
    except Exception as e:
        logger.error(f"Error fetching jobs list: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs")

@router.get("/search/advanced")
async def search_jobs_advanced(
    q: Optional[str] = Query(None, description="Search query for title, company, or description"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", description="Sort by: created_at, salary_value, score"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    db: Session = Depends(get_db)
):
    """
    Advanced job search with full-text search capabilities.
    """
    try:
        query = db.query(Job).filter(Job.expired == False)
        
        # Apply search query
        if q:
            search_filter = or_(
                Job.title.ilike(f"%{q}%"),
                Job.company.ilike(f"%{q}%"),
                Job.description.ilike(f"%{q}%"),
                Job.location.ilike(f"%{q}%")
            )
            query = query.filter(search_filter)
        
        # Apply sorting
        sort_column = getattr(Job, sort_by, Job.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))
        
        # Apply pagination
        total_count = query.count()
        jobs = query.offset(offset).limit(limit).all()
        
        return {
            "jobs": jobs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }
        
    except Exception as e:
        logger.error(f"Error in advanced job search: {e}")
        raise HTTPException(status_code=500, detail="Failed to search jobs") 