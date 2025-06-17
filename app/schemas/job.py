from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field, constr, confloat

class JobBase(BaseModel):
    """Base Job model with common attributes"""
    title: constr(min_length=1, max_length=255)
    company: constr(min_length=1, max_length=255)
    logo: HttpUrl
    location: constr(min_length=1, max_length=255)
    salary: constr(min_length=1, max_length=255)
    salary_value: confloat(gt=0)  # Must be positive
    job_type: constr(min_length=1, max_length=50)
    description: str
    experience_level: constr(min_length=1, max_length=50)
    specialization: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    job_url: Optional[HttpUrl] = None
    score: Optional[float] = Field(None, ge=0, le=1)  # Score between 0 and 1
    tags: List[str] = Field(default_factory=list)
    short_responsibilities: Optional[str] = None
    short_qualifications: Optional[str] = None
    is_verified: bool = False
    is_sponsored: bool = False
    provides_sponsorship: bool = False
    expired: bool = False

class JobCreate(JobBase):
    """Schema for creating a new job"""
    posted_date: datetime = Field(default_factory=datetime.now)

class JobUpdate(BaseModel):
    """Schema for updating an existing job"""
    title: Optional[constr(min_length=1, max_length=255)] = None
    company: Optional[constr(min_length=1, max_length=255)] = None
    logo: Optional[HttpUrl] = None
    location: Optional[constr(min_length=1, max_length=255)] = None
    salary: Optional[constr(min_length=1, max_length=255)] = None
    salary_value: Optional[confloat(gt=0)] = None
    job_type: Optional[constr(min_length=1, max_length=50)] = None
    description: Optional[str] = None
    experience_level: Optional[constr(min_length=1, max_length=50)] = None
    specialization: Optional[str] = None
    responsibilities: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    job_url: Optional[HttpUrl] = None
    score: Optional[float] = Field(None, ge=0, le=1)
    tags: Optional[List[str]] = None
    short_responsibilities: Optional[str] = None
    short_qualifications: Optional[str] = None
    is_verified: Optional[bool] = None
    is_sponsored: Optional[bool] = None
    provides_sponsorship: Optional[bool] = None
    expired: Optional[bool] = None

class JobInDB(JobBase):
    """Schema for job as stored in database"""
    id: int
    posted_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class JobResponse(JobInDB):
    """Schema for job response"""
    pass  # Same as JobInDB for now, but can be extended if needed

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