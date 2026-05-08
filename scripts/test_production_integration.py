#!/usr/bin/env python3
"""
Production Integration Test Script
Tests end-to-end functionality after deployment
"""

import requests
import json
import time
from datetime import datetime

def test_backend_health():
    """Test backend health endpoint"""
    print("🏥 Testing Backend Health...")
    
    try:
        response = requests.get('https://nippon-india-rag-api.onrender.com/api/health', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Backend Health: {data.get('status', 'unknown')}")
            print(f"📊 Active Threads: {data.get('active_threads', 0)}")
            print(f"📅 Uptime: {data.get('uptime', 'unknown')}")
            return True
        else:
            print(f"❌ Backend Health Check Failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend Health Check Error: {e}")
        return False

def test_frontend_health():
    """Test frontend health endpoint"""
    print("\n🎨 Testing Frontend Health...")
    
    try:
        response = requests.get('https://nippon-india-faq.vercel.app/api/health', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Frontend Health: {data.get('status', 'unknown')}")
            print(f"🌐 Frontend Version: {data.get('frontend', 'unknown')}")
            print(f"🔗 Backend Connection: {data.get('backend_connection', 'unknown')}")
            return True
        else:
            print(f"❌ Frontend Health Check Failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend Health Check Error: {e}")
        return False

def test_api_integration():
    """Test API integration between frontend and backend"""
    print("\n🔗 Testing API Integration...")
    
    test_queries = [
        "What is NAV of Nippon India Large Cap Fund Direct Growth?",
        "What is expense ratio of Nippon India Flexi Cap Fund?",
        "What is minimum SIP for Nippon India Multi Asset Allocation Fund?",
        "What is fund size of Nippon India Large Cap Fund?"
    ]
    
    api_url = "https://nippon-india-rag-api.onrender.com/api/chat"
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Test Query {i}: {query}")
        
        try:
            response = requests.post(
                api_url,
                json={'message': query, 'thread_id': f'test{i}'},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Response: {data.get('response', 'No response')[:100]}...")
                print(f"📊 Confidence: {data.get('confidence', 0)}")
                print(f"📅 Last Updated: {data.get('last_updated', 'unknown')}")
                print(f"⏱️ Processing Time: {data.get('processing_time_ms', 0)}ms")
            else:
                print(f"❌ API Test Failed: HTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ API Test Error: {e}")
            
        time.sleep(1)  # Rate limiting

def test_scheduler_status():
    """Test if scheduler is running properly"""
    print("\n📅 Testing Scheduler Status...")
    
    try:
        # Check if recent logs exist (would be uploaded as artifacts)
        response = requests.get(
            'https://api.github.com/repos/[REPO]/actions/artifacts',
            headers={'Authorization': 'token [GITHUB_TOKEN]'},
            timeout=10
        )
        
        if response.status_code == 200:
            artifacts = response.json().get('artifacts', [])
            recent_artifacts = [a for a in artifacts if 'scheduler' in a.get('name', '').lower()]
            
            if recent_artifacts:
                latest = recent_artifacts[0]
                print(f"✅ Latest Scheduler Artifact: {latest.get('created_at', 'unknown')}")
                return True
            else:
                print("⚠️  No recent scheduler artifacts found")
                return False
        else:
            print(f"❌ Scheduler Status Check Failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Scheduler Status Check Error: {e}")
        return False

def main():
    """Run all production integration tests"""
    print("🚀 Starting Production Integration Tests")
    print("=" * 80)
    
    start_time = datetime.now()
    
    # Run all tests
    tests = [
        ("Backend Health", test_backend_health),
        ("Frontend Health", test_frontend_health),
        ("API Integration", test_api_integration),
        ("Scheduler Status", test_scheduler_status)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} Test Exception: {e}")
            results[test_name] = False
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "=" * 80)
    print("📊 INTEGRATION TEST SUMMARY")
    print("=" * 80)
    print(f"⏱️  Total Duration: {duration:.2f} seconds")
    print(f"📅 Test Timestamp: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    passed_tests = sum(1 for result in results.values() if result)
    total_tests = len(results)
    
    print(f"✅ Tests Passed: {passed_tests}/{total_tests}")
    print(f"❌ Tests Failed: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        return 0
    else:
        print("⚠️  SOME INTEGRATION TESTS FAILED!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
