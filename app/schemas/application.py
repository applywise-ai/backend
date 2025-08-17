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
    NOT_FOUND = "Not Found" # When job no longer exists


class JobType(str, Enum):
    FULL_TIME = "fulltime"
    PART_TIME = "temporary"
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
    resume: Optional[str]
    resumeFilename: Optional[str]
    resumeAutofill: Optional[Dict[str, Any]]
    coverLetterPath: Optional[str]
    coverLetterFilename: Optional[str]

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

# Field types enum
class QuestionType(Enum):
    """Field types enum."""
    INPUT = "text"
    NUMBER = "number"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTISELECT = "multiselect"
    DATE = "date"
    FILE = "file"
    CHECKBOX = "checkbox"

class FormSectionType(str, Enum):
    PERSONAL = "personal"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    RESUME = "resume"
    COVER_LETTER = "cover_letter"
    ADDITIONAL = "additional"
    DEMOGRAPHIC = "demographic"

AnswerType = Union[str, int, List[int], List[str]]

class FormQuestion(BaseModel):
    """Form question model matching frontend interface"""
    unique_label_id: str
    question: str
    answer: Optional[AnswerType] = None
    type: QuestionType
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None
    section: FormSectionType
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    required: Optional[bool] = False
    pruned: Optional[bool] = False
    ai_custom: Optional[bool] = False

    class Config:
        use_enum_values = True  # Use enum values instead of enum objects for JSON serialization


class TaskStatusResponse(BaseModel):
    status: ApplicationStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PrepareJobRequest(BaseModel):
    """Request model for preparing a job application"""
    job_id: str


class ApplyJobRequest(BaseModel):
    """Request model for job application submission"""
    application_id: str


class ApplyJobResponse(BaseModel):
    """Response model for job application submission"""
    application_id: str
    status: ApplicationStatus
    message: str

class SaveFormRequest(BaseModel):
    """Request model for saving form questions"""
    application_id: str
    form_questions: List[FormQuestion]


class SaveFormResponse(BaseModel):
    """Response model for saving form questions"""
    application_id: str
    status: ApplicationStatus
    message: str


class GenerateCoverLetterRequest(BaseModel):
    """Request model for generating cover letter"""
    job_id: str
    prompt: Optional[str] = None


class GenerateCoverLetterResponse(BaseModel):
    """Response model for cover letter generation"""
    application_id: str
    cover_letter_path: str
    message: str


class GenerateCustomAnswerRequest(BaseModel):
    """Request model for generating custom answers"""
    job_description: str
    question: str
    prompt: Optional[str] = None


class GenerateCustomAnswerResponse(BaseModel):
    """Response model for custom answer generation"""
    answer: str
    message: str 