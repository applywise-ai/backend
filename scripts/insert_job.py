import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
import time

print("[1] Script started")

# Load environment variables
load_dotenv()
print("[2] Environment variables loaded")

# Database connection parameters with timeouts
DB_PARAMS = {
    "host": os.getenv("POSTGRES_HOST", "172.31.85.170"),
    "database": os.getenv("POSTGRES_DB", "applywise"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    # Add timeout parameters
    "connect_timeout": 10,  # Connection timeout in seconds
    "options": "-c statement_timeout=30000"  # Statement timeout in milliseconds (30 seconds)
}

print("[3] Database parameters:", {k: v for k, v in DB_PARAMS.items() if k != 'password'})

def test_connection():
    """Test database connection and print detailed error if it fails"""
    try:
        print("[4] Testing database connection...")
        start_time = time.time()
        
        # Try to connect
        conn = psycopg2.connect(**DB_PARAMS)
        conn.close()
        
        end_time = time.time()
        print(f"[5] Test connection successful! Time taken: {end_time - start_time:.2f} seconds")
        return True
        
    except psycopg2.OperationalError as e:
        print("\n[ERROR] Database connection failed!")
        print("Common issues and solutions:")
        print("1. VPN not connected - Please check your VPN connection")
        print("2. RDS instance not accessible - Verify security group rules")
        print("3. Wrong credentials - Check your .env file")
        print(f"4. Timeout - Current timeout is {DB_PARAMS['connect_timeout']} seconds")
        print(f"\nDetailed error: {str(e)}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error during connection test: {str(e)}")
        return False

class Job(BaseModel):
    """Pydantic model matching the TypeScript Job interface"""
    id: Optional[int] = None
    title: str
    company: str
    logo: str
    location: str
    salary: str
    salary_value: float  # Numeric value for filtering
    job_type: str
    posted_date: datetime
    description: str
    is_verified: bool = False
    is_sponsored: bool = False
    provides_sponsorship: bool = False
    experience_level: str
    specialization: Optional[str] = None
    responsibilities: List[str] = []
    requirements: List[str] = []
    job_url: Optional[str] = None
    score: Optional[float] = None
    tags: List[str] = []
    short_responsibilities: Optional[str] = None
    short_qualifications: Optional[str] = None
    expired: bool = False

print("[4] Job model defined")

def create_jobs_table(cursor):
    """Create jobs table if it doesn't exist"""
    print("[5] Creating jobs table if not exists...")
    start_time = time.time()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            company VARCHAR(255) NOT NULL,
            logo TEXT NOT NULL,
            location VARCHAR(255) NOT NULL,
            salary VARCHAR(255) NOT NULL,
            salary_value DECIMAL NOT NULL,
            job_type VARCHAR(50) NOT NULL,
            posted_date TIMESTAMP NOT NULL,
            description TEXT NOT NULL,
            is_verified BOOLEAN DEFAULT FALSE,
            is_sponsored BOOLEAN DEFAULT FALSE,
            provides_sponsorship BOOLEAN DEFAULT FALSE,
            experience_level VARCHAR(50) NOT NULL,
            specialization VARCHAR(255),
            responsibilities TEXT[],
            requirements TEXT[],
            job_url TEXT,
            score DECIMAL,
            tags TEXT[],
            short_responsibilities TEXT,
            short_qualifications TEXT,
            expired BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    end_time = time.time()
    print(f"[6] Table creation completed in {end_time - start_time:.2f} seconds")

def insert_sample_job(cursor):
    """Insert a sample job into the jobs table"""
    print("[7] Preparing sample job data...")
    
    job_data = {
        "title": "Senior Software Engineer",
        "company": "TechCorp Innovation",
        "logo": "https://example.com/techcorp-logo.png",
        "location": "San Francisco, CA (Hybrid)",
        "salary": "$150,000 - $220,000 annually",
        "salary_value": 185000.00,  # Average of the range
        "job_type": "Full-time",
        "posted_date": datetime.now(),
        "description": """TechCorp Innovation is seeking a Senior Software Engineer to join our rapidly growing team. 
        You'll be working on cutting-edge technology solutions that help businesses transform their digital presence.""",
        "is_verified": True,
        "is_sponsored": False,
        "provides_sponsorship": True,
        "experience_level": "Senior",
        "specialization": "Full Stack Development",
        "responsibilities": [
            "Lead the development of complex web applications using React and Node.js",
            "Mentor junior developers and conduct code reviews",
            "Design and implement scalable microservices architecture",
            "Collaborate with product managers to define technical requirements"
        ],
        "requirements": [
            "7+ years of software development experience",
            "Strong expertise in JavaScript/TypeScript, React, and Node.js",
            "Experience with cloud platforms (AWS/GCP)",
            "Bachelor's degree in Computer Science or related field"
        ],
        "job_url": "https://techcorp.com/careers/senior-software-engineer",
        "score": 0.95,
        "tags": ["react", "nodejs", "typescript", "aws", "senior", "full-stack"],
        "short_responsibilities": "Lead development of web applications, mentor team members, design architecture",
        "short_qualifications": "7+ years exp, JS/TS, React, Node.js, Cloud platforms",
        "expired": False
    }
    
    print("[8] Executing INSERT query...")
    start_time = time.time()
    
    cursor.execute("""
        INSERT INTO jobs (
            title, company, logo, location, salary, salary_value, job_type, 
            posted_date, description, is_verified, is_sponsored, provides_sponsorship,
            experience_level, specialization, responsibilities, requirements,
            job_url, score, tags, short_responsibilities, short_qualifications, expired
        )
        VALUES (
            %(title)s, %(company)s, %(logo)s, %(location)s, %(salary)s, %(salary_value)s,
            %(job_type)s, %(posted_date)s, %(description)s, %(is_verified)s, %(is_sponsored)s,
            %(provides_sponsorship)s, %(experience_level)s, %(specialization)s, %(responsibilities)s,
            %(requirements)s, %(job_url)s, %(score)s, %(tags)s, %(short_responsibilities)s,
            %(short_qualifications)s, %(expired)s
        )
        RETURNING id
    """, job_data)
    
    job_id = cursor.fetchone()[0]
    end_time = time.time()
    print(f"[9] Insert completed in {end_time - start_time:.2f} seconds")
    return job_id

def main():
    # First test the connection
    if not test_connection():
        print("[ERROR] Exiting due to connection failure")
        return

    conn = None
    cursor = None
    try:
        print("[10] Establishing main database connection...")
        start_time = time.time()
        
        # Connect to the database
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        end_time = time.time()
        print(f"[11] Database connection established in {end_time - start_time:.2f} seconds")
        
        # Create table if it doesn't exist
        create_jobs_table(cursor)
        
        # Insert sample job
        job_id = insert_sample_job(cursor)
        
        # Commit the transaction
        print("[12] Committing transaction...")
        start_time = time.time()
        conn.commit()
        end_time = time.time()
        print(f"[13] Transaction committed in {end_time - start_time:.2f} seconds")
        
        print(f"[14] Successfully inserted job with ID: {job_id}")
        
    except psycopg2.OperationalError as e:
        print(f"[ERROR] Database operation failed: {str(e)}")
        if conn:
            print("[ERROR] Rolling back transaction...")
            conn.rollback()
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {str(e)}")
        if conn:
            print("[ERROR] Rolling back transaction...")
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
            print("[15] Cursor closed")
        if conn:
            conn.close()
            print("[16] Database connection closed")
            
    print("[17] Script completed")

if __name__ == "__main__":
    script_start_time = time.time()
    main()
    script_end_time = time.time()
    print(f"[18] Total execution time: {script_end_time - script_start_time:.2f} seconds") 