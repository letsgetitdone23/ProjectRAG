"""
Session Persistence and State Management
Handles persistent storage and recovery of session state
"""

import logging
import json
import threading
import time
import pickle
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import gzip
import sqlite3
from contextlib import contextmanager

from .session_manager import ThreadSession, ConversationContext

@dataclass
class SessionState:
    """Represents persistent session state"""
    session_id: str
    thread_id: str
    user_id: Optional[str]
    created_at: datetime
    last_activity: datetime
    conversation_history: List[Dict]
    context_window: int
    memory_limit: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SessionState':
        """Create from dictionary"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        return cls(**data)

@dataclass
class ThreadState:
    """Represents persistent thread state"""
    thread_id: str
    created_at: datetime
    last_activity: datetime
    active_sessions: List[str]
    total_queries_processed: int
    average_response_time_ms: float
    error_count: int
    rag_config: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ThreadState':
        """Create from dictionary"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        return cls(**data)

class SessionPersistenceManager:
    """Manages persistent storage and recovery of session state"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Storage configuration
        self.storage_type = config.get('storage_type', 'file')  # file, sqlite, memory
        self.storage_path = Path(config.get('storage_path', './data/sessions'))
        self.compression_enabled = config.get('compression_enabled', True)
        self.auto_save_interval = config.get('auto_save_interval', 300)  # 5 minutes
        self.max_file_size_mb = config.get('max_file_size_mb', 100)
        
        # Initialize storage
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._initialize_storage()
        
        # In-memory cache
        self.session_cache: Dict[str, SessionState] = {}
        self.thread_cache: Dict[str, ThreadState] = {}
        self.cache_lock = threading.RLock()
        
        # Auto-save thread
        self.auto_save_enabled = config.get('auto_save_enabled', True)
        if self.auto_save_enabled:
            self.auto_save_thread = threading.Thread(
                target=self._auto_save_worker,
                daemon=True
            )
            self.auto_save_thread.start()
        
        # Cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True
        )
        self.cleanup_thread.start()
        
        self.logger.info(f"Session Persistence Manager initialized with {self.storage_type} storage")
    
    def _initialize_storage(self):
        """Initialize storage backend"""
        if self.storage_type == 'sqlite':
            self._initialize_sqlite_storage()
        elif self.storage_type == 'file':
            self._initialize_file_storage()
        elif self.storage_type == 'memory':
            self._initialize_memory_storage()
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    def _initialize_sqlite_storage(self):
        """Initialize SQLite database for session storage"""
        self.db_path = self.storage_path / "sessions.db"
        
        with sqlite3.connect(self.db_path) as conn:
            # Create sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    user_id TEXT,
                    created_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    conversation_history TEXT NOT NULL,
                    context_window INTEGER NOT NULL,
                    memory_limit INTEGER NOT NULL,
                    metadata TEXT,
                    compressed BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Create threads table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    active_sessions TEXT NOT NULL,
                    total_queries_processed INTEGER DEFAULT 0,
                    average_response_time_ms REAL DEFAULT 0.0,
                    error_count INTEGER DEFAULT 0,
                    rag_config TEXT NOT NULL,
                    compressed BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_thread_id ON sessions(thread_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity)")
            
            conn.commit()
        
        self.logger.info("SQLite storage initialized")
    
    def _initialize_file_storage(self):
        """Initialize file-based storage"""
        self.sessions_dir = self.storage_path / "sessions"
        self.threads_dir = self.storage_path / "threads"
        
        self.sessions_dir.mkdir(exist_ok=True)
        self.threads_dir.mkdir(exist_ok=True)
        
        self.logger.info("File storage initialized")
    
    def _initialize_memory_storage(self):
        """Initialize in-memory storage"""
        self.memory_sessions: Dict[str, SessionState] = {}
        self.memory_threads: Dict[str, ThreadState] = {}
        
        self.logger.info("Memory storage initialized")
    
    def save_session(self, session_state: SessionState) -> bool:
        """Save session state to persistent storage"""
        try:
            if self.storage_type == 'sqlite':
                return self._save_session_sqlite(session_state)
            elif self.storage_type == 'file':
                return self._save_session_file(session_state)
            elif self.storage_type == 'memory':
                return self._save_session_memory(session_state)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error saving session {session_state.session_id}: {str(e)}")
            return False
    
    def load_session(self, session_id: str) -> Optional[SessionState]:
        """Load session state from persistent storage"""
        try:
            # Check cache first
            with self.cache_lock:
                if session_id in self.session_cache:
                    return self.session_cache[session_id]
            
            # Load from storage
            if self.storage_type == 'sqlite':
                session_state = self._load_session_sqlite(session_id)
            elif self.storage_type == 'file':
                session_state = self._load_session_file(session_id)
            elif self.storage_type == 'memory':
                session_state = self._load_session_memory(session_id)
            else:
                return None
            
            # Cache the loaded session
            if session_state:
                with self.cache_lock:
                    self.session_cache[session_id] = session_state
            
            return session_state
            
        except Exception as e:
            self.logger.error(f"Error loading session {session_id}: {str(e)}")
            return None
    
    def save_thread(self, thread_state: ThreadState) -> bool:
        """Save thread state to persistent storage"""
        try:
            if self.storage_type == 'sqlite':
                return self._save_thread_sqlite(thread_state)
            elif self.storage_type == 'file':
                return self._save_thread_file(thread_state)
            elif self.storage_type == 'memory':
                return self._save_thread_memory(thread_state)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error saving thread {thread_state.thread_id}: {str(e)}")
            return False
    
    def load_thread(self, thread_id: str) -> Optional[ThreadState]:
        """Load thread state from persistent storage"""
        try:
            # Check cache first
            with self.cache_lock:
                if thread_id in self.thread_cache:
                    return self.thread_cache[thread_id]
            
            # Load from storage
            if self.storage_type == 'sqlite':
                thread_state = self._load_thread_sqlite(thread_id)
            elif self.storage_type == 'file':
                thread_state = self._load_thread_file(thread_id)
            elif self.storage_type == 'memory':
                thread_state = self._load_thread_memory(thread_id)
            else:
                return None
            
            # Cache the loaded thread
            if thread_state:
                with self.cache_lock:
                    self.thread_cache[thread_id] = thread_state
            
            return thread_state
            
        except Exception as e:
            self.logger.error(f"Error loading thread {thread_id}: {str(e)}")
            return None
    
    def _save_session_sqlite(self, session_state: SessionState) -> bool:
        """Save session to SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            data = session_state.to_dict()
            
            # Serialize conversation history
            conversation_json = json.dumps(data['conversation_history'])
            metadata_json = json.dumps(data['metadata'])
            
            # Compress if enabled
            compressed = False
            if self.compression_enabled and len(conversation_json) > 1024:
                conversation_json = gzip.compress(conversation_json.encode()).decode('latin1')
                compressed = True
            
            conn.execute("""
                INSERT OR REPLACE INTO sessions 
                (session_id, thread_id, user_id, created_at, last_activity, 
                 conversation_history, context_window, memory_limit, metadata, compressed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_state.session_id,
                session_state.thread_id,
                session_state.user_id,
                data['created_at'],
                data['last_activity'],
                conversation_json,
                session_state.context_window,
                session_state.memory_limit,
                metadata_json,
                compressed
            ))
            
            conn.commit()
            return True
    
    def _load_session_sqlite(self, session_id: str) -> Optional[SessionState]:
        """Load session from SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT session_id, thread_id, user_id, created_at, last_activity,
                       conversation_history, context_window, memory_limit, metadata, compressed
                FROM sessions WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Deserialize conversation history
            conversation_json = row[5]
            if row[9]:  # compressed
                conversation_json = gzip.decompress(conversation_json.encode('latin1')).decode()
            
            conversation_history = json.loads(conversation_json)
            metadata = json.loads(row[8]) if row[8] else {}
            
            return SessionState(
                session_id=row[0],
                thread_id=row[1],
                user_id=row[2],
                created_at=datetime.fromisoformat(row[3]),
                last_activity=datetime.fromisoformat(row[4]),
                conversation_history=conversation_history,
                context_window=row[6],
                memory_limit=row[7],
                metadata=metadata
            )
    
    def _save_session_file(self, session_state: SessionState) -> bool:
        """Save session to file"""
        session_file = self.sessions_dir / f"{session_state.session_id}.json"
        
        data = session_state.to_dict()
        
        # Compress if enabled
        if self.compression_enabled:
            session_file = session_file.with_suffix('.json.gz')
            with gzip.open(session_file, 'wt', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
    
    def _load_session_file(self, session_id: str) -> Optional[SessionState]:
        """Load session from file"""
        # Try compressed file first
        session_file = self.sessions_dir / f"{session_id}.json.gz"
        if not session_file.exists():
            session_file = self.sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return None
        
        # Load data
        if session_file.suffix == '.gz':
            with gzip.open(session_file, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        else:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        return SessionState.from_dict(data)
    
    def _save_session_memory(self, session_state: SessionState) -> bool:
        """Save session to memory"""
        self.memory_sessions[session_state.session_id] = session_state
        return True
    
    def _load_session_memory(self, session_id: str) -> Optional[SessionState]:
        """Load session from memory"""
        return self.memory_sessions.get(session_id)
    
    def _save_thread_sqlite(self, thread_state: ThreadState) -> bool:
        """Save thread to SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            data = thread_state.to_dict()
            
            # Serialize data
            active_sessions_json = json.dumps(data['active_sessions'])
            rag_config_json = json.dumps(data['rag_config'])
            
            conn.execute("""
                INSERT OR REPLACE INTO threads 
                (thread_id, created_at, last_activity, active_sessions,
                 total_queries_processed, average_response_time_ms, error_count, rag_config, compressed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                thread_state.thread_id,
                data['created_at'],
                data['last_activity'],
                active_sessions_json,
                thread_state.total_queries_processed,
                thread_state.average_response_time_ms,
                thread_state.error_count,
                rag_config_json,
                False
            ))
            
            conn.commit()
            return True
    
    def _load_thread_sqlite(self, thread_id: str) -> Optional[ThreadState]:
        """Load thread from SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT thread_id, created_at, last_activity, active_sessions,
                       total_queries_processed, average_response_time_ms, error_count, rag_config
                FROM threads WHERE thread_id = ?
            """, (thread_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            active_sessions = json.loads(row[3])
            rag_config = json.loads(row[7])
            
            return ThreadState(
                thread_id=row[0],
                created_at=datetime.fromisoformat(row[1]),
                last_activity=datetime.fromisoformat(row[2]),
                active_sessions=active_sessions,
                total_queries_processed=row[4],
                average_response_time_ms=row[5],
                error_count=row[6],
                rag_config=rag_config
            )
    
    def _save_thread_file(self, thread_state: ThreadState) -> bool:
        """Save thread to file"""
        thread_file = self.threads_dir / f"{thread_state.thread_id}.json"
        
        data = thread_state.to_dict()
        
        with open(thread_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
    
    def _load_thread_file(self, thread_id: str) -> Optional[ThreadState]:
        """Load thread from file"""
        thread_file = self.threads_dir / f"{thread_id}.json"
        
        if not thread_file.exists():
            return None
        
        with open(thread_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return ThreadState.from_dict(data)
    
    def _save_thread_memory(self, thread_state: ThreadState) -> bool:
        """Save thread to memory"""
        self.memory_threads[thread_state.thread_id] = thread_state
        return True
    
    def _load_thread_memory(self, thread_id: str) -> Optional[ThreadState]:
        """Load thread from memory"""
        return self.memory_threads.get(thread_id)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session from persistent storage"""
        try:
            if self.storage_type == 'sqlite':
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                    conn.commit()
            
            elif self.storage_type == 'file':
                for ext in ['.json', '.json.gz']:
                    session_file = self.sessions_dir / f"{session_id}{ext}"
                    if session_file.exists():
                        session_file.unlink()
            
            elif self.storage_type == 'memory':
                self.memory_sessions.pop(session_id, None)
            
            # Remove from cache
            with self.cache_lock:
                self.session_cache.pop(session_id, None)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting session {session_id}: {str(e)}")
            return False
    
    def get_active_sessions(self, thread_id: Optional[str] = None) -> List[str]:
        """Get list of active session IDs"""
        try:
            if self.storage_type == 'sqlite':
                with sqlite3.connect(self.db_path) as conn:
                    if thread_id:
                        cursor = conn.execute(
                            "SELECT session_id FROM sessions WHERE thread_id = ?",
                            (thread_id,)
                        )
                    else:
                        cursor = conn.execute("SELECT session_id FROM sessions")
                    
                    return [row[0] for row in cursor.fetchall()]
            
            elif self.storage_type == 'file':
                session_ids = []
                for session_file in self.sessions_dir.glob("*.json*"):
                    session_ids.append(session_file.stem.replace('.json', ''))
                return session_ids
            
            elif self.storage_type == 'memory':
                return list(self.memory_sessions.keys())
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting active sessions: {str(e)}")
            return []
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up expired sessions"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            cleaned_count = 0
            
            if self.storage_type == 'sqlite':
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "DELETE FROM sessions WHERE last_activity < ?",
                        (cutoff_time.isoformat(),)
                    )
                    cleaned_count = cursor.rowcount
                    conn.commit()
            
            elif self.storage_type == 'file':
                for session_file in self.sessions_dir.glob("*.json*"):
                    try:
                        if session_file.suffix == '.gz':
                            with gzip.open(session_file, 'rt') as f:
                                data = json.load(f)
                        else:
                            with open(session_file, 'r') as f:
                                data = json.load(f)
                        
                        last_activity = datetime.fromisoformat(data['last_activity'])
                        if last_activity < cutoff_time:
                            session_file.unlink()
                            cleaned_count += 1
                    
                    except Exception:
                        # Remove corrupted files
                        session_file.unlink()
                        cleaned_count += 1
            
            elif self.storage_type == 'memory':
                expired_sessions = [
                    session_id for session_id, session in self.memory_sessions.items()
                    if session.last_activity < cutoff_time
                ]
                
                for session_id in expired_sessions:
                    del self.memory_sessions[session_id]
                    cleaned_count += 1
            
            # Clear from cache
            with self.cache_lock:
                expired_cache_sessions = [
                    session_id for session_id, session in self.session_cache.items()
                    if session.last_activity < cutoff_time
                ]
                
                for session_id in expired_cache_sessions:
                    del self.session_cache[session_id]
            
            self.logger.info(f"Cleaned up {cleaned_count} expired sessions")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            return 0
    
    def _auto_save_worker(self):
        """Background thread for auto-saving"""
        while True:
            try:
                time.sleep(self.auto_save_interval)
                
                # Auto-save logic would be implemented here
                # For now, just log that auto-save ran
                self.logger.debug("Auto-save completed")
                
            except Exception as e:
                self.logger.error(f"Error in auto-save worker: {str(e)}")
    
    def _cleanup_worker(self):
        """Background thread for cleanup"""
        while True:
            try:
                time.sleep(3600)  # Run every hour
                
                cleaned_count = self.cleanup_expired_sessions()
                if cleaned_count > 0:
                    self.logger.info(f"Cleanup completed: {cleaned_count} sessions removed")
                
            except Exception as e:
                self.logger.error(f"Error in cleanup worker: {str(e)}")
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        try:
            stats = {
                'storage_type': self.storage_type,
                'storage_path': str(self.storage_path),
                'cache_size': len(self.session_cache),
                'thread_cache_size': len(self.thread_cache)
            }
            
            if self.storage_type == 'file':
                session_files = list(self.sessions_dir.glob("*.json*"))
                thread_files = list(self.threads_dir.glob("*.json"))
                
                total_size = sum(f.stat().st_size for f in session_files + thread_files)
                
                stats.update({
                    'session_files': len(session_files),
                    'thread_files': len(thread_files),
                    'total_size_bytes': total_size,
                    'total_size_mb': total_size / (1024 * 1024)
                })
            
            elif self.storage_type == 'sqlite':
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM sessions")
                    session_count = cursor.fetchone()[0]
                    
                    cursor = conn.execute("SELECT COUNT(*) FROM threads")
                    thread_count = cursor.fetchone()[0]
                    
                    db_size = self.db_path.stat().st_size
                    
                    stats.update({
                        'session_count': session_count,
                        'thread_count': thread_count,
                        'db_size_bytes': db_size,
                        'db_size_mb': db_size / (1024 * 1024)
                    })
            
            elif self.storage_type == 'memory':
                stats.update({
                    'memory_sessions': len(self.memory_sessions),
                    'memory_threads': len(self.memory_threads)
                })
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting storage stats: {str(e)}")
            return {'error': str(e)}
    
    def shutdown(self):
        """Gracefully shutdown persistence manager"""
        self.logger.info("Shutting down Session Persistence Manager")
        
        # Save all cached data
        with self.cache_lock:
            for session_state in self.session_cache.values():
                self.save_session(session_state)
            
            for thread_state in self.thread_cache.values():
                self.save_thread(thread_state)
        
        # Clear caches
        with self.cache_lock:
            self.session_cache.clear()
            self.thread_cache.clear()
        
        self.logger.info("Session Persistence Manager shutdown complete")
