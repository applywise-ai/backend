#!/usr/bin/env python3
"""
Test script for job description summarization using AI Assistant.
"""

import sys
import os
import pandas as pd
import logging

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.ai_assistant import AIAssistant

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_jobs_df():
    """Create a sample DataFrame with job descriptions for testing."""
    sample_jobs = [
        {
            'title': 'Senior Software Engineer',
            'company': 'TechCorp',
            'location': 'San Francisco, CA',
            'description': '''
            We are looking for a Senior Software Engineer to join our team.
            
            Responsibilities:
            - Lead development of complex web applications using React and Node.js
            - Mentor junior developers and conduct code reviews
            - Design and implement scalable microservices architecture
            - Collaborate with product managers to define technical requirements
            
            Requirements:
            - 7+ years of software development experience
            - Strong expertise in JavaScript/TypeScript, React, and Node.js
            - Experience with cloud platforms (AWS/GCP)
            - Bachelor's degree in Computer Science or related field
            - Must be eligible to work in the US (we provide H1B sponsorship)
            
            Salary: $150,000 - $220,000 annually
            Employment Type: Full-time
            '''
        },
        {
            'title': 'Data Scientist',
            'company': 'DataTech Inc',
            'location': 'New York, NY',
            'description': '''
            Join our data science team to build machine learning models.
            
            Key Responsibilities:
            - Develop and deploy machine learning models
            - Analyze large datasets to extract insights
            - Work with cross-functional teams to implement data-driven solutions
            - Present findings to stakeholders
            
            Qualifications:
            - 3+ years of experience in data science or related field
            - Proficiency in Python, R, SQL
            - Experience with ML frameworks (TensorFlow, PyTorch)
            - Master's degree in Statistics, Computer Science, or related field
            
            Compensation: $120,000 - $180,000
            Job Type: Full-time, Remote
            '''
        },
        {
            'title': 'Product Manager Intern',
            'company': 'StartupXYZ',
            'location': 'Austin, TX',
            'description': '''
            Summer internship opportunity for aspiring product managers.
            
            What you'll do:
            - Assist in product strategy and roadmap development
            - Conduct user research and market analysis
            - Work with engineering and design teams
            - Learn about agile development methodologies
            
            Requirements:
            - Currently pursuing a degree in Business, Engineering, or related field
            - Strong analytical and communication skills
            - Passion for technology and product development
            - Available for 12-week summer program
            
            Stipend: $5,000/month
            Duration: 3 months
            '''
        }
    ]
    
    return pd.DataFrame(sample_jobs)


def test_job_summarization():
    """Test the job summarization functionality."""
    try:
        # Create sample user profile (minimal for testing)
        user_profile = {
            'fullName': 'John Doe',
            'isProMember': True,  # Use Pro features for better results
            'currentLocation': 'San Francisco, CA'
        }
        
        # Create sample jobs DataFrame
        jobs_df = create_sample_jobs_df()
        
        print(f"Created sample DataFrame with {len(jobs_df)} jobs")
        print("Sample job titles:", jobs_df['title'].tolist())
        print()
        
        # Initialize AI Assistant
        print("Initializing AI Assistant...")
        ai_assistant = AIAssistant(user_profile)
        
        # Test job summarization
        print("Starting job summarization...")
        summarized_df = ai_assistant.summarize_job_descriptions(jobs_df, batch_size=2)
        
        # Display results
        print("\n" + "="*80)
        print("JOB SUMMARIZATION RESULTS")
        print("="*80)
        
        for idx, row in summarized_df.iterrows():
            print(f"\nJob {idx + 1}: {row['title']} at {row['company']}")
            print("-" * 50)
            print(f"Provides Sponsorship: {row['provides_sponsorship']}")
            print(f"Salary Range: ${row['salary_min_range']} - ${row['salary_max_range']}")
            print(f"Short Responsibilities: {row['short_responsibilities']}")
            print(f"Short Qualifications: {row['short_qualifications']}")
            print(f"Responsibilities ({len(row['responsibilities'])} items):")
            for i, resp in enumerate(row['responsibilities'], 1):
                print(f"  {i}. {resp}")
            print(f"Requirements ({len(row['requirements'])} items):")
            for i, req in enumerate(row['requirements'], 1):
                print(f"  {i}. {req}")
            print()
        
        # Save results to CSV
        output_file = "summarized_jobs.csv"
        summarized_df.to_csv(output_file, index=False)
        print(f"Results saved to {output_file}")
        
        return summarized_df
        
    except Exception as e:
        logger.error(f"Error in job summarization test: {str(e)}")
        raise


if __name__ == "__main__":
    print("Testing Job Description Summarization")
    print("=" * 50)
    
    try:
        result_df = test_job_summarization()
        print("\n✅ Job summarization test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        sys.exit(1) 