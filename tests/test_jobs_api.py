#!/usr/bin/env python3
"""
Simple test script to verify the Jobs API endpoints are working.
"""

import requests
import json
import sys
from typing import Dict, Any

# API base URL
BASE_URL = "http://localhost:8000/jobs"

def test_endpoint(endpoint: str, params: Dict[str, Any] = None, description: str = "") -> bool:
    """
    Test an API endpoint and print results.
    
    Args:
        endpoint: API endpoint path
        params: Query parameters
        description: Description of the test
        
    Returns:
        bool: True if successful, False otherwise
    """
    url = f"{BASE_URL}{endpoint}"
    
    print(f"\n🧪 Testing: {description}")
    print(f"   URL: {url}")
    if params:
        print(f"   Params: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print(f"   ✅ Success! Found {len(data)} jobs")
            elif isinstance(data, dict) and 'jobs' in data:
                print(f"   ✅ Success! Found {len(data['jobs'])} jobs")
                print(f"   Has more: {data.get('hasMore', 'N/A')}")
            elif isinstance(data, (int, float)):
                print(f"   ✅ Success! Count: {data}")
            else:
                print(f"   ✅ Success! Response received")
            
            return True
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection failed - Is the server running on {BASE_URL}?")
        return False
    except requests.exceptions.Timeout:
        print(f"   ❌ Request timed out")
        return False
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False

def main():
    """Run all API tests."""
    print("🚀 Testing Jobs API Endpoints")
    print("=" * 50)
    
    # Check if server is running
    print("\n🔍 Checking if server is running...")
    try:
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Server is running!")
        else:
            print(f"⚠️ Server responded with status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Please start the server first.")
        print("   Run: uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Error connecting to server: {str(e)}")
        return False
    
    # Test endpoints
    tests = [
        # Basic pagination
        ("/paginated", {"limit": 5}, "Get paginated jobs (limit 5)"),
        
        # With search query (now includes skills)
        ("/paginated", {"limit": 3, "q": "python"}, "Search for 'python' in title/company/description/skills (limit 3)"),
        
        # With multiple locations
        ("/paginated", {"limit": 3, "location": "San Francisco,New York"}, "Get jobs in multiple locations (limit 3)"),
        
        # With multiple specializations
        ("/paginated", {"limit": 3, "specialization": "backend,frontend"}, "Get jobs with multiple specializations (limit 3)"),
        
        # With sorting
        ("/paginated", {"limit": 3, "sort_by": "salary_max_range", "sort_order": "desc"}, "Get jobs sorted by salary (limit 3)"),
        
        # With filters
        ("/paginated", {"limit": 3, "job_type": "fulltime"}, "Get fulltime jobs (limit 3)"),
        ("/paginated", {"limit": 3, "experience_level": "senior"}, "Get senior level jobs (limit 3)"),
        
        # Combined search, sort, and filter
        ("/paginated", {"limit": 3, "q": "react", "location": "San Francisco,Remote", "specialization": "frontend"}, "Search 'react' with multiple filters (limit 3)"),
        
        # Test excluded_job_ids parameter
        ("/paginated", {"limit": 3, "excluded_job_ids": "test1,test2"}, "Get jobs excluding specific IDs (limit 3)"),
        
        # Recommended jobs endpoint
        ("/recommended", {"experience_level": "senior", "specializations": "backend,frontend", "limit": 5}, "Get recommended jobs for senior backend/frontend (limit 5)"),
        ("/recommended", {"experience_level": "senior", "specializations": "backend", "excluded_job_ids": "test1,test2", "limit": 3}, "Get recommended jobs with excluded IDs (limit 3)"),
        
        # Count endpoints
        ("/total-available-count", {}, "Get total available jobs count"),
        ("/filtered-count", {"job_type": "fulltime"}, "Get filtered count (fulltime jobs)"),
        
        # Legacy endpoint
        ("/", {"limit": 3}, "Get jobs list (legacy endpoint)"),
    ]
    
    successful_tests = 0
    total_tests = len(tests)
    
    for endpoint, params, description in tests:
        if test_endpoint(endpoint, params, description):
            successful_tests += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print(f"   Total tests: {total_tests}")
    print(f"   Successful: {successful_tests}")
    print(f"   Failed: {total_tests - successful_tests}")
    
    success_rate = (successful_tests / total_tests) * 100
    print(f"   Success rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 Most tests passed! API is working well.")
        return True
    elif success_rate >= 50:
        print("⚠️ Some tests failed. Check the server logs.")
        return False
    else:
        print("❌ Many tests failed. There may be issues with the API.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 