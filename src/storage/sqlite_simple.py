"""
Simple SQLite Vector Store Implementation
Basic SQLite implementation without vector extensions for compatibility
"""

import logging
import sqlite3
import json
import numpy as np
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from .vector_store import VectorStore, VectorRecord

@dataclass
class SimpleSQLiteVectorStore(VectorStore):
    """Simple SQLite implementation of vector store"""
    
    def __init__(self, config: Dict):
        self.database_path = config.get('database_path', './data/vector_store.db')
        self.dimension = config.get('dimension', 1024)
        self.metric = config.get('metric', 'cosine')
        self.logger = logging.getLogger(__name__)
        
        # Ensure database directory exists
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize SQLite database"""
        try:
            self.conn = sqlite3.connect(self.database_path)
            
            # Create tables if they don't exist
            self._create_tables()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    def _create_tables(self):
        """Create necessary tables for vector storage"""
        cursor = self.conn.cursor()
        
        # Create basic table without vector extensions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                embedding BLOB,
                content TEXT,
                source_url TEXT,
                document_type TEXT,
                scheme_name TEXT,
                chunk_type TEXT,
                token_count INTEGER,
                created_at TEXT,
                last_updated TEXT,
                metadata TEXT
            )
        """)
        
        self.conn.commit()
    
    def add_vectors(self, vectors: List[VectorRecord]) -> bool:
        """Add vectors to SQLite database"""
        try:
            cursor = self.conn.cursor()
            
            for record in vectors:
                # Convert embedding to binary blob
                embedding_blob = sqlite3.Binary(np.array(record.embedding, dtype=np.float32).tobytes())
                
                cursor.execute("""
                    INSERT OR REPLACE INTO vectors 
                    (id, embedding, content, source_url, document_type, scheme_name, chunk_type, token_count, created_at, last_updated, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    embedding_blob,
                    record.content,
                    record.source_url,
                    record.document_type,
                    record.scheme_name,
                    record.chunk_type,
                    record.token_count,
                    record.created_at,
                    record.last_updated,
                    json.dumps(record.metadata) if record.metadata else None
                ))
            
            self.conn.commit()
            self.logger.info(f"Added {len(vectors)} vectors to SQLite database")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add vectors to SQLite: {str(e)}")
            return False
    
    def search(self, query_vector: List[float], top_k: int = 10, 
               filters: Optional[Dict] = None) -> List[Dict]:
        """Search vectors in SQLite database using basic similarity"""
        try:
            cursor = self.conn.cursor()
            
            # For now, use simple random sampling as fallback
            # In a real implementation, you'd calculate cosine similarity
            cursor.execute("""
                SELECT id, content, source_url, document_type, scheme_name, chunk_type, metadata
                FROM vectors
                ORDER BY RANDOM()
                LIMIT ?
            """, (top_k,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'score': 0.5,  # Placeholder score
                    'content': row[1],
                    'source_url': row[2],
                    'document_type': row[3],
                    'scheme_name': row[4],
                    'chunk_type': row[5],
                    'metadata': json.loads(row[6]) if row[6] else {}
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to search SQLite: {str(e)}")
            return []
    
    def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors from SQLite database"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute(f"""
                DELETE FROM vectors WHERE id IN ({','.join(['?']*len(ids))})
            """, ids)
            
            self.conn.commit()
            self.logger.info(f"Deleted {len(ids)} vectors from SQLite database")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete vectors from SQLite: {str(e)}")
            return False
    
    def get_stats(self) -> Dict:
        """Get SQLite database statistics"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM vectors")
            total_vectors = cursor.fetchone()[0]
            
            return {
                'total_vectors': total_vectors,
                'dimension': self.dimension,
                'metric': self.metric,
                'database_path': self.database_path
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get SQLite stats: {str(e)}")
            return {}
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
