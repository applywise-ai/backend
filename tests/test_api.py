#!/usr/bin/env python3
"""
Test script for ApplyWise Backend API with Firestore
"""

import requests
import json
import time
from typing import Dict, Any

API_BASE_URL = "http://localhost:8000"
TEST_USER_ID = "test_user_123"  # Test user ID


def test_health_check():
    """Test the health check endpoint"""
    print("🔍 Testing health check...")
    
    response = requests.get(f"{API_BASE_URL}/health")
    if response.status_code == 200:
        print("✅ Health check passed")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Health check failed: {response.status_code}")
    
    return response.status_code == 200


def test_apply_job():
    """Test job application submission"""
    print("\n📝 Testing job application...")
    
    # Sample job application data
    application_data = {
        "user_id": TEST_USER_ID,
        "job_url": "https://www.linkedin.com/jobs/view/3750000000",
        "resume_data": {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1-555-123-4567",
            "linkedin": "https://linkedin.com/in/johndoe",
            "website": "https://johndoe.dev"
        },
        "cover_letter_template": "Dear Hiring Manager,\n\nI am excited to apply for this position...",
        "application_answers": {
            "years_experience": "5",
            "willing_to_relocate": "Yes",
            "salary_expectation": "100000"
        }
    }
    
    response = requests.post(
        f"{API_BASE_URL}/apply",
        json=application_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Job application submitted successfully")
        print(f"Task ID: {result['task_id']}")
        print(f"Application ID: {result['application_id']}")
        print(f"Is existing application: {result['is_existing_application']}")
        return result['task_id'], result['application_id']
    else:
        print(f"❌ Job application failed: {response.status_code}")
        print(response.text)
        return None, None


def test_apply_job_duplicate():
    """Test applying to the same job again (should use existing application)"""
    print("\n🔄 Testing duplicate job application...")
    
    # Same job URL as before
    application_data = {
        "user_id": TEST_USER_ID,
        "job_url": "https://www.linkedin.com/jobs/view/3750000000",
        "resume_data": {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com"
        }
    }
    
    response = requests.post(
        f"{API_BASE_URL}/apply",
        json=application_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Duplicate job application handled successfully")
        print(f"Task ID: {result['task_id']}")
        print(f"Application ID: {result['application_id']}")
        print(f"Is existing application: {result['is_existing_application']}")
        
        if result['is_existing_application']:
            print("✅ Correctly identified as existing application")
        else:
            print("⚠️  Expected existing application but got new one")
        
        return result['task_id'], result['application_id']
    else:
        print(f"❌ Duplicate job application failed: {response.status_code}")
        print(response.text)
        return None, None


def test_task_status(task_id: str):
    """Test task status checking"""
    print(f"\n📊 Checking task status for {task_id}...")
    
    max_attempts = 30
    attempt = 0
    
    while attempt < max_attempts:
        response = requests.get(f"{API_BASE_URL}/status/{task_id}")
        
        if response.status_code == 200:
            result = response.json()
            status = result['status']
            
            print(f"Status: {status}")
            
            if status in ['completed', 'failed']:
                print("✅ Task completed")
                print(json.dumps(result, indent=2))
                return result
            elif status == 'processing':
                print("⏳ Task is processing...")
            else:
                print(f"📋 Task status: {status}")
        else:
            print(f"❌ Failed to get task status: {response.status_code}")
            return None
        
        attempt += 1
        time.sleep(2)
    
    print("⏰ Timeout waiting for task completion")
    return None


def test_get_user_applications():
    """Test getting list of applications for a user"""
    print(f"\n📋 Getting applications for user {TEST_USER_ID}...")
    
    response = requests.get(f"{API_BASE_URL}/users/{TEST_USER_ID}/applications")
    
    if response.status_code == 200:
        result = response.json()
        applications = result['applications']
        print(f"✅ Found {len(applications)} applications")
        print(f"Total count: {result['total_count']}")
        print(f"Has more: {result['has_more']}")
        
        for app in applications[:3]:  # Show first 3
            print(f"  - ID: {app['id']}, Status: {app['status']}, URL: {app['job_url']}")
        
        return applications
    else:
        print(f"❌ Failed to get user applications: {response.status_code}")
        return None


def test_get_specific_application(application_id: str):
    """Test getting a specific application"""
    print(f"\n📄 Getting specific application {application_id}...")
    
    response = requests.get(f"{API_BASE_URL}/users/{TEST_USER_ID}/applications/{application_id}")
    
    if response.status_code == 200:
        application = response.json()
        print("✅ Application retrieved successfully")
        print(f"  - Job ID: {application['job_id']}")
        print(f"  - Status: {application['status']}")
        print(f"  - Job URL: {application['job_url']}")
        return application
    else:
        print(f"❌ Failed to get application: {response.status_code}")
        return None


def test_get_application_logs(application_id: str):
    """Test getting application logs"""
    print(f"\n📝 Getting logs for application {application_id}...")
    
    response = requests.get(f"{API_BASE_URL}/users/{TEST_USER_ID}/applications/{application_id}/logs")
    
    if response.status_code == 200:
        result = response.json()
        logs = result['logs']
        print(f"✅ Found {len(logs)} log entries")
        
        for log in logs[-5:]:  # Show last 5 logs
            print(f"  - [{log.get('level', 'info')}] {log.get('message', '')}")
        
        return logs
    else:
        print(f"❌ Failed to get application logs: {response.status_code}")
        return None


def test_worker_status():
    """Test worker status endpoint"""
    print("\n👷 Checking worker status...")
    
    response = requests.get(f"{API_BASE_URL}/workers")
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Worker status retrieved")
        
        # Count active tasks
        active_tasks = result.get('active_tasks', {})
        total_active = sum(len(tasks) for tasks in active_tasks.values())
        print(f"Active tasks: {total_active}")
        
        # Show worker stats
        stats = result.get('stats', {})
        print(f"Workers: {len(stats)}")
        
        return result
    else:
        print(f"❌ Failed to get worker status: {response.status_code}")
        return None


def main():
    """Run all tests"""
    print("🧪 ApplyWise Backend API Test Suite (Firestore)")
    print("=" * 60)
    
    # Test health check
    if not test_health_check():
        print("❌ Health check failed. Make sure the API is running.")
        return
    
    # Test worker status
    test_worker_status()
    
    # Test getting user applications (should be empty initially)
    test_get_user_applications()
    
    # Test job application submission
    print("\n⚠️  Job application test is disabled to avoid spamming job sites.")
    print("To test job application, uncomment the following lines:")
    print("# task_id, app_id = test_apply_job()")
    print("# if task_id and app_id:")
    print("#     test_task_status(task_id)")
    print("#     test_get_specific_application(app_id)")
    print("#     test_get_application_logs(app_id)")
    print("#     test_apply_job_duplicate()  # Test duplicate handling")
    
    # Uncomment these lines to test actual job application
    # task_id, app_id = test_apply_job()
    # if task_id and app_id:
    #     test_task_status(task_id)
    #     test_get_specific_application(app_id)
    #     test_get_application_logs(app_id)
    #     
    #     # Test duplicate application
    #     duplicate_task_id, duplicate_app_id = test_apply_job_duplicate()
    #     if duplicate_task_id:
    #         test_task_status(duplicate_task_id)
    
    print("\n✅ Test suite completed!")
    print(f"\n📝 Note: All tests used user_id: {TEST_USER_ID}")
    print("In a real application, you would get the user_id from authentication.")


if __name__ == "__main__":
    main() 