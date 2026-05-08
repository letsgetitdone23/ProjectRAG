"""
Thread Pool for Concurrent RAG Service
Manages thread lifecycle and resource allocation for concurrent conversations
"""

import logging
import threading
import time
import uuid
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from queue import Queue, Empty
import asyncio
from pathlib import Path

from .session_manager import ThreadSession, ConversationContext

@dataclass
class ThreadMetrics:
    """Metrics for thread performance monitoring"""
    thread_id: str
    created_at: datetime
    last_activity: datetime
    total_queries_processed: int = 0
    average_response_time_ms: float = 0.0
    error_count: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    def update_response_time(self, response_time_ms: float):
        """Update average response time"""
        if self.total_queries_processed == 0:
            self.average_response_time_ms = response_time_ms
        else:
            # Exponential moving average
            alpha = 0.1
            self.average_response_time_ms = (
                alpha * response_time_ms + 
                (1 - alpha) * self.average_response_time_ms
            )
        self.total_queries_processed += 1
        self.last_activity = datetime.now()
    
    def increment_error(self):
        """Increment error count"""
        self.error_count += 1
    
    def get_health_score(self) -> float:
        """Calculate thread health score (0-100)"""
        # Factors: response time, error rate, age
        response_time_score = max(0, 100 - (self.average_response_time_ms / 10))  # 10s = 0 score
        error_rate_score = max(0, 100 - (self.error_count * 10))  # 10 errors = 0 score
        
        # Age factor (newer threads get slight bonus)
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        age_score = max(0, 100 - age_hours)  # 100 hours = 0 score
        
        return (response_time_score + error_rate_score + age_score) / 3

@dataclass
class ResourceLimits:
    """Resource limits for thread pool"""
    max_threads: int = 5
    max_concurrent_conversations: int = 10
    max_memory_per_thread_mb: int = 512
    max_cpu_per_thread_percent: float = 20.0
    thread_timeout_seconds: int = 300
    cleanup_interval_seconds: int = 60

