from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    logo = Column(String)
    location = Column(String)
    salary = Column(String)
    salary_value = Column(Float)
    job_type = Column(String)
    description = Column(Text)
    experience_level = Column(String)
    specialization = Column(String)
    responsibilities = Column(JSON)  # List of strings
    requirements = Column(JSON)  # List of strings
    job_url = Column(String)  # Database column is job_url
    score = Column(Float)
    tags = Column(JSON)  # List of strings
    short_responsibilities = Column(String)
    short_qualifications = Column(String)
    is_verified = Column(Boolean, default=False)
    is_sponsored = Column(Boolean, default=False)
    provides_sponsorship = Column(Boolean, default=False)
    expired = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class JobApplication(Base):
    __tablename__ = "job_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True, nullable=False)
    job_url = Column(String, nullable=False)
    company_name = Column(String)
    job_title = Column(String)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    
    # Application data
    resume_path = Column(String)
    cover_letter_path = Column(String)
    application_data = Column(JSON)  # Store form data, answers, etc.
    
    # Results
    screenshot_urls = Column(JSON)  # List of screenshot URLs
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    logs = relationship("ApplicationLog", back_populates="application")


class ApplicationLog(Base):
    __tablename__ = "application_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("job_applications.id"))
    level = Column(String)  # info, warning, error
    message = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    application = relationship("JobApplication", back_populates="logs")


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(String, unique=True, index=True)
    session_id = Column(String)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 