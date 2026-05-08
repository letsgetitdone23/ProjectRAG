"""
Load Balancer for Resource Allocation
Manages optimal thread selection and resource distribution
"""

import logging
import threading
import time
import heapq
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import random

from .thread_pool import ThreadMetrics, ThreadPoolManager
from .session_manager import ThreadSession

@dataclass
class ResourceMetrics:
    """Metrics for resource monitoring"""
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    disk_io_mb_per_sec: float = 0.0
    network_io_mb_per_sec: float = 0.0
    active_connections: int = 0
    queue_length: int = 0
    response_time_ms: float = 0.0
    
    def get_load_score(self) -> float:
        """Calculate overall load score (0-100, higher = more loaded)"""
        # Weight different factors
        cpu_weight = 0.3
        memory_weight = 0.2
        queue_weight = 0.3
        response_weight = 0.2
        
        cpu_score = min(100, self.cpu_usage_percent * 2)  # Scale CPU impact
        memory_score = min(100, (self.memory_usage_mb / 1024) * 100)  # 1GB = 100%
        queue_score = min(100, self.queue_length * 10)  # 10 queries = 100%
        response_score = min(100, self.response_time_ms / 10)  # 10s = 100%
        
        return (
            cpu_score * cpu_weight +
            memory_score * memory_weight +
            queue_score * queue_weight +
            response_score * response_weight
        )

@dataclass
class LoadBalancingStrategy:
    """Configuration for load balancing strategy"""
    algorithm: str = "weighted_round_robin"  # round_robin, weighted_round_robin, least_connections, least_response_time, random
    health_check_interval: int = 30  # seconds
    max_failures: int = 3
    recovery_timeout: int = 60  # seconds
    weight_decay_factor: float = 0.95  # for weighted algorithms
    
