"""
Session Manager for Multi-thread RAG Service
Handles multiple concurrent conversations with thread isolation and context management
"""

import logging
import uuid
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json
from pathlib import Path

from ..retrieval.rag_service import RAGService

@dataclass
class ConversationContext:
    """Represents a conversation context within a thread"""
    thread_id: str
    user_id: Optional[str] = None
    conversation_history: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    memory_limit: int = 50  # Maximum conversation turns
    context_window: int = 10  # Recent context for RAG
    
    def add_message(self, message: Dict):
        """Add a message to conversation history"""
        self.conversation_history.append(message)
        self.last_activity = datetime.now()
        
        # Trim history if exceeds memory limit
        if len(self.conversation_history) > self.memory_limit:
            self.conversation_history = self.conversation_history[-self.memory_limit:]
    
    def get_recent_context(self) -> List[Dict]:
        """Get recent context for RAG processing"""
        return self.conversation_history[-self.context_window:]
    
    def is_expired(self, max_age_hours: int = 24) -> bool:
        """Check if conversation context is expired"""
        return datetime.now() - self.last_activity > timedelta(hours=max_age_hours)

@dataclass
class ThreadSession:
    """Represents a thread session with isolated context"""
    thread_id: str
    rag_service: RAGService
    active_conversations: Dict[str, ConversationContext] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    max_concurrent_conversations: int = 10
    
    def get_or_create_conversation(self, user_id: Optional[str] = None) -> ConversationContext:
        """Get existing conversation or create new one"""
        # Simple strategy: one conversation per user in this thread
        conversation_id = user_id or f"anonymous_{uuid.uuid4().hex[:8]}"
        
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = ConversationContext(
                thread_id=self.thread_id,
                user_id=user_id
            )
        
        conversation = self.active_conversations[conversation_id]
        conversation.last_activity = datetime.now()
        
        return conversation
    
    def cleanup_expired_conversations(self):
        """Remove expired conversations"""
        expired_ids = [
            conv_id for conv_id, conv in self.active_conversations.items()
            if conv.is_expired()
        ]
        
        for conv_id in expired_ids:
            del self.active_conversations[conv_id]
    
    def can_accept_new_conversation(self) -> bool:
        """Check if thread can accept new conversation"""
        return len(self.active_conversations) < self.max_concurrent_conversations

