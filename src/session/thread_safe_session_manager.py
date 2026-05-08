"""
Thread-Safe Session Manager
Provides isolated chat sessions with no memory sharing between threads
"""

import threading
import uuid
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import logging

@dataclass
class ChatMessage:
    """Individual chat message"""
    message: str
    response: str
    timestamp: datetime
    user_id: str
    thread_id: str
    source_url: str = ""
    confidence: float = 0.0
    processing_time_ms: float = 0.0

@dataclass
class ThreadSession:
    """Isolated thread session with no shared memory"""
    thread_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    messages: List[ChatMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    
    def add_message(self, message: ChatMessage):
        """Add message to this thread only"""
        self.messages.append(message)
        self.last_activity = datetime.now()
    
    def get_context(self) -> List[Dict]:
        """Get context for this thread only"""
        return [
            {
                "role": "user",
                "content": msg.message,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in self.messages[-5:]  # Last 5 messages for context
        ]

class ThreadSafeSessionManager:
    """Thread-safe session manager with complete isolation"""
    
    def __init__(self, max_sessions_per_user: int = 10, session_timeout_minutes: int = 30):
        self.max_sessions_per_user = max_sessions_per_user
        self.session_timeout_minutes = session_timeout_minutes
        
        # Thread-safe storage
        self._sessions: Dict[str, ThreadSession] = {}
        self._user_sessions: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.RLock()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Thread-safe session manager initialized")
    
    def create_session(self, user_id: str, thread_id: Optional[str] = None) -> ThreadSession:
        """Create new isolated session"""
        with self._lock:
            # Clean up expired sessions first
            self._cleanup_expired_sessions()
            
            # Check session limit per user
            user_thread_ids = self._user_sessions.get(user_id, [])
            if len(user_thread_ids) >= self.max_sessions_per_user:
                # Remove oldest session
                oldest_thread_id = user_thread_ids[0]
                self._remove_session(oldest_thread_id)
            
            # Generate thread ID if not provided
            if not thread_id:
                thread_id = str(uuid.uuid4())
            
            # Create new isolated session
            session = ThreadSession(
                thread_id=thread_id,
                user_id=user_id,
                created_at=datetime.now(),
                last_activity=datetime.now()
            )
            
            # Store session
            self._sessions[thread_id] = session
            self._user_sessions[user_id].append(thread_id)
            
            self.logger.info(f"Created new session: {thread_id} for user: {user_id}")
            return session
    
    def get_session(self, thread_id: str) -> Optional[ThreadSession]:
        """Get session by thread ID"""
        with self._lock:
            session = self._sessions.get(thread_id)
            if session and session.is_active:
                # Update last activity
                session.last_activity = datetime.now()
                return session
            return None
    
    def add_message(self, thread_id: str, message: ChatMessage) -> bool:
        """Add message to specific thread only"""
        with self._lock:
            session = self.get_session(thread_id)
            if session:
                session.add_message(message)
                self.logger.debug(f"Added message to thread: {thread_id}")
                return True
            return False
    
    def get_thread_context(self, thread_id: str) -> List[Dict]:
        """Get context for specific thread only"""
        with self._lock:
            session = self.get_session(thread_id)
            if session:
                return session.get_context()
            return []
    
    def get_user_threads(self, user_id: str) -> List[str]:
        """Get all thread IDs for a user"""
        with self._lock:
            return self._user_sessions.get(user_id, []).copy()
    
    def remove_session(self, thread_id: str) -> bool:
        """Remove specific session"""
        with self._lock:
            return self._remove_session(thread_id)
    
    def _remove_session(self, thread_id: str) -> bool:
        """Internal session removal (called within lock)"""
        session = self._sessions.pop(thread_id, None)
        if session:
            # Remove from user sessions
            user_threads = self._user_sessions.get(session.user_id, [])
            if thread_id in user_threads:
                user_threads.remove(thread_id)
            
            self.logger.info(f"Removed session: {thread_id}")
            return True
        return False
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.now()
        expired_threads = []
        
        for thread_id, session in self._sessions.items():
            inactive_minutes = (current_time - session.last_activity).total_seconds() / 60
            if inactive_minutes > self.session_timeout_minutes:
                expired_threads.append(thread_id)
        
        for thread_id in expired_threads:
            self._remove_session(thread_id)
        
        if expired_threads:
            self.logger.info(f"Cleaned up {len(expired_threads)} expired sessions")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        with self._lock:
            self._cleanup_expired_sessions()
            
            active_sessions = len(self._sessions)
            total_users = len(self._user_sessions)
            
            user_session_counts = [len(threads) for threads in self._user_sessions.values()]
            avg_sessions_per_user = sum(user_session_counts) / len(user_session_counts) if user_session_counts else 0
            
            return {
                "active_sessions": active_sessions,
                "total_users": total_users,
                "avg_sessions_per_user": avg_sessions_per_user,
                "max_sessions_per_user": self.max_sessions_per_user,
                "session_timeout_minutes": self.session_timeout_minutes
            }

# Global thread-safe session manager instance
_session_manager = None
_manager_lock = threading.Lock()

def get_session_manager() -> ThreadSafeSessionManager:
    """Get global thread-safe session manager"""
    global _session_manager
    if _session_manager is None:
        with _manager_lock:
            if _session_manager is None:
                _session_manager = ThreadSafeSessionManager()
    return _session_manager

def create_isolated_session(user_id: str, thread_id: Optional[str] = None) -> ThreadSession:
    """Create new isolated session"""
    return get_session_manager().create_session(user_id, thread_id)

def get_thread_session(thread_id: str) -> Optional[ThreadSession]:
    """Get thread session"""
    return get_session_manager().get_session(thread_id)

def add_thread_message(thread_id: str, message: ChatMessage) -> bool:
    """Add message to thread"""
    return get_session_manager().add_message(thread_id, message)
