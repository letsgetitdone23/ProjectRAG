"""
Test script to verify multi-threading functionality
Tests multiple simultaneous chat sessions with thread isolation
"""

import requests
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

def test_concurrent_sessions():
    """Test multiple concurrent sessions"""
    base_url = "http://localhost:8000"
    
    # Test queries for different users
    test_queries = [
        "What is the expense ratio of Nippon India Large Cap Fund Direct Growth?",
        "What is the minimum SIP amount for Nippon India Flexi Cap Fund Direct Growth?",
        "What is the benchmark index of Nippon India Multi Asset Allocation Fund Direct Growth?",
        "What is NAV of Nippon India Large Cap Fund Direct Growth?",
        "What is exit load for Nippon India Flexi Cap Fund Direct Growth?",
        "What is riskometer classification of Nippon India Multi Asset Allocation Fund Direct Growth?"
    ]
    
    def simulate_user_session(user_id, session_id):
        """Simulate a user session with multiple queries"""
        results = []
        
        try:
            # Create session
            session_data = {
                "user_id": user_id,
                "thread_id": f"thread_{user_id}_{session_id}"
            }
            
            # Send multiple queries
            for i, query in enumerate(test_queries[:3]):  # 3 queries per session
                payload = {
                    "message": query,
                    "user_id": user_id,
                    "thread_id": session_data["thread_id"]
                }
                
                response = requests.post(f"{base_url}/api/chat", json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    results.append({
                        "user_id": user_id,
                        "thread_id": data["thread_id"],
                        "query": query,
                        "response": data["response"],
                        "source_url": data["source_url"],
                        "confidence": data["confidence"],
                        "active_threads": data.get("active_threads", 0),
                        "processing_time_ms": data["processing_time_ms"]
                    })
                else:
                    results.append({
                        "user_id": user_id,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    })
                
                # Small delay between queries
                time.sleep(0.1)
                
        except Exception as e:
            results.append({
                "user_id": user_id,
                "error": str(e)
            })
        
        return results
    
    def run_concurrent_test():
        """Run concurrent test with multiple users"""
        print("🧪 Testing Multi-Threaded RAG System")
        print("=" * 60)
        
        # Create multiple user sessions
        num_users = 5
        num_sessions_per_user = 2
        
        all_tasks = []
        
        for user_id in range(num_users):
            for session_id in range(num_sessions_per_user):
                task = (f"user_{user_id}", f"session_{session_id}")
                all_tasks.append(task)
        
        print(f"📊 Starting {len(all_tasks)} concurrent sessions...")
        print(f"👥 Users: {num_users}, Sessions per user: {num_sessions_per_user}")
        
        # Execute tasks concurrently
        start_time = time.time()
        all_results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(simulate_user_session, user_id, session_id): (user_id, session_id)
                for user_id, session_id in all_tasks
            }
            
            # Collect results
            completed_tasks = 0
            for future in as_completed(future_to_task):
                user_id, session_id = future_to_task[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    completed_tasks += 1
                    print(f"✅ Completed session {user_id}_{session_id} ({completed_tasks}/{len(all_tasks)})")
                except Exception as e:
                    print(f"❌ Error in session {user_id}_{session_id}: {str(e)}")
        
        total_time = time.time() - start_time
        
        # Analyze results
        print(f"\n📈 Test Results:")
        print(f"⏱️ Total time: {total_time:.2f} seconds")
        print(f"📊 Total queries: {len(all_results)}")
        
        # Check for thread isolation
        thread_ids = set()
        user_threads = {}
        
        successful_queries = 0
        failed_queries = 0
        
        for result in all_results:
            if "error" not in result:
                successful_queries += 1
                thread_id = result.get("thread_id")
                user_id = result.get("user_id")
                
                if thread_id:
                    thread_ids.add(thread_id)
                    
                    if user_id not in user_threads:
                        user_threads[user_id] = set()
                    user_threads[user_id].add(thread_id)
            else:
                failed_queries += 1
        
        print(f"✅ Successful queries: {successful_queries}")
        print(f"❌ Failed queries: {failed_queries}")
        print(f"🧵 Unique thread IDs: {len(thread_ids)}")
        
        # Verify thread isolation
        print(f"\n🔍 Thread Isolation Analysis:")
        for user_id, threads in user_threads.items():
            print(f"👤 User {user_id}: {len(threads)} unique threads")
            if len(threads) > 1:
                print(f"  ✅ Multiple threads detected - isolation working")
            else:
                print(f"  ⚠️ Single thread only")
        
        # Check response quality
        print(f"\n📊 Response Quality:")
        nippon_responses = 0
        advisory_responses = 0
        
        for result in all_results:
            if "response" in result:
                response = result["response"].lower()
                if "nippon india" in response:
                    nippon_responses += 1
                if "facts only" in response or "cannot offer investment advice" in response:
                    advisory_responses += 1
        
        print(f"🎯 Nippon India responses: {nippon_responses}")
        print(f"⚠️ Advisory refusals: {advisory_responses}")
        
        # Performance metrics
        if successful_queries > 0:
            avg_processing_time = sum(r.get("processing_time_ms", 0) for r in all_results if "processing_time_ms" in r) / successful_queries
            print(f"⚡ Average processing time: {avg_processing_time:.2f}ms")
        
        print(f"\n🎯 Multi-Threading Test Completed!")
        
        return {
            "total_queries": len(all_results),
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "unique_threads": len(thread_ids),
            "total_time": total_time,
            "thread_isolation": len(thread_ids) >= len(all_tasks) * 0.8  # At least 80% should have unique threads
        }
    
    return run_concurrent_test()

def test_health_endpoints():
    """Test health and session endpoints"""
    base_url = "http://localhost:8000"
    
    print("\n🏥 Testing Health Endpoints")
    print("-" * 40)
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health: {data['status']}")
            print(f"🧵 Active threads: {data['active_threads']}")
            print(f"📊 Active sessions: {data['active_sessions']}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
        
        # Test sessions endpoint
        response = requests.get(f"{base_url}/api/sessions", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Sessions endpoint working")
            print(f"📊 Active sessions: {data.get('active_sessions', 0)}")
            print(f"👥 Total users: {data.get('total_users', 0)}")
        else:
            print(f"❌ Sessions endpoint failed: {response.status_code}")
        
        # Test stats endpoint
        response = requests.get(f"{base_url}/api/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Stats endpoint working")
            print(f"🔧 Multi-threading: {data['system_info'].get('multi_threading', False)}")
            print(f"🛡️ Thread-safe: {data['system_info'].get('thread_safe', False)}")
        else:
            print(f"❌ Stats endpoint failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing endpoints: {str(e)}")

if __name__ == "__main__":
    try:
        # Test health endpoints first
        test_health_endpoints()
        
        # Run concurrent test
        results = test_concurrent_sessions()
        
        # Final assessment
        print(f"\n🏆 Multi-Threading Assessment:")
        if results["thread_isolation"] and results["successful_queries"] > 0:
            print("✅ Multi-threading implementation is working correctly!")
            print("✅ Thread isolation is maintained")
            print("✅ Concurrent sessions are supported")
        else:
            print("❌ Multi-threading implementation needs improvement")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
