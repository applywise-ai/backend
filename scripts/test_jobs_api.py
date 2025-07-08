#!/usr/bin/env python3
"""
Test script for Jobs API endpoints
"""

import requests
import json
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"
JOBS_API_URL = f"{API_BASE_URL}/jobs"

def test_health():
    """Test if the API is running"""
    print("🏥 Testing API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API is healthy")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False

def test_get_jobs_paginated():
    """Test paginated jobs endpoint"""
    print("\n📄 Testing paginated jobs...")
    try:
        response = requests.get(f"{JOBS_API_URL}/paginated?limit=5")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved paginated jobs")
            print(f"  - Jobs count: {len(data.get('jobs', []))}")
            print(f"  - Has more: {data.get('hasMore', False)}")
            print(f"  - Last job ID: {data.get('lastJobId', 'None')}")
            return data
        else:
            print(f"❌ Failed to get paginated jobs: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error testing paginated jobs: {e}")
        return None

def test_get_filtered_count():
    """Test filtered jobs count endpoint"""
    print("\n🔢 Testing filtered jobs count...")
    try:
        response = requests.get(f"{JOBS_API_URL}/filtered-count")
        if response.status_code == 200:
            count = response.json()
            print(f"✅ Retrieved filtered jobs count: {count}")
            return count
        else:
            print(f"❌ Failed to get filtered jobs count: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error testing filtered jobs count: {e}")
        return None

def test_get_total_available_count():
    """Test total available jobs count endpoint"""
    print("\n📊 Testing total available jobs count...")
    try:
        response = requests.get(f"{JOBS_API_URL}/total-available-count")
        if response.status_code == 200:
            count = response.json()
            print(f"✅ Retrieved total available jobs count: {count}")
            return count
        else:
            print(f"❌ Failed to get total available jobs count: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error testing total available jobs count: {e}")
        return None

def test_get_single_job(job_id: int):
    """Test getting a single job"""
    print(f"\n🎯 Testing single job retrieval (ID: {job_id})...")
    try:
        response = requests.get(f"{JOBS_API_URL}/{job_id}")
        if response.status_code == 200:
            job = response.json()
            if job:
                print(f"✅ Retrieved job: {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
                return job
            else:
                print("ℹ️ Job not found or expired (returned null)")
                return None
        else:
            print(f"❌ Failed to get single job: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error testing single job: {e}")
        return None

def test_get_bulk_jobs(job_ids: list):
    """Test bulk jobs retrieval"""
    print(f"\n📦 Testing bulk jobs retrieval ({len(job_ids)} jobs)...")
    try:
        job_ids_str = ",".join(map(str, job_ids))
        response = requests.get(f"{JOBS_API_URL}/bulk?job_ids={job_ids_str}")
        if response.status_code == 200:
            jobs = response.json()
            valid_jobs = [job for job in jobs if job is not None]
            print(f"✅ Retrieved {len(valid_jobs)} out of {len(job_ids)} requested jobs")
            return jobs
        else:
            print(f"❌ Failed to get bulk jobs: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error testing bulk jobs: {e}")
        return None

def test_jobs_with_filters():
    """Test jobs with various filters"""
    print("\n🔍 Testing jobs with filters...")
    
    # Test location filter
    try:
        response = requests.get(f"{JOBS_API_URL}/paginated?limit=3&location=San Francisco")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Location filter test: {len(data.get('jobs', []))} jobs in San Francisco")
        else:
            print(f"❌ Location filter test failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Location filter test error: {e}")
    
    # Test job type filter
    try:
        response = requests.get(f"{JOBS_API_URL}/paginated?limit=3&job_type=Full-time")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Job type filter test: {len(data.get('jobs', []))} full-time jobs")
        else:
            print(f"❌ Job type filter test failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Job type filter test error: {e}")

def test_advanced_search():
    """Test advanced search endpoint"""
    print("\n🔎 Testing advanced search...")
    try:
        response = requests.get(f"{JOBS_API_URL}/search/advanced?q=engineer&limit=5")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Advanced search test: {len(data.get('jobs', []))} jobs found for 'engineer'")
            print(f"  - Total count: {data.get('total_count', 0)}")
            print(f"  - Has more: {data.get('has_more', False)}")
            return data
        else:
            print(f"❌ Advanced search test failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Advanced search test error: {e}")
        return None

def main():
    """Run all tests"""
    print("🚀 Starting Jobs API Tests")
    print("=" * 50)
    
    # Test API health first
    if not test_health():
        print("\n❌ API is not healthy. Make sure the server is running.")
        return
    
    # Test paginated jobs
    paginated_data = test_get_jobs_paginated()
    
    # Test count endpoints
    filtered_count = test_get_filtered_count()
    total_count = test_get_total_available_count()
    
    # Test single job if we have jobs from pagination
    if paginated_data and paginated_data.get('jobs'):
        first_job = paginated_data['jobs'][0]
        job_id = first_job.get('id')
        if job_id:
            test_get_single_job(job_id)
            
            # Test bulk jobs with a few IDs
            job_ids = [job.get('id') for job in paginated_data['jobs'][:3] if job.get('id')]
            if job_ids:
                test_get_bulk_jobs(job_ids)
    
    # Test filters
    test_jobs_with_filters()
    
    # Test advanced search
    test_advanced_search()
    
    print("\n" + "=" * 50)
    print("🏁 Jobs API Tests Complete")

if __name__ == "__main__":
    main() 