class ThreadPoolManager:
    """Manages thread pool for concurrent RAG service with resource monitoring"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Resource limits
        self.limits = ResourceLimits(**config.get('resource_limits', {}))
        
        # Thread management
        self.active_threads: Dict[str, ThreadSession] = {}
        self.thread_metrics: Dict[str, ThreadMetrics] = {}
        self.thread_lock = threading.Lock()
        
        # Thread pool executor
        self.executor = ThreadPoolExecutor(
            max_workers=self.limits.max_threads,
            thread_name_prefix="RAG-Thread"
        )
        
        # Query queue for pending requests
        self.query_queue = Queue(maxsize=100)
        self.pending_futures: Dict[str, Future] = {}
        
        # Load balancer
        self.load_balancer = LoadBalancer(self)
        
        # Monitoring
        self.monitoring_enabled = config.get('monitoring_enabled', True)
        self.metrics_history: List[Dict] = []
        
        # Start background threads
        self._start_background_threads()
        
        self.logger.info(f"Thread Pool Manager initialized with max_threads={self.limits.max_threads}")
    
    def _start_background_threads(self):
        """Start background monitoring and cleanup threads"""
        # Query processor thread
        self.query_processor_thread = threading.Thread(
            target=self._process_query_queue,
            daemon=True
        )
        self.query_processor_thread.start()
        
        # Monitoring thread
        if self.monitoring_enabled:
            self.monitoring_thread = threading.Thread(
                target=self._monitor_resources,
                daemon=True
            )
            self.monitoring_thread.start()
        
        # Cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_resources,
            daemon=True
        )
        self.cleanup_thread.start()
    
    def submit_query(self, query: str, user_id: Optional[str] = None,
                    thread_id: Optional[str] = None, **kwargs) -> str:
        """Submit query to thread pool"""
        query_id = str(uuid.uuid4())
        
        query_data = {
            'query_id': query_id,
            'query': query,
            'user_id': user_id,
            'thread_id': thread_id,
            'submitted_at': datetime.now(),
            **kwargs
        }
        
        try:
            self.query_queue.put(query_data, timeout=1.0)
            self.logger.info(f"Query submitted: {query_id}")
            return query_id
        except:
            self.logger.error("Query queue is full")
            raise Exception("System is busy, please try again later")
    
    def get_query_result(self, query_id: str, timeout: float = 30.0) -> Dict:
        """Get result of submitted query"""
        if query_id not in self.pending_futures:
            raise ValueError(f"Query {query_id} not found")
        
        future = self.pending_futures[query_id]
        
        try:
            result = future.result(timeout=timeout)
            del self.pending_futures[query_id]
            return result
        except Exception as e:
            del self.pending_futures[query_id]
            self.logger.error(f"Query {query_id} failed: {str(e)}")
            raise
    
    def _process_query_queue(self):
        """Background thread to process queued queries"""
        while True:
            try:
                # Get query from queue
                query_data = self.query_queue.get(timeout=1.0)
                
                # Submit to thread pool
                future = self.executor.submit(self._execute_query, query_data)
                self.pending_futures[query_data['query_id']] = future
                
                self.logger.debug(f"Query {query_data['query_id']} submitted to thread pool")
                
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing query queue: {str(e)}")
    
    def _execute_query(self, query_data: Dict) -> Dict:
        """Execute query in thread pool"""
        start_time = time.time()
        query_id = query_data['query_id']
        
        try:
            # Get or create thread session
            thread_session = self.load_balancer.get_optimal_thread(
                user_id=query_data.get('user_id'),
                preferred_thread_id=query_data.get('thread_id')
            )
            
            if not thread_session:
                return {
                    'query_id': query_id,
                    'error': 'No available threads',
                    'message': 'System is busy, please try again later'
                }
            
            # Process query
            result = thread_session.rag_service.process_query(
                query_data['query'],
                previous_queries=[]  # Could be enhanced with context
            )
            
            # Update metrics
            response_time_ms = (time.time() - start_time) * 1000
            self._update_thread_metrics(thread_session.thread_id, response_time_ms, False)
            
            return {
                'query_id': query_id,
                'response': result.answer,
                'source_url': result.source_url,
                'confidence': result.confidence_score,
                'thread_id': thread_session.thread_id,
                'processing_time_ms': result.processing_time_ms,
                'total_time_ms': response_time_ms
            }
            
        except Exception as e:
            # Update error metrics
            response_time_ms = (time.time() - start_time) * 1000
            if 'thread_session' in locals():
                self._update_thread_metrics(thread_session.thread_id, response_time_ms, True)
            
            self.logger.error(f"Query {query_id} execution failed: {str(e)}")
            
            return {
                'query_id': query_id,
                'error': 'Processing failed',
                'message': 'I apologize, but I encountered an error processing your request.',
                'error_details': str(e)
            }
    
    def _update_thread_metrics(self, thread_id: str, response_time_ms: float, is_error: bool):
        """Update thread performance metrics"""
        with self.thread_lock:
            if thread_id not in self.thread_metrics:
                self.thread_metrics[thread_id] = ThreadMetrics(
                    thread_id=thread_id,
                    created_at=datetime.now(),
                    last_activity=datetime.now()
                )
            
            metrics = self.thread_metrics[thread_id]
            metrics.update_response_time(response_time_ms)
            
            if is_error:
                metrics.increment_error()
    
    def _monitor_resources(self):
        """Background thread to monitor thread resources"""
        while True:
            try:
                time.sleep(self.limits.cleanup_interval_seconds)
                
                with self.thread_lock:
                    for thread_id, metrics in self.thread_metrics.items():
                        # Update resource usage (simplified)
                        # In production, would use psutil or similar
                        metrics.memory_usage_mb = 100  # Placeholder
                        metrics.cpu_usage_percent = 5.0  # Placeholder
                
                # Collect system metrics
                self._collect_system_metrics()
                
            except Exception as e:
                self.logger.error(f"Error monitoring resources: {str(e)}")
    
    def _collect_system_metrics(self):
        """Collect system-wide metrics"""
        try:
            with self.thread_lock:
                total_threads = len(self.active_threads)
                total_queries = sum(m.total_queries_processed for m in self.thread_metrics.values())
                avg_response_time = sum(m.average_response_time_ms for m in self.thread_metrics.values()) / max(1, len(self.thread_metrics))
                total_errors = sum(m.error_count for m in self.thread_metrics.values())
                
                metrics = {
                    'timestamp': datetime.now().isoformat(),
                    'active_threads': total_threads,
                    'pending_queries': self.query_queue.qsize(),
                    'total_queries_processed': total_queries,
                    'average_response_time_ms': avg_response_time,
                    'total_errors': total_errors,
                    'thread_health_scores': {
                        thread_id: metrics.get_health_score()
                        for thread_id, metrics in self.thread_metrics.items()
                    }
                }
                
                self.metrics_history.append(metrics)
                
                # Keep only last 1000 entries
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {str(e)}")
    
    def _cleanup_resources(self):
        """Background thread to cleanup expired resources"""
        while True:
            try:
                time.sleep(self.limits.cleanup_interval_seconds)
                
                current_time = datetime.now()
                cleanup_threshold = current_time - timedelta(seconds=self.limits.thread_timeout_seconds)
                
                with self.thread_lock:
                    # Find expired threads
                    expired_threads = [
                        thread_id for thread_id, metrics in self.thread_metrics.items()
                        if metrics.last_activity < cleanup_threshold
                    ]
                    
                    for thread_id in expired_threads:
                        self._cleanup_thread(thread_id)
                
            except Exception as e:
                self.logger.error(f"Error during cleanup: {str(e)}")
    
    def _cleanup_thread(self, thread_id: str):
        """Cleanup expired thread"""
        try:
            # Remove thread session
            if thread_id in self.active_threads:
                del self.active_threads[thread_id]
            
            # Remove metrics
            if thread_id in self.thread_metrics:
                del self.thread_metrics[thread_id]
            
            self.logger.info(f"Cleaned up expired thread: {thread_id}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up thread {thread_id}: {str(e)}")
    
    def get_pool_status(self) -> Dict:
        """Get current thread pool status"""
        with self.thread_lock:
            return {
                'active_threads': len(self.active_threads),
                'max_threads': self.limits.max_threads,
                'pending_queries': self.query_queue.qsize(),
                'thread_metrics': {
                    thread_id: {
                        'total_queries': metrics.total_queries_processed,
                        'avg_response_time_ms': metrics.average_response_time_ms,
                        'error_count': metrics.error_count,
                        'health_score': metrics.get_health_score(),
                        'last_activity': metrics.last_activity.isoformat()
                    }
                    for thread_id, metrics in self.thread_metrics.items()
                },
                'system_metrics': self.metrics_history[-1] if self.metrics_history else None
            }
    
    def shutdown(self):
        """Gracefully shutdown thread pool"""
        self.logger.info("Shutting down Thread Pool Manager")
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Clear resources
        with self.thread_lock:
            self.active_threads.clear()
            self.thread_metrics.clear()
            self.pending_futures.clear()
        
        self.logger.info("Thread Pool Manager shutdown complete")

class LoadBalancer:
    """Load balancer for optimal thread selection"""
    
    def __init__(self, pool_manager: ThreadPoolManager):
        self.pool_manager = pool_manager
        self.logger = logging.getLogger(__name__)
    
    def get_optimal_thread(self, user_id: Optional[str] = None,
                          preferred_thread_id: Optional[str] = None) -> Optional[ThreadSession]:
        """Get optimal thread for query processing"""
        with self.pool_manager.thread_lock:
            # If preferred thread is available and has capacity
            if (preferred_thread_id and 
                preferred_thread_id in self.pool_manager.active_threads and
                self.pool_manager.active_threads[preferred_thread_id].can_accept_new_conversation()):
                return self.pool_manager.active_threads[preferred_thread_id]
            
            # Find thread with best health score and capacity
            available_threads = [
                (thread_id, thread_session)
                for thread_id, thread_session in self.pool_manager.active_threads.items()
                if thread_session.can_accept_new_conversation()
            ]
            
            if not available_threads:
                return None
            
            # Sort by health score
            available_threads.sort(
                key=lambda x: self.pool_manager.thread_metrics.get(x[0], ThreadMetrics(x[0], datetime.now(), datetime.now())).get_health_score(),
                reverse=True
            )
            
            return available_threads[0][1]
