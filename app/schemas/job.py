from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List
from datetime import datetime

class JobBase(BaseModel):
    """Base Job model with common attributes"""
    title: str = Field(..., min_length=1, max_length=255)
    company: str = Field(..., min_length=1, max_length=255)
    company_url: Optional[HttpUrl] = None
    logo: Optional[HttpUrl] = None
    company_description: Optional[str] = None
    location: Optional[str] = Field(None, min_length=1, max_length=255)
    salary_min_range: Optional[float] = Field(None, gt=0)
    salary_max_range: Optional[float] = Field(None, gt=0)
    salary_currency: Optional[str] = Field(None, min_length=1, max_length=50)
    job_type: str = Field(..., min_length=1, max_length=50)
    description: str
    posted_date: datetime
    experience_level: str = Field(..., min_length=1, max_length=50)
    specialization: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    job_url: Optional[HttpUrl] = None
    skills: List[str] = Field(default_factory=list)
    short_responsibilities: Optional[str] = None
    short_qualifications: Optional[str] = None
    is_remote: bool = False
    is_verified: bool = False
    is_sponsored: bool = False
    provides_sponsorship: bool = False
    expired: bool = False

class JobCreate(BaseModel):
    id: str
    title: str
    company: str
    company_url: Optional[str] = None
    logo: Optional[str] = None
    location: Optional[str] = None
    salary_min_range: Optional[float] = None
    salary_max_range: Optional[float] = None
    salary_currency: Optional[str] = None
    job_type: Optional[str] = None
    description: Optional[str] = None
    company_description: Optional[str] = None
    company_size: Optional[str] = None
    experience_level: Optional[str] = None
    specialization: Optional[str] = None
    responsibilities: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    job_url: Optional[str] = None
    score: Optional[float] = None
    tags: Optional[List[str]] = None
    short_responsibilities: Optional[str] = None
    short_qualifications: Optional[str] = None
    is_verified: Optional[bool] = True
    is_sponsored: Optional[bool] = False
    provides_sponsorship: Optional[bool] = False
    expired: Optional[bool] = False
    is_remote: Optional[bool] = False
    posted_date: Optional[datetime] = None

class JobInDB(JobBase):
    """Schema for job as stored in database"""
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class JobResponse(JobInDB):
    """Schema for job response"""
    pass  # Same as JobInDB for now, but can be extended if needed

class JobFilters(BaseModel):
    """Schema for job filtering parameters"""
    location: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    company: Optional[str] = None
    title: Optional[str] = None
    provides_sponsorship: Optional[bool] = None
    is_verified: Optional[bool] = None
    tags: Optional[List[str]] = None

class JobsPaginatedResponse(BaseModel):
    """Schema for paginated jobs response"""
    jobs: List[JobResponse]
    has_more: bool
    last_job_id: Optional[str] = None
    total_count: int
    filtered_count: int

class JobsCountResponse(BaseModel):
    """Schema for jobs count response"""
    filtered_count: int
    total_available: int

class JobsSearchResponse(BaseModel):
    """Schema for advanced job search response"""
    jobs: List[JobResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool

class JobsResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    lastJobId: Optional[str] = None

# Example of how to use the schema:
"""
# Creating a new job
new_job = JobCreate(
    title="Senior Software Engineer",
    company="TechCorp Innovation",
    logo="https://example.com/techcorp-logo.png",
    location="San Francisco, CA (Hybrid)",
    salary="$150,000 - $220,000 annually",
    salary_value=185000.00,
    job_type="Full-time",
    description="TechCorp Innovation is seeking a Senior Software Engineer...",
    experience_level="Senior",
    specialization="Full Stack Development",
    responsibilities=[
        "Lead development of web applications",
        "Mentor junior developers"
    ],
    requirements=[
        "7+ years of software development experience",
        "Strong expertise in JavaScript/TypeScript"
    ],
    job_url="https://techcorp.com/careers/senior-software-engineer",
    score=0.95,
    tags=["react", "nodejs", "typescript"],
    short_responsibilities="Lead development, mentor team",
    short_qualifications="7+ years exp, JS/TS",
    is_verified=True,
    provides_sponsorship=True
)
""" 