from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


class ApplicationStatus(str, Enum):
    """Application status matching frontend TypeScript interface"""
    PENDING = "Pending"    # Initial state when job is being processed
    PROCESSING = "Processing"  # When job is actively being processed
    DRAFT = "Draft"        # After processing, ready for user to review and submit
    APPLIED = "Applied"
    SAVED = "Saved"
    REJECTED = "Rejected"
    INTERVIEWING = "Interviewing"
    EXPIRED = "Expired"
    ACCEPTED = "Accepted"
    FAILED = "Failed"      # When job application processing fails


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class Education(BaseModel):
    school: str
    degree: str
    fieldOfStudy: str
    educationFrom: datetime
    educationTo: Optional[datetime]
    educationGpa: Optional[float]
    educationEndMonth: Optional[str]
    educationEndYear: Optional[str]
    educationStartMonth: Optional[str]
    educationStartYear: Optional[str]


class Employment(BaseModel):
    company: str
    position: str
    employmentFrom: datetime
    employmentTo: Optional[datetime]
    employmentDescription: str
    employmentLocation: str


class Project(BaseModel):
    projectName: str
    projectDescription: str
    projectLink: Optional[str]


class UserProfile(BaseModel):
    # Personal Information
    fullName: str
    email: str
    phoneNumber: Optional[str]
    currentLocation: Optional[str]
    resumeUrl: Optional[str]
    resumeFilename: Optional[str]
    resumeAutofill: Optional[Dict[str, Any]]

    # Social Links
    linkedin: Optional[str]
    twitter: Optional[str]
    github: Optional[str]
    portfolio: Optional[str]

    # Demographics
    gender: Optional[List[str]]
    veteran: Optional[bool]
    sexuality: Optional[List[str]]
    race: Optional[List[str]]
    hispanic: Optional[bool]
    disability: Optional[bool]
    trans: Optional[bool]

    # Work Eligibility
    eligibleCanada: Optional[bool]
    eligibleUS: Optional[bool]
    usSponsorship: Optional[bool]
    caSponsorship: Optional[bool]
    over18: Optional[bool]

    # Job Preferences
    noticePeriod: Optional[str]
    expectedSalary: Optional[str]
    jobTypes: Optional[List[JobType]]
    locationPreferences: Optional[List[str]]
    roleLevel: Optional[str]
    industrySpecializations: Optional[List[str]]
    companySize: Optional[str]

    # Notification Preferences
    newJobMatches: Optional[bool]
    autoApplyWithoutReview: Optional[bool]
    ignorePartialProfileAlert: Optional[bool]

    # Subscription
    isProMember: Optional[bool]
    aiCredits: Optional[int]

    # Education
    education: List[Education] = []

    # Employment
    employment: List[Employment] = []

    # Skills
    skills: List[str] = []

    # Source
    source: Optional[str]

    # Projects
    projects: List[Project] = []

    # Job Feedback
    likedJobs: List[str] = []
    dislikedJobs: List[str] = []


class QuestionType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FILE = "file"
    DATE = "date"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"


class FormSectionType(str, Enum):
    PERSONAL = "personal"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    SKILLS = "skills"
    ADDITIONAL = "additional"


class FileType(str, Enum):
    RESUME = "resume"
    COVER_LETTER = "cover_letter"
    PORTFOLIO = "portfolio"
    OTHER = "other"


class Answer(BaseModel):
    """Answer model that can handle different types of answers"""
    value: Union[str, List[str], bool, int, float]
    file_url: Optional[str] = None
    file_name: Optional[str] = None


class FormQuestion(BaseModel):
    """Form question model matching frontend interface"""
    id: str
    question: str
    answer: Union[str, Dict[str, Union[str, int, bool, None]]]  # Matches frontend Answer type
    type: QuestionType
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None
    section: FormSectionType
    file_type: Optional[FileType] = None
    required: Optional[bool] = False


class JobApplicationCreate(BaseModel):
    user_id: str
    job_url: HttpUrl
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    resume_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
    application_data: Optional[Dict[str, Any]] = None


class JobApplicationResponse(BaseModel):
    id: str
    job_id: str
    job_url: str
    company_name: Optional[str]
    job_title: Optional[str]
    status: str
    screenshot_urls: Optional[List[str]]
    error_message: Optional[str]
    created_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    status: ApplicationStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PrepareJobRequest(BaseModel):
    """Request model for preparing a job application"""
    job_id: str


class ApplyJobRequest(BaseModel):
    """Request model for job application submission"""
    job_id: str
    application_id: str


class ApplyJobResponse(BaseModel):
    """Response model for job application submission"""
    application_id: str
    status: ApplicationStatus
    message: str


class ApplicationResponse(BaseModel):
    """Response model for a single application"""
    id: str
    user_id: str
    job_id: str
    status: ApplicationStatus
    form_questions: List[FormQuestion]
    applied_date: Optional[datetime] = None
    last_updated: datetime
    created_at: datetime
    resume_url: Optional[str] = None
    resume_filename: Optional[str] = None
    cover_letter_url: Optional[str] = None
    cover_letter_filename: Optional[str] = None
    screenshots: List[str] = []


class UserApplicationsResponse(BaseModel):
    """Response model for user applications list"""
    applications: List[ApplicationResponse]
    total: int


class SaveFormRequest(BaseModel):
    """Request model for saving form questions"""
    application_id: str
    form_questions: List[FormQuestion]


class SaveFormResponse(BaseModel):
    """Response model for saving form questions"""
    application_id: str
    status: ApplicationStatus
    message: str 