class SessionManager:
    """Manages multiple concurrent RAG conversations with thread isolation"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Thread pool management
        self.active_threads: Dict[str, ThreadSession] = {}
        self.thread_lock = threading.Lock()
        self.max_threads = config.get('max_threads', 5)
        self.session_timeout = config.get('session_timeout_hours', 24)
        
        # Session persistence
        self.persist_sessions = config.get('persist_sessions', True)
        self.session_storage_path = Path(config.get('session_storage_path', './data/sessions'))
        
        if self.persist_sessions:
            self.session_storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing sessions
        if self.persist_sessions:
            self._load_persisted_sessions()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_sessions, daemon=True)
        self.cleanup_thread.start()
        
        self.logger.info(f"Session Manager initialized with max_threads={self.max_threads}")
    
    def create_thread_session(self) -> Optional[ThreadSession]:
        """Create a new thread session"""
        with self.thread_lock:
            if len(self.active_threads) >= self.max_threads:
                self.logger.warning("Maximum thread limit reached")
                return None
            
            # Create thread ID
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
            
            # Create RAG service for this thread
            rag_config = self.config.get('rag_config', {})
            rag_service = RAGService(rag_config)
            
            # Create thread session
            thread_session = ThreadSession(
                thread_id=thread_id,
                rag_service=rag_service
            )
            
            self.active_threads[thread_id] = thread_session
            
            self.logger.info(f"Created new thread session: {thread_id}")
            return thread_session
    
    def get_available_thread(self) -> Optional[ThreadSession]:
        """Get an available thread session or create new one"""
        with self.thread_lock:
            # Find thread with capacity
            for thread_session in self.active_threads.values():
                if thread_session.can_accept_new_conversation():
                    return thread_session
            
            # Create new thread if under limit
            if len(self.active_threads) < self.max_threads:
                return self.create_thread_session()
            
            return None
    
    def process_query(self, query: str, user_id: Optional[str] = None, 
                     thread_id: Optional[str] = None) -> Dict:
        """Process a query in appropriate thread session"""
        # Get or create thread session
        if thread_id and thread_id in self.active_threads:
            thread_session = self.active_threads[thread_id]
        else:
            thread_session = self.get_available_thread()
            
            if not thread_session:
                return {
                    'error': 'No available threads',
                    'message': 'System is busy, please try again later'
                }
        
        # Get or create conversation context
        conversation = thread_session.get_or_create_conversation(user_id)
        
        # Add user message to context
        user_message = {
            'type': 'user',
            'content': query,
            'timestamp': datetime.now().isoformat(),
            'thread_id': thread_session.thread_id
        }
        conversation.add_message(user_message)
        
        try:
            # Process query with RAG service
            recent_context = conversation.get_recent_context()
            
            # Extract previous queries for context
            previous_queries = [msg['content'] for msg in recent_context if msg['type'] == 'user']
            
            # Process with context
            result = thread_session.rag_service.process_query(query, previous_queries)
            
            # Add assistant response to context
            assistant_message = {
                'type': 'assistant',
                'content': result.answer,
                'timestamp': datetime.now().isoformat(),
                'thread_id': thread_session.thread_id,
                'source_url': result.source_url,
                'confidence': result.confidence_score
            }
            conversation.add_message(assistant_message)
            
            # Persist session if enabled
            if self.persist_sessions:
                self._persist_session(thread_session.thread_id, conversation)
            
            return {
                'response': result.answer,
                'source_url': result.source_url,
                'confidence': result.confidence_score,
                'thread_id': thread_session.thread_id,
                'conversation_id': conversation.user_id or 'anonymous',
                'processing_time_ms': result.processing_time_ms,
                'context_length': len(recent_context)
            }
            
        except Exception as e:
            self.logger.error(f"Error processing query in thread {thread_session.thread_id}: {str(e)}")
            
            # Add error message to context
            error_message = {
                'type': 'assistant',
                'content': 'I apologize, but I encountered an error processing your request.',
                'timestamp': datetime.now().isoformat(),
                'thread_id': thread_session.thread_id,
                'error': str(e)
            }
            conversation.add_message(error_message)
            
            return {
                'error': 'Processing failed',
                'message': 'I apologize, but I encountered an error processing your request.',
                'thread_id': thread_session.thread_id
            }
    
    def get_thread_stats(self) -> Dict:
        """Get statistics about active threads"""
        with self.thread_lock:
            total_conversations = sum(
                len(thread.active_conversations) 
                for thread in self.active_threads.values()
            )
            
            return {
                'active_threads': len(self.active_threads),
                'total_conversations': total_conversations,
                'max_threads': self.max_threads,
                'threads': [
                    {
                        'thread_id': thread.thread_id,
                        'conversations': len(thread.active_conversations),
                        'created_at': thread.created_at.isoformat(),
                        'last_activity': thread.last_activity.isoformat()
                    }
                    for thread in self.active_threads.values()
                ]
            }
    
    def _cleanup_expired_sessions(self):
        """Background thread to cleanup expired sessions"""
        while True:
            try:
                time.sleep(300)  # Check every 5 minutes
                
                with self.thread_lock:
                    # Cleanup expired conversations
                    for thread_session in self.active_threads.values():
                        thread_session.cleanup_expired_conversations()
                    
                    # Remove inactive threads
                    inactive_threads = [
                        thread_id for thread_id, thread in self.active_threads.items()
                        if thread.is_expired(self.session_timeout)
                    ]
                    
                    for thread_id in inactive_threads:
                        del self.active_threads[thread_id]
                        self.logger.info(f"Removed inactive thread: {thread_id}")
                
            except Exception as e:
                self.logger.error(f"Error in cleanup thread: {str(e)}")
    
    def _persist_session(self, thread_id: str, conversation: ConversationContext):
        """Persist conversation session to storage"""
        try:
            session_file = self.session_storage_path / f"{thread_id}_{conversation.user_id or 'anonymous'}.json"
            
            session_data = {
                'thread_id': thread_id,
                'user_id': conversation.user_id,
                'conversation_history': conversation.conversation_history,
                'created_at': conversation.created_at.isoformat(),
                'last_activity': conversation.last_activity.isoformat(),
                'memory_limit': conversation.memory_limit,
                'context_window': conversation.context_window
            }
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Failed to persist session: {str(e)}")
    
    def _load_persisted_sessions(self):
        """Load persisted sessions from storage"""
        try:
            if not self.session_storage_path.exists():
                return
            
            for session_file in self.session_storage_path.glob("*.json"):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                    
                    # This would need to be integrated with thread creation
                    # For now, just log that sessions were found
                    self.logger.info(f"Found persisted session: {session_file.name}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to load session {session_file}: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Failed to load persisted sessions: {str(e)}")
    
    def shutdown(self):
        """Gracefully shutdown session manager"""
        self.logger.info("Shutting down Session Manager")
        
        # Persist all active sessions
        if self.persist_sessions:
            with self.thread_lock:
                for thread_session in self.active_threads.values():
                    for conversation in thread_session.active_conversations.values():
                        self._persist_session(thread_session.thread_id, conversation)
        
        # Clear active threads
        with self.thread_lock:
            self.active_threads.clear()
        
        self.logger.info("Session Manager shutdown complete")
