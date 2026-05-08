"""
Context Manager for Thread Isolation
Manages conversation context with memory limits and thread isolation
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
import json
from pathlib import Path
import hashlib

from .session_manager import ConversationContext

@dataclass
class ContextWindow:
    """Represents a sliding window of conversation context"""
    window_size: int = 10
    max_tokens: int = 4000
    messages: List[Dict] = field(default_factory=list)
    total_tokens: int = 0
    
    def add_message(self, message: Dict, token_count: int):
        """Add message to context window"""
        self.messages.append(message)
        self.total_tokens += token_count
        
        # Trim window if exceeds limits
        self._trim_window()
    
    def _trim_window(self):
        """Trim window to fit within limits"""
        while (len(self.messages) > self.window_size or 
               self.total_tokens > self.max_tokens) and self.messages:
            removed = self.messages.pop(0)
            self.total_tokens -= removed.get('token_count', 0)
    
    def get_context(self) -> List[Dict]:
        """Get current context messages"""
        return self.messages.copy()
    
    def get_context_summary(self) -> str:
        """Get summary of context for logging"""
        if not self.messages:
            return "No context"
        
        recent_messages = self.messages[-3:]  # Last 3 messages
        summary_parts = []
        
        for msg in recent_messages:
            msg_type = msg.get('type', 'unknown')
            content_preview = msg.get('content', '')[:50] + "..." if len(msg.get('content', '')) > 50 else msg.get('content', '')
            summary_parts.append(f"{msg_type}: {content_preview}")
        
        return " | ".join(summary_parts)

@dataclass
class ContextMetrics:
    """Metrics for context management"""
    total_contexts: int = 0
    active_contexts: int = 0
    total_messages: int = 0
    total_tokens: int = 0
    average_context_size: float = 0.0
    memory_usage_mb: float = 0.0
    context_hits: int = 0
    context_misses: int = 0
    
    def update_metrics(self, context_size: int, token_count: int):
        """Update metrics with new context data"""
        self.total_messages += 1
        self.total_tokens += token_count
        
        if self.total_contexts > 0:
            self.average_context_size = (
                (self.average_context_size * (self.total_contexts - 1) + context_size) / 
                self.total_contexts
            )

class ContextManager:
    """Manages conversation context with thread isolation and memory management"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Context configuration
        self.max_contexts_per_thread = config.get('max_contexts_per_thread', 10)
        self.default_window_size = config.get('default_window_size', 10)
        self.max_tokens_per_context = config.get('max_tokens_per_context', 4000)
        self.context_ttl_hours = config.get('context_ttl_hours', 24)
        
        # Thread-isolated context storage
        self.thread_contexts: Dict[str, Dict[str, ConversationContext]] = defaultdict(dict)
        self.context_windows: Dict[str, Dict[str, ContextWindow]] = defaultdict(dict)
        self.context_lock = threading.RLock()
        
        # Context cache for frequently accessed contexts
        self.context_cache: Dict[str, ConversationContext] = {}
        self.cache_max_size = config.get('context_cache_size', 100)
        
        # Metrics
        self.metrics = ContextMetrics()
        
        # Persistence
        self.persist_contexts = config.get('persist_contexts', True)
        self.context_storage_path = Path(config.get('context_storage_path', './data/contexts'))
        
        if self.persist_contexts:
            self.context_storage_path.mkdir(parents=True, exist_ok=True)
        
        # Cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_contexts, daemon=True)
        self.cleanup_thread.start()
        
        self.logger.info("Context Manager initialized with thread isolation")
    
    def get_or_create_context(self, thread_id: str, user_id: Optional[str] = None,
                            context_id: Optional[str] = None) -> ConversationContext:
        """Get existing context or create new one with thread isolation"""
        with self.context_lock:
            # Generate context ID if not provided
            if not context_id:
                context_id = self._generate_context_id(thread_id, user_id)
            
            # Check cache first
            cache_key = f"{thread_id}:{context_id}"
            if cache_key in self.context_cache:
                self.metrics.context_hits += 1
                return self.context_cache[cache_key]
            
            self.metrics.context_misses += 1
            
            # Get thread-specific contexts
            thread_contexts = self.thread_contexts[thread_id]
            
            # Create new context if doesn't exist
            if context_id not in thread_contexts:
                # Check thread capacity
                if len(thread_contexts) >= self.max_contexts_per_thread:
                    self._evict_oldest_context(thread_id)
                
                # Create new context
                context = ConversationContext(
                    thread_id=thread_id,
                    user_id=user_id
                )
                
                thread_contexts[context_id] = context
                
                # Create context window
                if thread_id not in self.context_windows:
                    self.context_windows[thread_id] = {}
                
                self.context_windows[thread_id][context_id] = ContextWindow(
                    window_size=self.default_window_size,
                    max_tokens=self.max_tokens_per_context
                )
                
                # Update metrics
                self.metrics.total_contexts += 1
                self.metrics.active_contexts += 1
                
                self.logger.info(f"Created new context: {context_id} in thread {thread_id}")
            
            # Cache the context
            self._cache_context(cache_key, thread_contexts[context_id])
            
            return thread_contexts[context_id]
    
    def add_message_to_context(self, thread_id: str, context_id: str, 
                             message: Dict, token_count: int = 0) -> bool:
        """Add message to context with thread isolation"""
        with self.context_lock:
            try:
                # Get context
                context = self.get_or_create_context(thread_id, context_id=context_id)
                
                # Add message to conversation history
                context.add_message(message)
                
                # Add to context window
                if (thread_id in self.context_windows and 
                    context_id in self.context_windows[thread_id]):
                    window = self.context_windows[thread_id][context_id]
                    window.add_message(message, token_count)
                
                # Update metrics
                self.metrics.update_metrics(len(context.conversation_history), token_count)
                
                # Persist context if enabled
                if self.persist_contexts:
                    self._persist_context(thread_id, context_id, context)
                
                return True
                
            except Exception as e:
                self.logger.error(f"Error adding message to context {context_id}: {str(e)}")
                return False
    
    def get_context_window(self, thread_id: str, context_id: str) -> List[Dict]:
        """Get context window for RAG processing"""
        with self.context_lock:
            if (thread_id in self.context_windows and 
                context_id in self.context_windows[thread_id]):
                window = self.context_windows[thread_id][context_id]
                return window.get_context()
            
            return []
    
    def get_context_summary(self, thread_id: str, context_id: str) -> str:
        """Get summary of context for debugging"""
        with self.context_lock:
            if (thread_id in self.context_windows and 
                context_id in self.context_windows[thread_id]):
                window = self.context_windows[thread_id][context_id]
                return window.get_context_summary()
            
            return "No context window found"
    
    def clear_context(self, thread_id: str, context_id: str) -> bool:
        """Clear specific context"""
        with self.context_lock:
            try:
                # Remove from thread contexts
                if thread_id in self.thread_contexts:
                    self.thread_contexts[thread_id].pop(context_id, None)
                
                # Remove from context windows
                if thread_id in self.context_windows:
                    self.context_windows[thread_id].pop(context_id, None)
                
                # Remove from cache
                cache_key = f"{thread_id}:{context_id}"
                self.context_cache.pop(cache_key, None)
                
                # Remove persisted context
                if self.persist_contexts:
                    self._remove_persisted_context(thread_id, context_id)
                
                # Update metrics
                self.metrics.active_contexts = max(0, self.metrics.active_contexts - 1)
                
                self.logger.info(f"Cleared context: {context_id} in thread {thread_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error clearing context {context_id}: {str(e)}")
                return False
    
    def clear_thread_contexts(self, thread_id: str) -> int:
        """Clear all contexts for a thread"""
        with self.context_lock:
            cleared_count = 0
            
            try:
                # Get context IDs to clear
                if thread_id in self.thread_contexts:
                    context_ids = list(self.thread_contexts[thread_id].keys())
                    
                    for context_id in context_ids:
                        if self.clear_context(thread_id, context_id):
                            cleared_count += 1
                
                self.logger.info(f"Cleared {cleared_count} contexts in thread {thread_id}")
                return cleared_count
                
            except Exception as e:
                self.logger.error(f"Error clearing thread contexts {thread_id}: {str(e)}")
                return 0
    
    def _generate_context_id(self, thread_id: str, user_id: Optional[str] = None) -> str:
        """Generate unique context ID"""
        timestamp = datetime.now().isoformat()
        unique_string = f"{thread_id}:{user_id or 'anonymous'}:{timestamp}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:16]
    
    def _evict_oldest_context(self, thread_id: str):
        """Evict oldest context from thread"""
        if thread_id not in self.thread_contexts:
            return
        
        # Find oldest context
        oldest_context_id = None
        oldest_time = datetime.now()
        
        for context_id, context in self.thread_contexts[thread_id].items():
            if context.last_activity < oldest_time:
                oldest_time = context.last_activity
                oldest_context_id = context_id
        
        if oldest_context_id:
            self.clear_context(thread_id, oldest_context_id)
            self.logger.info(f"Evicted oldest context: {oldest_context_id} in thread {thread_id}")
    
    def _cache_context(self, cache_key: str, context: ConversationContext):
        """Cache context for fast access"""
        # Remove oldest if cache is full
        if len(self.context_cache) >= self.cache_max_size:
            oldest_key = next(iter(self.context_cache))
            del self.context_cache[oldest_key]
        
        self.context_cache[cache_key] = context
    
    def _cleanup_expired_contexts(self):
        """Background thread to cleanup expired contexts"""
        while True:
            try:
                time.sleep(3600)  # Check every hour
                
                current_time = datetime.now()
                expired_threshold = current_time - timedelta(hours=self.context_ttl_hours)
                
                with self.context_lock:
                    expired_contexts = []
                    
                    for thread_id, contexts in self.thread_contexts.items():
                        for context_id, context in contexts.items():
                            if context.last_activity < expired_threshold:
                                expired_contexts.append((thread_id, context_id))
                    
                    for thread_id, context_id in expired_contexts:
                        self.clear_context(thread_id, context_id)
                
                if expired_contexts:
                    self.logger.info(f"Cleaned up {len(expired_contexts)} expired contexts")
                
            except Exception as e:
                self.logger.error(f"Error during context cleanup: {str(e)}")
    
    def _persist_context(self, thread_id: str, context_id: str, context: ConversationContext):
        """Persist context to storage"""
        try:
            context_file = self.context_storage_path / f"{thread_id}_{context_id}.json"
            
            context_data = {
                'thread_id': thread_id,
                'context_id': context_id,
                'user_id': context.user_id,
                'conversation_history': context.conversation_history,
                'created_at': context.created_at.isoformat(),
                'last_activity': context.last_activity.isoformat(),
                'memory_limit': context.memory_limit,
                'context_window': context.context_window
            }
            
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Failed to persist context: {str(e)}")
    
    def _remove_persisted_context(self, thread_id: str, context_id: str):
        """Remove persisted context file"""
        try:
            context_file = self.context_storage_path / f"{thread_id}_{context_id}.json"
            if context_file.exists():
                context_file.unlink()
                
        except Exception as e:
            self.logger.error(f"Failed to remove persisted context: {str(e)}")
    
    def get_thread_contexts_info(self, thread_id: str) -> Dict:
        """Get information about contexts in a thread"""
        with self.context_lock:
            if thread_id not in self.thread_contexts:
                return {'thread_id': thread_id, 'contexts': [], 'total_contexts': 0}
            
            contexts_info = []
            for context_id, context in self.thread_contexts[thread_id].items():
                contexts_info.append({
                    'context_id': context_id,
                    'user_id': context.user_id,
                    'message_count': len(context.conversation_history),
                    'created_at': context.created_at.isoformat(),
                    'last_activity': context.last_activity.isoformat(),
                    'summary': self.get_context_summary(thread_id, context_id)
                })
            
            return {
                'thread_id': thread_id,
                'contexts': contexts_info,
                'total_contexts': len(contexts_info)
            }
    
    def get_global_metrics(self) -> Dict:
        """Get global context management metrics"""
        with self.context_lock:
            return {
                'total_contexts': self.metrics.total_contexts,
                'active_contexts': self.metrics.active_contexts,
                'total_messages': self.metrics.total_messages,
                'total_tokens': self.metrics.total_tokens,
                'average_context_size': self.metrics.average_context_size,
                'memory_usage_mb': self.metrics.memory_usage_mb,
                'context_hit_rate': (
                    self.metrics.context_hits / 
                    max(1, self.metrics.context_hits + self.metrics.context_misses)
                ),
                'cache_size': len(self.context_cache),
                'thread_count': len(self.thread_contexts),
                'contexts_per_thread': {
                    thread_id: len(contexts)
                    for thread_id, contexts in self.thread_contexts.items()
                }
            }
    
    def shutdown(self):
        """Gracefully shutdown context manager"""
        self.logger.info("Shutting down Context Manager")
        
        # Persist all active contexts
        if self.persist_contexts:
            with self.context_lock:
                for thread_id, contexts in self.thread_contexts.items():
                    for context_id, context in contexts.items():
                        self._persist_context(thread_id, context_id, context)
        
        # Clear all data
        with self.context_lock:
            self.thread_contexts.clear()
            self.context_windows.clear()
            self.context_cache.clear()
        
        self.logger.info("Context Manager shutdown complete")
