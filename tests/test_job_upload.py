#!/usr/bin/env python3
"""
Test script to upload backend_jobs_raw.csv to the database using the fetch jobs service.
"""

import sys
import os
import pandas as pd
import logging
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.fetch_jobs.main import JobFetcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_job_upload():
    """
    Test uploading backend_jobs_raw.csv to the database.
    """
    print("🧪 Testing job upload with backend_jobs_raw.csv...")
    
    # Path to the CSV file
    csv_file = "all_jobs_raw.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return
    
    try:
        # Load the CSV file
        print(f"📖 Loading CSV file: {csv_file}")
        jobs_df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(jobs_df)} jobs from CSV")
        
        # Display basic information about the data
        print("\n📊 Data Overview:")
        print(f"   Total rows: {len(jobs_df)}")
        print(f"   Columns: {list(jobs_df.columns)}")
        
        # Show sample of key columns
        print("\n🔍 Sample Data:")
        sample_cols = ['title', 'company', 'location', 'salary_min_range', 'salary_max_range', 'salary_currency']
        for col in sample_cols:
            if col in jobs_df.columns:
                non_null_count = jobs_df[col].notna().sum()
                print(f"   {col}: {non_null_count}/{len(jobs_df)} non-null values")
        
        # Initialize JobFetcher
        print("\n🚀 Initializing JobFetcher...")
        job_fetcher = JobFetcher()
        
        # Test the formatting function
        print("\n🔧 Testing job formatting...")
        formatted_df = job_fetcher._format_for_upload(jobs_df)
        print(f"✅ Formatted {len(formatted_df)} jobs")
        
        # Display formatting results
        if 'job_level' in formatted_df.columns:
            unique_levels = formatted_df['job_level'].unique()
            print(f"   Job levels after formatting: {unique_levels}")
        
        if 'location' in formatted_df.columns:
            unique_locations = formatted_df['location'].unique()
            print(f"   Locations after formatting: {unique_locations}")
        
        # Test the upload function
        print("\n🗄️ Testing database upload...")
        upload_stats = job_fetcher.upload_jobs(jobs_df)
        
        # Display upload results
        print("\n📈 Upload Results:")
        print(f"   Total rows processed: {upload_stats['total_rows']}")
        print(f"   ✅ Successful uploads: {upload_stats['successful_uploads']}")
        print(f"   ❌ Failed uploads: {upload_stats['failed_uploads']}")
        
        if 'skipped_duplicates' in upload_stats:
            print(f"   ⏭️ Skipped duplicates: {upload_stats['skipped_duplicates']}")
        
        if upload_stats['errors']:
            print(f"   ⚠️ Errors: {len(upload_stats['errors'])}")
            for error in upload_stats['errors'][:3]:  # Show first 3 errors
                print(f"      - {error}")
        
        # Calculate success rate
        success_rate = (upload_stats['successful_uploads'] / upload_stats['total_rows']) * 100 if upload_stats['total_rows'] > 0 else 0
        print(f"\n🎉 Upload completed with {success_rate:.1f}% success rate!")
        
        if success_rate >= 90:
            print("✅ Test PASSED - High success rate achieved!")
        elif success_rate >= 70:
            print("⚠️ Test PARTIAL - Moderate success rate, some issues detected")
        else:
            print("❌ Test FAILED - Low success rate, significant issues detected")
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = test_job_upload()
    sys.exit(0 if success else 1) 