class LoadBalancer:
    """Advanced load balancer for optimal thread selection"""
    
    def __init__(self, thread_pool_manager: ThreadPoolManager, config: Dict):
        self.thread_pool_manager = thread_pool_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Load balancing strategy
        self.strategy = LoadBalancingStrategy(**config.get('load_balancing', {}))
        
        # Thread tracking
        self.thread_metrics: Dict[str, ThreadMetrics] = {}
        self.thread_resources: Dict[str, ResourceMetrics] = {}
        self.thread_health: Dict[str, bool] = {}
        self.thread_failures: Dict[str, int] = defaultdict(int)
        self.thread_weights: Dict[str, float] = {}
        
        # Load balancing state
        self.round_robin_index = 0
        self.weighted_heap: List[Tuple[float, str]] = []  # (weight, thread_id)
        self.heap_lock = threading.Lock()
        
        # Monitoring
        self.monitoring_enabled = config.get('monitoring_enabled', True)
        self.load_history: deque = deque(maxlen=1000)
        
        # Health checking
        self.health_check_enabled = config.get('health_check_enabled', True)
        
        # Start background threads
        self._start_background_threads()
        
        self.logger.info(f"Load Balancer initialized with {self.strategy.algorithm} algorithm")
    
    def _start_background_threads(self):
        """Start background monitoring and health check threads"""
        if self.monitoring_enabled:
            self.monitoring_thread = threading.Thread(
                target=self._monitor_resources,
                daemon=True
            )
            self.monitoring_thread.start()
        
        if self.health_check_enabled:
            self.health_check_thread = threading.Thread(
                target=self._health_check_worker,
                daemon=True
            )
            self.health_check_thread.start()
    
    def select_optimal_thread(self, user_id: Optional[str] = None,
                            preferred_thread_id: Optional[str] = None,
                            query_complexity: str = "medium") -> Optional[str]:
        """Select optimal thread based on load balancing strategy"""
        try:
            # Get available threads
            available_threads = self._get_available_threads()
            
            if not available_threads:
                self.logger.warning("No available threads for load balancing")
                return None
            
            # Apply load balancing algorithm
            if self.strategy.algorithm == "round_robin":
                selected_thread = self._round_robin_selection(available_threads)
            elif self.strategy.algorithm == "weighted_round_robin":
                selected_thread = self._weighted_round_robin_selection(available_threads)
            elif self.strategy.algorithm == "least_connections":
                selected_thread = self._least_connections_selection(available_threads)
            elif self.strategy.algorithm == "least_response_time":
                selected_thread = self._least_response_time_selection(available_threads)
            elif self.strategy.algorithm == "random":
                selected_thread = self._random_selection(available_threads)
            else:
                # Default to weighted round robin
                selected_thread = self._weighted_round_robin_selection(available_threads)
            
            # Log selection
            if selected_thread:
                self.logger.debug(f"Selected thread {selected_thread} using {self.strategy.algorithm}")
            
            return selected_thread
            
        except Exception as e:
            self.logger.error(f"Error in thread selection: {str(e)}")
            return None
    
    def _get_available_threads(self) -> List[str]:
        """Get list of healthy, available threads"""
        with self.thread_pool_manager.thread_lock:
            available = []
            
            for thread_id, thread_session in self.thread_pool_manager.active_threads.items():
                # Check if thread is healthy
                if not self.thread_health.get(thread_id, True):
                    continue
                
                # Check if thread can accept new conversation
                if not thread_session.can_accept_new_conversation():
                    continue
                
                # Check failure count
                if self.thread_failures[thread_id] >= self.strategy.max_failures:
                    continue
                
                available.append(thread_id)
            
            return available
    
    def _round_robin_selection(self, available_threads: List[str]) -> Optional[str]:
        """Round-robin thread selection"""
        if not available_threads:
            return None
        
        selected_thread = available_threads[self.round_robin_index % len(available_threads)]
        self.round_robin_index += 1
        
        return selected_thread
    
    def _weighted_round_robin_selection(self, available_threads: List[str]) -> Optional[str]:
        """Weighted round-robin thread selection"""
        if not available_threads:
            return None
        
        # Calculate weights based on thread performance
        weights = []
        for thread_id in available_threads:
            weight = self._calculate_thread_weight(thread_id)
            weights.append(weight)
            self.thread_weights[thread_id] = weight
        
        # Select thread based on weights
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(available_threads)
        
        # Weighted selection
        rand_value = random.random() * total_weight
        current_weight = 0
        
        for i, weight in enumerate(weights):
            current_weight += weight
            if rand_value <= current_weight:
                return available_threads[i]
        
        return available_threads[-1]
    
    def _least_connections_selection(self, available_threads: List[str]) -> Optional[str]:
        """Select thread with least active connections"""
        if not available_threads:
            return None
        
        min_connections = float('inf')
        selected_thread = None
        
        for thread_id in available_threads:
            connections = len(self.thread_pool_manager.active_threads[thread_id].active_conversations)
            
            if connections < min_connections:
                min_connections = connections
                selected_thread = thread_id
        
        return selected_thread
    
    def _least_response_time_selection(self, available_threads: List[str]) -> Optional[str]:
        """Select thread with best response time"""
        if not available_threads:
            return None
        
        best_response_time = float('inf')
        selected_thread = None
        
        for thread_id in available_threads:
            metrics = self.thread_metrics.get(thread_id)
            if metrics and metrics.average_response_time_ms < best_response_time:
                best_response_time = metrics.average_response_time_ms
                selected_thread = thread_id
        
        return selected_thread or available_threads[0]
    
    def _random_selection(self, available_threads: List[str]) -> Optional[str]:
        """Random thread selection"""
        if not available_threads:
            return None
        
        return random.choice(available_threads)
    
    def _calculate_thread_weight(self, thread_id: str) -> float:
        """Calculate weight for thread based on performance metrics"""
        try:
            metrics = self.thread_metrics.get(thread_id)
            resources = self.thread_resources.get(thread_id)
            
            if not metrics:
                return 1.0  # Default weight
            
            # Base weight from health score
            health_score = metrics.get_health_score()
            
            # Adjust for resource usage
            if resources:
                load_score = resources.get_load_score()
                # Higher load = lower weight
                load_factor = max(0.1, 1.0 - (load_score / 100))
            else:
                load_factor = 1.0
            
            # Adjust for error rate
            if metrics.total_queries_processed > 0:
                error_rate = metrics.error_count / metrics.total_queries_processed
                error_factor = max(0.1, 1.0 - (error_rate * 10))  # 10% error = 0 weight
            else:
                error_factor = 1.0
            
            # Calculate final weight
            weight = health_score * load_factor * error_factor
            
            # Apply weight decay
            weight *= self.strategy.weight_decay_factor
            
            return max(0.1, weight)  # Minimum weight
            
        except Exception as e:
            self.logger.error(f"Error calculating weight for thread {thread_id}: {str(e)}")
            return 1.0
    
    def update_thread_metrics(self, thread_id: str, metrics: ThreadMetrics):
        """Update thread performance metrics"""
        self.thread_metrics[thread_id] = metrics
        
        # Update load history
        load_entry = {
            'timestamp': datetime.now(),
            'thread_id': thread_id,
            'response_time_ms': metrics.average_response_time_ms,
            'error_count': metrics.error_count,
            'total_queries': metrics.total_queries_processed
        }
        self.load_history.append(load_entry)
    
    def update_thread_resources(self, thread_id: str, resources: ResourceMetrics):
        """Update thread resource metrics"""
        self.thread_resources[thread_id] = resources
    
    def record_thread_failure(self, thread_id: str):
        """Record thread failure"""
        self.thread_failures[thread_id] += 1
        
        # Mark as unhealthy if too many failures
        if self.thread_failures[thread_id] >= self.strategy.max_failures:
            self.thread_health[thread_id] = False
            self.logger.warning(f"Thread {thread_id} marked as unhealthy due to failures")
    
    def record_thread_success(self, thread_id: str):
        """Record thread success (for recovery)"""
        if self.thread_failures[thread_id] > 0:
            self.thread_failures[thread_id] = max(0, self.thread_failures[thread_id] - 1)
            
            # Mark as healthy if failures are reduced
            if self.thread_failures[thread_id] < self.strategy.max_failures:
                self.thread_health[thread_id] = True
                self.logger.info(f"Thread {thread_id} recovered and marked as healthy")
    
    def _monitor_resources(self):
        """Background thread to monitor thread resources"""
        while True:
            try:
                time.sleep(10)  # Monitor every 10 seconds
                
                with self.thread_pool_manager.thread_lock:
                    for thread_id in self.thread_pool_manager.active_threads.keys():
                        # Simulate resource monitoring (in production, use psutil or similar)
                        resources = ResourceMetrics(
                            cpu_usage_percent=random.uniform(5, 30),  # Simulated
                            memory_usage_mb=random.uniform(50, 200),  # Simulated
                            active_connections=len(self.thread_pool_manager.active_threads[thread_id].active_conversations),
                            queue_length=self.thread_pool_manager.query_queue.qsize(),
                            response_time_ms=self.thread_metrics.get(thread_id, ThreadMetrics(thread_id, datetime.now(), datetime.now())).average_response_time_ms
                        )
                        
                        self.update_thread_resources(thread_id, resources)
                
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {str(e)}")
    
    def _health_check_worker(self):
        """Background thread for health checking"""
        while True:
            try:
                time.sleep(self.strategy.health_check_interval)
                
                with self.thread_pool_manager.thread_lock:
                    for thread_id, thread_session in self.thread_pool_manager.active_threads.items():
                        # Simple health check: try to get thread stats
                        try:
                            # In production, would do actual health check
                            # For now, just check if thread is responsive
                            if thread_session.last_activity:
                                time_since_activity = datetime.now() - thread_session.last_activity
                                
                                # Mark as unhealthy if no activity for too long
                                if time_since_activity > timedelta(minutes=5):
                                    if self.thread_health.get(thread_id, True):
                                        self.thread_health[thread_id] = False
                                        self.logger.warning(f"Thread {thread_id} marked as unhealthy (no activity)")
                                else:
                                    if not self.thread_health.get(thread_id, True):
                                        self.thread_health[thread_id] = True
                                        self.logger.info(f"Thread {thread_id} recovered and marked as healthy")
                        
                        except Exception as e:
                            self.record_thread_failure(thread_id)
                            self.logger.error(f"Health check failed for thread {thread_id}: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Error in health check worker: {str(e)}")
    
    def get_load_balancing_stats(self) -> Dict:
        """Get load balancing statistics"""
        with self.thread_pool_manager.thread_lock:
            total_threads = len(self.thread_pool_manager.active_threads)
            healthy_threads = sum(1 for healthy in self.thread_health.values() if healthy)
            
            # Calculate average metrics
            avg_response_time = 0
            avg_cpu_usage = 0
            avg_memory_usage = 0
            
            if self.thread_metrics:
                avg_response_time = sum(m.average_response_time_ms for m in self.thread_metrics.values()) / len(self.thread_metrics)
            
            if self.thread_resources:
                avg_cpu_usage = sum(r.cpu_usage_percent for r in self.thread_resources.values()) / len(self.thread_resources)
                avg_memory_usage = sum(r.memory_usage_mb for r in self.thread_resources.values()) / len(self.thread_resources)
            
            return {
                'algorithm': self.strategy.algorithm,
                'total_threads': total_threads,
                'healthy_threads': healthy_threads,
                'unhealthy_threads': total_threads - healthy_threads,
                'average_response_time_ms': avg_response_time,
                'average_cpu_usage_percent': avg_cpu_usage,
                'average_memory_usage_mb': avg_memory_usage,
                'thread_weights': self.thread_weights.copy(),
                'thread_failures': dict(self.thread_failures),
                'load_history_size': len(self.load_history)
            }
    
    def get_thread_details(self) -> Dict:
        """Get detailed information about all threads"""
        with self.thread_pool_manager.thread_lock:
            thread_details = {}
            
            for thread_id, thread_session in self.thread_pool_manager.active_threads.items():
                metrics = self.thread_metrics.get(thread_id)
                resources = self.thread_resources.get(thread_id)
                
                details = {
                    'thread_id': thread_id,
                    'healthy': self.thread_health.get(thread_id, True),
                    'failures': self.thread_failures[thread_id],
                    'active_conversations': len(thread_session.active_conversations),
                    'can_accept_new': thread_session.can_accept_new_conversation(),
                    'created_at': thread_session.created_at.isoformat(),
                    'last_activity': thread_session.last_activity.isoformat()
                }
                
                if metrics:
                    details.update({
                        'total_queries': metrics.total_queries_processed,
                        'average_response_time_ms': metrics.average_response_time_ms,
                        'error_count': metrics.error_count,
                        'health_score': metrics.get_health_score()
                    })
                
                if resources:
                    details.update({
                        'cpu_usage_percent': resources.cpu_usage_percent,
                        'memory_usage_mb': resources.memory_usage_mb,
                        'active_connections': resources.active_connections,
                        'queue_length': resources.queue_length,
                        'load_score': resources.get_load_score()
                    })
                
                thread_details[thread_id] = details
            
            return thread_details
    
    def rebalance_threads(self) -> int:
        """Rebalance threads by adjusting weights"""
        try:
            rebalanced_count = 0
            
            # Recalculate all thread weights
            with self.thread_pool_manager.thread_lock:
                for thread_id in self.thread_pool_manager.active_threads.keys():
                    old_weight = self.thread_weights.get(thread_id, 1.0)
                    new_weight = self._calculate_thread_weight(thread_id)
                    
                    if abs(old_weight - new_weight) > 0.1:  # Significant change
                        self.thread_weights[thread_id] = new_weight
                        rebalanced_count += 1
            
            self.logger.info(f"Rebalanced {rebalanced_count} threads")
            return rebalanced_count
            
        except Exception as e:
            self.logger.error(f"Error during rebalancing: {str(e)}")
            return 0
    
    def shutdown(self):
        """Gracefully shutdown load balancer"""
        self.logger.info("Shutting down Load Balancer")
        
        # Clear all data
        self.thread_metrics.clear()
        self.thread_resources.clear()
        self.thread_health.clear()
        self.thread_failures.clear()
        self.thread_weights.clear()
        self.load_history.clear()
        
        self.logger.info("Load Balancer shutdown complete")
