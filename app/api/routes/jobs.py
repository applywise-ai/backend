from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from app.db.supabase import supabase_manager
from app.schemas.job import JobResponse, JobsPaginatedResponse, JobsCountResponse, JobsSearchResponse
import logging
from datetime import datetime, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)

def convert_job_to_response(job_dict: Dict[str, Any]) -> JobResponse:
    """Convert Supabase job dict to Pydantic JobResponse"""
    try:
        # Ensure list fields are not None
        job_dict['responsibilities'] = job_dict.get('responsibilities') or []
        job_dict['requirements'] = job_dict.get('requirements') or []
        job_dict['skills'] = job_dict.get('skills') or []
        job_dict['tags'] = job_dict.get('tags') or []
        
        return JobResponse(**job_dict)
    except Exception as e:
        logger.error("Error converting job dict to response: %s", e)
        logger.error("Job dict: %s", job_dict)
        raise HTTPException(status_code=500, detail=f"Error processing job data: {str(e)}")

@router.get("/paginated", response_model=JobsPaginatedResponse)
async def get_jobs(
    limit: int = Query(10, ge=1, le=100, description="Number of jobs per page"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    q: Optional[str] = Query(None, description="Search query"),
    location: Optional[str] = Query(None, description="Location filter (comma-separated)"),
    job_type: Optional[str] = Query(None, description="Job type filter"),
    experience_level: Optional[str] = Query(None, description="Experience level filter (comma-separated)"),
    salary_min: Optional[float] = Query(None, description="Minimum salary"),
    salary_max: Optional[float] = Query(None, description="Maximum salary"),
    company: Optional[str] = Query(None, description="Company filter"),
    title: Optional[str] = Query(None, description="Title filter"),
    specialization: Optional[str] = Query(None, description="Specialization filter (comma-separated)"),
    provides_sponsorship: Optional[bool] = Query(None, description="Provides sponsorship filter"),
    is_verified: Optional[bool] = Query(None, description="Verified jobs filter"),
    excluded_job_ids: Optional[str] = Query(None, description="Comma-separated job IDs to exclude"),
    sort_by: str = Query("created_at", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)")
):
    """
    Get paginated list of jobs with filters and search
    """
    try:
        # Use offset directly (no need to calculate from page)
        
        # Build base query
        query = supabase_manager.client.table('jobs').select('*')
        
        # Filter out expired jobs
        query = query.eq('expired', False)
        
        # Apply search query
        if q:
            # Supabase doesn't support complex OR queries as easily as SQLAlchemy
            # We'll search in title and company for now
            search_query = f"%{q}%"
            query = query.or_(f"title.ilike.{search_query},company.ilike.{search_query},description.ilike.{search_query}")
        
        # Apply location filter
        if location:
            locations = [loc.strip() for loc in location.split(',')]
            remote_locations = [loc for loc in locations if loc.lower() in ['remote', 'anywhere']]
            non_remote_locations = [loc for loc in locations if loc.lower() not in ['remote', 'anywhere']]
            
            location_conditions = []
            if non_remote_locations:
                for loc in non_remote_locations:
                    location_conditions.append(f"location.ilike.%{loc}%")
            if remote_locations:
                location_conditions.append("is_remote.eq.true")
            
            if location_conditions:
                query = query.or_(','.join(location_conditions))
        
        # Apply job type filter
        if job_type:
            query = query.ilike('job_type', f'%{job_type}%')
        
        # Apply experience level filter
        if experience_level:
            experience_levels = [level.strip() for level in experience_level.split(',')]
            exp_conditions = [f"experience_level.ilike.%{level}%" for level in experience_levels]
            if exp_conditions:
                query = query.or_(','.join(exp_conditions))
        
        # Apply salary filters
        if salary_min is not None or salary_max is not None:
            # Filter out jobs with null salary values when salary filters are applied
            query = query.not_.is_('salary_min_range', None).not_.is_('salary_max_range', None)
        
            if salary_min is not None:
                query = query.gte('salary_min_range', salary_min)
            if salary_max is not None:
                query = query.lte('salary_max_range', salary_max)
        
        # Apply company filter
        if company:
            query = query.ilike('company', f'%{company}%')
        
        # Apply title filter
        if title:
            query = query.ilike('title', f'%{title}%')
        
        # Apply specialization filter
        if specialization:
            specializations = [spec.strip() for spec in specialization.split(',')]
            spec_conditions = [f"specialization.ilike.%{spec}%" for spec in specializations]
            if spec_conditions:
                query = query.or_(','.join(spec_conditions))
        
        # Apply sponsorship filter
        if provides_sponsorship is not None:
            query = query.eq('provides_sponsorship', provides_sponsorship)
        
        # Apply verification filter
        if is_verified is not None:
            query = query.eq('is_verified', is_verified)
        
        # Apply exclude IDs filter
        if excluded_job_ids:
            exclude_list = [id.strip() for id in excluded_job_ids.split(',')]
            query = query.not_.in_('id', exclude_list)
        
        # TEMPORARY: Filter out greenhouse jobs
        query = query.not_.ilike('job_url', '%greenhouse%')
        
        # Apply sorting with id as secondary sort
        if sort_order.lower() == 'desc':
            query = query.order(sort_by, desc=True).order('id')
        else:
            query = query.order(sort_by).order('id')
        
        # Apply pagination - request one extra job to check if there are more
        query = query.range(offset, offset + limit)  # Get limit + 1 jobs
        
        # Execute query
        result = query.execute()
        jobs_data = result.data or []
        
        # Check if there are more jobs
        has_more = len(jobs_data) > limit
        
        # If we got more than limit, remove the extra job
        if has_more:
            jobs_data = jobs_data[:limit]
        
        # Convert to response format
        jobs = [convert_job_to_response(job) for job in jobs_data]
        
        return JobsPaginatedResponse(
            jobs=jobs,
            has_more=has_more
        )
        
    except Exception as e:
        logger.error("Error in get_jobs: %s", e)
        raise HTTPException(status_code=500, detail=f"Error fetching jobs: {str(e)}")

@router.get("/filtered-count")
async def get_jobs_count(
    q: Optional[str] = Query(None, description="Search query"),
    location: Optional[str] = Query(None, description="Location filter (comma-separated)"),
    job_type: Optional[str] = Query(None, description="Job type filter"),
    experience_level: Optional[str] = Query(None, description="Experience level filter (comma-separated)"),
    salary_min: Optional[float] = Query(None, description="Minimum salary"),
    salary_max: Optional[float] = Query(None, description="Maximum salary"),
    company: Optional[str] = Query(None, description="Company filter"),
    title: Optional[str] = Query(None, description="Title filter"),
    specialization: Optional[str] = Query(None, description="Specialization filter (comma-separated)"),
    provides_sponsorship: Optional[bool] = Query(None, description="Provides sponsorship filter"),
    is_verified: Optional[bool] = Query(None, description="Verified jobs filter"),
    excluded_job_ids: Optional[str] = Query(None, description="Comma-separated job IDs to exclude"),
):
    """
    Get count of jobs matching filters
    """
    try:
        # Build count query
        query = supabase_manager.client.table('jobs').select('id', count='exact').eq('expired', False)
        
        # Apply the same filters as in get_jobs
        if q:
            search_query = f"%{q}%"
            query = query.or_(f"title.ilike.{search_query},company.ilike.{search_query},description.ilike.{search_query}")
        
        if location:
            locations = [loc.strip() for loc in location.split(',')]
            remote_locations = [loc for loc in locations if loc.lower() in ['remote', 'anywhere']]
            non_remote_locations = [loc for loc in locations if loc.lower() not in ['remote', 'anywhere']]
            
            location_conditions = []
            if non_remote_locations:
                for loc in non_remote_locations:
                    location_conditions.append(f"location.ilike.%{loc}%")
            if remote_locations:
                location_conditions.append("is_remote.eq.true")
            
            if location_conditions:
                query = query.or_(','.join(location_conditions))
        
        if job_type:
            query = query.ilike('job_type', f'%{job_type}%')
        
        if experience_level:
            experience_levels = [level.strip() for level in experience_level.split(',')]
            exp_conditions = [f"experience_level.ilike.%{level}%" for level in experience_levels]
            if exp_conditions:
                query = query.or_(','.join(exp_conditions))
        
        if salary_min is not None or salary_max is not None:
            # Filter out jobs with null salary values when salary filters are applied
            query = query.not_.is_('salary_min_range', None).not_.is_('salary_max_range', None)
        
            if salary_min is not None:
                query = query.gte('salary_min_range', salary_min)
            if salary_max is not None:
                query = query.lte('salary_max_range', salary_max)
        
        if company:
            query = query.ilike('company', f'%{company}%')
        
        if title:
            query = query.ilike('title', f'%{title}%')
        
        if specialization:
            specializations = [spec.strip() for spec in specialization.split(',')]
            spec_conditions = [f"specialization.ilike.%{spec}%" for spec in specializations]
            if spec_conditions:
                query = query.or_(','.join(spec_conditions))
        
        if provides_sponsorship is not None:
            query = query.eq('provides_sponsorship', provides_sponsorship)
        
        if is_verified is not None:
            query = query.eq('is_verified', is_verified)
        
        # Apply exclude IDs filter
        if excluded_job_ids:
            exclude_list = [id.strip() for id in excluded_job_ids.split(',')]
            query = query.not_.in_('id', exclude_list)
        
        # TEMPORARY: Filter out greenhouse jobs
        query = query.not_.ilike('job_url', '%greenhouse%')
        
        result = query.execute()
        filtered_count = result.count if result.count is not None else 0
        logger.info(f"Filtered count: {filtered_count}")
        
        
        return filtered_count
        
    except Exception as e:
        logger.error("Error in get_jobs_count: %s", e)
        raise HTTPException(status_code=500, detail=f"Error counting jobs: {str(e)}")

@router.get("/total-available-count")
async def get_total_available_count(
    exclude_applied_count: Optional[int] = Query(None, description="Number of applied jobs to subtract")
):
    """
    Get total count of available (non-expired) jobs
    """
    try:
        # Get total count of non-expired jobs
        query = supabase_manager.client.table('jobs').select('id', count='exact').eq('expired', False)
        result = query.execute()
        total_count = result.count if result.count is not None else 0
        
        # Subtract applied count if provided
        if exclude_applied_count:
            total_count = max(0, total_count - exclude_applied_count)
        
        return total_count
        
    except Exception as e:
        logger.error("Error in get_total_available_count: %s", e)
        raise HTTPException(status_code=500, detail=f"Error getting total available count: {str(e)}")

@router.get("/bulk", response_model=List[Optional[JobResponse]])
async def get_jobs_bulk(
    job_ids: str = Query(..., description="Comma-separated job IDs")
):
    """
    Get multiple jobs by their IDs
    """
    try:
        job_id_list = [id.strip() for id in job_ids.split(',') if id.strip()]
        
        if not job_id_list:
            return []
        
        # Get jobs by IDs
        query = supabase_manager.client.table('jobs').select('*').in_('id', job_id_list)
        result = query.execute()
        jobs_data = result.data or []
        
        # Create a dict for quick lookup
        jobs_dict = {job['id']: convert_job_to_response(job) for job in jobs_data}
        
        # Return jobs in the same order as requested, with None for missing jobs
        jobs = [jobs_dict.get(job_id) for job_id in job_id_list]
        
        return jobs
        
    except Exception as e:
        logger.error("Error in get_jobs_bulk: %s", e)
        raise HTTPException(status_code=500, detail=f"Error getting bulk jobs: {str(e)}")

@router.get("/recommended", response_model=List[JobResponse])
async def get_recommended_jobs(
    experience_level: str = Query(..., description="Experience level"),
    specializations: str = Query(..., description="Comma-separated specializations"),
    requires_sponsorship: Optional[bool] = Query(None, description="Requires sponsorship"),
    excluded_job_ids: Optional[str] = Query(None, description="Comma-separated job IDs to exclude"),
    limit: int = Query(10, ge=1, le=50, description="Number of jobs to return")
):
    """
    Get recommended jobs based on user preferences
    """
    try:
        # Calculate date threshold (jobs from last 30 days)
        date_threshold = datetime.now() - timedelta(days=7)
        
        # Build query
        query = supabase_manager.client.table('jobs').select('*').eq('expired', False)
        
        # Filter by date
        query = query.gte('created_at', date_threshold.isoformat())
        
        # Apply sponsorship filter
        if requires_sponsorship is not None:
            query = query.eq('provides_sponsorship', requires_sponsorship)
        
        # Apply experience level filter
        query = query.ilike('experience_level', f'%{experience_level}%')
        
        # Apply specialization filter
        specialization_list = [spec.strip() for spec in specializations.split(',')]
        
        # Expand specializations with related terms
        expanded_specializations = []
        for spec in specialization_list:
            expanded_specializations.append(spec)
            if spec.lower() == 'frontend':
                expanded_specializations.extend(['front-end', 'front end', 'react', 'vue', 'angular'])
            elif spec.lower() == 'backend':
                expanded_specializations.extend(['back-end', 'back end', 'api', 'server'])
            elif spec.lower() == 'fullstack':
                expanded_specializations.extend(['full-stack', 'full stack'])
        
        spec_conditions = [f"specialization.ilike.%{spec}%" for spec in expanded_specializations]
        if spec_conditions:
            query = query.or_(','.join(spec_conditions))
        
        # Apply exclude IDs filter
        if excluded_job_ids:
            exclude_list = [id.strip() for id in excluded_job_ids.split(',')]
            query = query.not_.in_('id', exclude_list)
        
        # TEMPORARY: Filter out greenhouse jobs
        query = query.not_.ilike('job_url', '%greenhouse%')
        
        # Order by creation date (newest first) and limit
        query = query.order('created_at', desc=True).limit(limit)
        
        result = query.execute()
        jobs_data = result.data or []
        
        # Convert to response format
        jobs = [convert_job_to_response(job) for job in jobs_data]
        
        return jobs
        
    except Exception as e:
        logger.error("Error in get_recommended_jobs: %s", e)
        raise HTTPException(status_code=500, detail=f"Error getting recommended jobs: {str(e)}")

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str
):
    """
    Get a single job by ID
    """
    try:
        result = supabase_manager.client.table('jobs').select('*').eq('id', job_id).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_data = result.data[0]
        return convert_job_to_response(job_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in get_job: %s", e)
        raise HTTPException(status_code=500, detail=f"Error fetching job: {str(e)}")