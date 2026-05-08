#!/usr/bin/env python3
"""
Test Multi-thread RAG Service with Concurrent Queries
"""

import sys
import json
import logging
import asyncio
import time
import threading
import random
from typing import List, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

from api.api_gateway import create_api_gateway

def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

class MultiThreadRAGTester:
    """Tester for multi-thread RAG service"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.logger = logging.getLogger(__name__)
        self.test_results = []
    
    async def test_concurrent_queries(self, num_concurrent: int = 5, 
                                   queries_per_thread: int = 3) -> Dict:
        """Test concurrent queries"""
        self.logger.info(f"Testing {num_concurrent} concurrent threads with {queries_per_thread} queries each")
        
        # Sample queries
        sample_queries = [
            "What is NAV of Nippon India Large Cap Fund?",
            "What is the expense ratio of HDFC Mid-Cap Fund?",
            "Tell me about the performance of Axis Bluechip Fund",
            "What is the minimum investment amount for ICICI Prudential Fund?",
            "Explain the risk factors of mutual fund investments",
            "What are the tax benefits of ELSS funds?",
            "How to invest in SIP mutual funds?",
            "What is the difference between regular and direct plans?",
            "Which fund is best for long-term investment?",
            "What is the current NAV of SBI Bluechip Fund?"
        ]
        
        start_time = time.time()
        
        # Create thread pool for concurrent testing
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            # Submit tasks
            futures = []
            
            for thread_id in range(num_concurrent):
                future = executor.submit(
                    self._run_concurrent_thread,
                    thread_id,
                    sample_queries[:queries_per_thread],
                    f"user_{thread_id}"
                )
                futures.append(future)
            
            # Collect results
            thread_results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=30)
                    thread_results.append(result)
                except Exception as e:
                    self.logger.error(f"Thread execution failed: {str(e)}")
                    thread_results.append({'error': str(e)})
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_threads = sum(1 for r in thread_results if 'error' not in r)
        total_queries = sum(r.get('queries_completed', 0) for r in thread_results)
        avg_response_time = sum(r.get('avg_response_time', 0) for r in thread_results) / max(1, len(thread_results))
        
        results = {
            'test_type': 'concurrent_queries',
            'concurrent_threads': num_concurrent,
            'queries_per_thread': queries_per_thread,
            'total_queries': total_queries,
            'successful_threads': successful_threads,
            'total_time_seconds': total_time,
            'queries_per_second': total_queries / total_time if total_time > 0 else 0,
            'average_response_time_ms': avg_response_time,
            'thread_results': thread_results
        }
        
        self.logger.info(f"Concurrent test completed: {successful_threads}/{num_concurrent} threads successful")
        self.logger.info(f"Total queries: {total_queries}, QPS: {results['queries_per_second']:.2f}")
        
        return results
    
    def _run_concurrent_thread(self, thread_id: int, queries: List[str], user_id: str) -> Dict:
        """Run queries in a single thread"""
        thread_results = {
            'thread_id': thread_id,
            'user_id': user_id,
            'queries_completed': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'response_times': []
        }
        
        session_id = f"session_{thread_id}"
        
        for i, query in enumerate(queries):
            try:
                start_time = time.time()
                
                # Make API request
                response = requests.post(
                    f"{self.api_base_url}/api/chat",
                    json={
                        'message': query,
                        'user_id': user_id,
                        'session_id': session_id
                    },
                    timeout=10
                )
                
                response_time = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    result = response.json()
                    thread_results['successful_queries'] += 1
                    thread_results['response_times'].append(response_time)
                    
                    self.logger.debug(f"Thread {thread_id} - Query {i+1}: {response_time:.2f}ms")
                else:
                    thread_results['failed_queries'] += 1
                    self.logger.error(f"Thread {thread_id} - Query {i+1} failed: {response.status_code}")
                
                thread_results['queries_completed'] += 1
                
            except Exception as e:
                thread_results['failed_queries'] += 1
                self.logger.error(f"Thread {thread_id} - Query {i+1} exception: {str(e)}")
                thread_results['queries_completed'] += 1
        
        # Calculate average response time
        if thread_results['response_times']:
            thread_results['avg_response_time'] = sum(thread_results['response_times']) / len(thread_results['response_times'])
        else:
            thread_results['avg_response_time'] = 0
        
        return thread_results
    
    async def test_session_management(self, num_sessions: int = 10) -> Dict:
        """Test session management"""
        self.logger.info(f"Testing session management with {num_sessions} sessions")
        
        start_time = time.time()
        sessions_created = []
        
        try:
            # Create sessions
            for i in range(num_sessions):
                session_id = f"test_session_{i}"
                user_id = f"test_user_{i}"
                
                response = requests.post(
                    f"{self.api_base_url}/api/chat",
                    json={
                        'message': f"Test message for session {i}",
                        'user_id': user_id,
                        'session_id': session_id
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    sessions_created.append(session_id)
                    self.logger.debug(f"Created session {session_id}")
            
            # Get all sessions
            sessions_response = requests.get(f"{self.api_base_url}/api/sessions", timeout=10)
            
            # Cleanup sessions
            cleanup_count = 0
            for session_id in sessions_created:
                delete_response = requests.delete(f"{self.api_base_url}/api/sessions/{session_id}", timeout=10)
                if delete_response.status_code == 200:
                    cleanup_count += 1
            
            total_time = time.time() - start_time
            
            results = {
                'test_type': 'session_management',
                'sessions_requested': num_sessions,
                'sessions_created': len(sessions_created),
                'sessions_retrieved': len(sessions_response.json()) if sessions_response.status_code == 200 else 0,
                'sessions_cleaned': cleanup_count,
                'total_time_seconds': total_time,
                'sessions_per_second': num_sessions / total_time if total_time > 0 else 0
            }
            
            self.logger.info(f"Session management test completed: {len(sessions_created)}/{num_sessions} sessions created")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Session management test failed: {str(e)}")
            return {'error': str(e)}
    
    async def test_load_balancing(self, num_requests: int = 50) -> Dict:
        """Test load balancing across multiple threads"""
        self.logger.info(f"Testing load balancing with {num_requests} requests")
        
        sample_queries = [
            "What is NAV of Nippon India Large Cap Fund?",
            "What is the expense ratio of HDFC Mid-Cap Fund?",
            "Tell me about the performance of Axis Bluechip Fund"
        ]
        
        start_time = time.time()
        request_results = []
        
        # Submit all requests rapidly
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            
            for i in range(num_requests):
                query = random.choice(sample_queries)
                user_id = f"load_test_user_{i % 10}"  # 10 different users
                
                future = executor.submit(
                    self._make_single_request,
                    query,
                    user_id,
                    f"load_test_session_{i}"
                )
                futures.append(future)
            
            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=15)
                    request_results.append(result)
                except Exception as e:
                    self.logger.error(f"Load test request failed: {str(e)}")
                    request_results.append({'error': str(e)})
        
        total_time = time.time() - start_time
        
        # Analyze thread distribution
        thread_distribution = {}
        successful_requests = 0
        
        for result in request_results:
            if 'error' not in result:
                successful_requests += 1
                thread_id = result.get('thread_id', 'unknown')
                thread_distribution[thread_id] = thread_distribution.get(thread_id, 0) + 1
        
        results = {
            'test_type': 'load_balancing',
            'total_requests': num_requests,
            'successful_requests': successful_requests,
            'total_time_seconds': total_time,
            'requests_per_second': successful_requests / total_time if total_time > 0 else 0,
            'thread_distribution': thread_distribution,
            'threads_used': len(thread_distribution),
            'load_balance_score': self._calculate_load_balance_score(thread_distribution)
        }
        
        self.logger.info(f"Load balancing test completed: {successful_requests}/{num_requests} requests successful")
        self.logger.info(f"Threads used: {len(thread_distribution)}, Load balance score: {results['load_balance_score']:.2f}")
        
        return results
    
    def _make_single_request(self, query: str, user_id: str, session_id: str) -> Dict:
        """Make a single API request"""
        try:
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_base_url}/api/chat",
                json={
                    'message': query,
                    'user_id': user_id,
                    'session_id': session_id
                },
                timeout=10
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'response_time_ms': response_time,
                    'thread_id': result.get('thread_id'),
                    'confidence': result.get('confidence'),
                    'session_id': result.get('session_id')
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'response_time_ms': response_time
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response_time_ms': 0
            }
    
    def _calculate_load_balance_score(self, thread_distribution: Dict) -> float:
        """Calculate load balance score (0-1, 1 = perfectly balanced)"""
        if not thread_distribution:
            return 0.0
        
        total_requests = sum(thread_distribution.values())
        if total_requests == 0:
            return 0.0
        
        # Calculate variance from ideal distribution
        num_threads = len(thread_distribution)
        ideal_per_thread = total_requests / num_threads
        
        variance = sum((count - ideal_per_thread) ** 2 for count in thread_distribution.values())
        max_variance = (total_requests ** 2) if num_threads == 1 else (total_requests ** 2) / num_threads
        
        # Convert to score (lower variance = higher score)
        if max_variance == 0:
            return 1.0
        
        score = 1.0 - (variance / max_variance)
        return max(0.0, min(1.0, score))
    
    async def test_health_check(self) -> Dict:
        """Test health check endpoint"""
        try:
            response = requests.get(f"{self.api_base_url}/api/health", timeout=5)
            
            if response.status_code == 200:
                health_data = response.json()
                return {
                    'test_type': 'health_check',
                    'success': True,
                    'status': health_data.get('status'),
                    'active_threads': health_data.get('active_threads'),
                    'pending_queries': health_data.get('pending_queries'),
                    'total_sessions': health_data.get('total_sessions')
                }
            else:
                return {
                    'test_type': 'health_check',
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                'test_type': 'health_check',
                'success': False,
                'error': str(e)
            }
    
    async def run_all_tests(self) -> Dict:
        """Run all tests"""
        self.logger.info("Starting comprehensive multi-thread RAG tests")
        
        all_results = {
            'test_suite': 'multi_thread_rag',
            'timestamp': time.time(),
            'tests': []
        }
        
        # Test 1: Health check
        self.logger.info("Test 1: Health check")
        health_result = await self.test_health_check()
        all_results['tests'].append(health_result)
        
        # Test 2: Concurrent queries
        self.logger.info("Test 2: Concurrent queries")
        concurrent_result = await self.test_concurrent_queries(num_concurrent=5, queries_per_thread=3)
        all_results['tests'].append(concurrent_result)
        
        # Test 3: Session management
        self.logger.info("Test 3: Session management")
        session_result = await self.test_session_management(num_sessions=10)
        all_results['tests'].append(session_result)
        
        # Test 4: Load balancing
        self.logger.info("Test 4: Load balancing")
        load_balance_result = await self.test_load_balancing(num_requests=30)
        all_results['tests'].append(load_balance_result)
        
        # Summary
        successful_tests = sum(1 for test in all_results['tests'] if test.get('success', True))
        all_results['summary'] = {
            'total_tests': len(all_results['tests']),
            'successful_tests': successful_tests,
            'success_rate': successful_tests / len(all_results['tests'])
        }
        
        self.logger.info(f"Test suite completed: {successful_tests}/{len(all_results['tests'])} tests successful")
        
        return all_results

async def main():
    """Main test function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Configuration
    config = {
        'api': {
            'host': '0.0.0.0',
            'port': 8000,
            'debug': False
        },
        'session_management': {
            'max_threads': 5,
            'session_timeout_hours': 1,
            'persist_sessions': False  # Disable for testing
        },
        'thread_pool': {
            'max_threads': 5,
            'monitoring_enabled': True
        },
        'context_manager': {
            'max_contexts_per_thread': 10,
            'default_window_size': 5
        },
        'persistence': {
            'storage_type': 'memory'
        },
        'load_balancing': {
            'algorithm': 'weighted_round_robin',
            'health_check_interval': 10
        }
    }
    
    # Start API Gateway in background
    logger.info("Starting API Gateway for testing...")
    
    def run_api_gateway():
        api_gateway = create_api_gateway(config)
        api_gateway.run()
    
    # Run API in separate thread
    api_thread = threading.Thread(target=run_api_gateway, daemon=True)
    api_thread.start()
    
    # Wait for API to start
    logger.info("Waiting for API Gateway to start...")
    time.sleep(5)
    
    # Run tests
    tester = MultiThreadRAGTester()
    results = await tester.run_all_tests()
    
    # Print results
    print("\n" + "="*50)
    print("MULTI-THREAD RAG TEST RESULTS")
    print("="*50)
    
    for test in results['tests']:
        print(f"\n{test.get('test_type', 'Unknown Test').upper()}:")
        print(f"  Success: {test.get('success', 'N/A')}")
        
        if test.get('test_type') == 'concurrent_queries':
            print(f"  Threads: {test.get('concurrent_threads')}")
            print(f"  Queries: {test.get('total_queries')}")
            print(f"  QPS: {test.get('queries_per_second', 0):.2f}")
            print(f"  Avg Response Time: {test.get('average_response_time_ms', 0):.2f}ms")
        
        elif test.get('test_type') == 'session_management':
            print(f"  Sessions Created: {test.get('sessions_created')}")
            print(f"  Sessions Cleaned: {test.get('sessions_cleaned')}")
            print(f"  Sessions/sec: {test.get('sessions_per_second', 0):.2f}")
        
        elif test.get('test_type') == 'load_balancing':
            print(f"  Requests: {test.get('total_requests')}")
            print(f"  Successful: {test.get('successful_requests')}")
            print(f"  QPS: {test.get('requests_per_second', 0):.2f}")
            print(f"  Threads Used: {test.get('threads_used')}")
            print(f"  Load Balance Score: {test.get('load_balance_score', 0):.2f}")
        
        elif test.get('test_type') == 'health_check':
            print(f"  Status: {test.get('status')}")
            print(f"  Active Threads: {test.get('active_threads')}")
            print(f"  Pending Queries: {test.get('pending_queries')}")
    
    print(f"\nSUMMARY:")
    print(f"  Total Tests: {results['summary']['total_tests']}")
    print(f"  Successful: {results['summary']['successful_tests']}")
    print(f"  Success Rate: {results['summary']['success_rate']:.2%}")
    
    # Save results to file
    results_file = Path("test_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {results_file}")

if __name__ == "__main__":
    asyncio.run(main())
