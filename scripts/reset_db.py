import time
import sys
import os
from datetime import datetime
from typing import List

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.db.postgres import PostgresManager
from app.core.config import settings
from sqlalchemy import text

def create_jobs_table(postgres_manager: PostgresManager):
    """Create jobs table if it doesn't exist"""
    print("[5] Dropping existing jobs table...")
    start_time = time.time()
        
    session = postgres_manager.SessionLocal()
    try:
        session.execute(text("DROP TABLE IF EXISTS jobs CASCADE"))
        session.commit()
    finally:
        session.close()
        
        end_time = time.time()
    print(f"[6] Table dropped in {end_time - start_time:.2f} seconds")
    
    print("[7] Creating new jobs table with all fields...")
    start_time = time.time()
    
    session = postgres_manager.SessionLocal()
    try:
        session.execute(text("""
            CREATE TABLE jobs (
                id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            company VARCHAR(255) NOT NULL,
                logo VARCHAR(500),
                location VARCHAR(255),
                salary_min_range DECIMAL,
                salary_max_range DECIMAL,
                salary_currency VARCHAR(10),
                job_type VARCHAR(100),
                description TEXT,
                company_description TEXT,
                company_size VARCHAR(50),
                experience_level VARCHAR(100),
                specialization VARCHAR(100),
                responsibilities JSONB,
                requirements JSONB,
                skills JSONB,
                job_url VARCHAR(500),
                score DECIMAL,
                tags JSONB,
                short_responsibilities TEXT,
                short_qualifications TEXT,
            is_verified BOOLEAN DEFAULT FALSE,
            is_sponsored BOOLEAN DEFAULT FALSE,
            provides_sponsorship BOOLEAN DEFAULT FALSE,
            expired BOOLEAN DEFAULT FALSE,
                is_remote BOOLEAN DEFAULT FALSE,
                posted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """))
        session.commit()
    finally:
        session.close()
    
    end_time = time.time()
    print(f"[8] Table creation completed in {end_time - start_time:.2f} seconds")

def insert_sample_job(postgres_manager: PostgresManager):
    """Insert a sample job into the jobs table"""
    print("[9] Preparing sample job data...")
    
    # Generate a unique string ID
    import uuid
    import json
    job_id = str(uuid.uuid4())
    
    job_data = {
        "id": job_id,
        "title": "Senior Software Engineer",
        "company": "TechCorp Innovation",
        "logo": "https://example.com/techcorp-logo.png",
        "location": "San Francisco, CA (Hybrid)",
        "salary_min_range": 150000.00,
        "salary_max_range": 220000.00,
        "salary_currency": "USD",
        "job_type": "Full-time",
        "description": "TechCorp Innovation is seeking a Senior Software Engineer to join our rapidly growing team. You'll be working on cutting-edge technology solutions that help businesses transform their digital presence.",
        "company_description": "TechCorp Innovation is a leading technology company specializing in digital transformation solutions for enterprise clients.",
        "company_size": "medium",
        "experience_level": "Senior",
        "specialization": "Full Stack Development",
        "responsibilities": json.dumps([
            "Lead the development of complex web applications using React and Node.js",
            "Mentor junior developers and conduct code reviews",
            "Design and implement scalable microservices architecture",
            "Collaborate with product managers to define technical requirements"
        ]),
        "requirements": json.dumps([
            "7+ years of software development experience",
            "Strong expertise in JavaScript/TypeScript, React, and Node.js",
            "Experience with cloud platforms (AWS/GCP)",
            "Bachelor's degree in Computer Science or related field"
        ]),
        "skills": json.dumps(["JavaScript", "TypeScript", "React", "Node.js", "AWS"]),
        "job_url": "https://techcorp.com/careers/senior-software-engineer",
        "score": 0.95,
        "tags": json.dumps(["react", "nodejs", "typescript", "aws", "senior", "full-stack"]),
        "short_responsibilities": "Lead development of web applications, mentor team members, design architecture",
        "short_qualifications": "7+ years exp, JS/TS, React, Node.js, Cloud platforms",
        "is_verified": True,
        "is_sponsored": False,
        "provides_sponsorship": True,
        "expired": False,
        "is_remote": True,
        "posted_date": datetime.now()
    }
    
    print("[10] Executing INSERT query...")
    start_time = time.time()
    
    session = postgres_manager.SessionLocal()
    try:
        session.execute(text("""
        INSERT INTO jobs (
                id, title, company, logo, location, salary_min_range, salary_max_range, salary_currency, job_type,
                description, company_description, company_size, experience_level, specialization, responsibilities, 
                requirements, skills, job_url, score, tags, short_responsibilities, short_qualifications, 
                is_verified, is_sponsored, provides_sponsorship, expired, is_remote, posted_date
            ) VALUES (
                :id, :title, :company, :logo, :location, :salary_min_range, :salary_max_range, 
                :salary_currency, :job_type, :description, :company_description, :company_size, 
                :experience_level, :specialization, :responsibilities, :requirements, :skills, 
                :job_url, :score, :tags, :short_responsibilities, :short_qualifications, 
                :is_verified, :is_sponsored, :provides_sponsorship, :expired, :is_remote, :posted_date
            )
        """), job_data)
        session.commit()
    finally:
        session.close()
    
    end_time = time.time()
    print(f"[11] INSERT query executed in {end_time - start_time:.2f} seconds")
    
    return job_id

def main():
    print("[1] Starting job insertion script...")
    script_start_time = time.time()
    
    try:
        # Initialize PostgresManager
        print("[2] Initializing PostgresManager...")
        start_time = time.time()
        postgres_manager = PostgresManager()
        end_time = time.time()
        print(f"[3] PostgresManager initialized in {end_time - start_time:.2f} seconds")
        
        # Test connection
        print("[4] Testing database connection...")
        start_time = time.time()
        session = postgres_manager.SessionLocal()
        try:
            result = session.execute(text("SELECT 1"))
            result.fetchone()
        finally:
            session.close()
        end_time = time.time()
        print(f"[5] Connection test successful in {end_time - start_time:.2f} seconds")
        
        # Create jobs table
        create_jobs_table(postgres_manager)
        
    except Exception as e:
        print(f"[ERROR] An error occurred: {e}")
        return
    finally:
        print("[13] Script completed")
    
    script_end_time = time.time()
    print(f"[14] Total execution time: {script_end_time - script_start_time:.2f} seconds")

if __name__ == "__main__":
    main()