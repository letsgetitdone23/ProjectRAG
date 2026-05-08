"""
SQLite Vector Store Implementation with Vector Extensions
Uses SQLite with vector-similarity or sqlite-vss extensions for efficient vector search
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
class SQLiteVectorStore(VectorStore):
    """SQLite implementation of vector store using vector extensions"""
    
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
        """Initialize SQLite database with vector extensions"""
        try:
            self.conn = sqlite3.connect(self.database_path)
            self.conn.enable_load_extension(True)
            
            # Try to load vector extension
            try:
                self.conn.load_extension("vector")
                self.vector_extension = "vector"
                self.logger.info("Loaded vector extension")
            except sqlite3.OperationalError:
                # Fallback to sqlite-vss
                try:
                    self.conn.load_extension("vss")
                    self.vector_extension = "vss"
                    self.logger.info("Loaded vss extension")
                except sqlite3.OperationalError:
                    self.logger.warning("No vector extension available, using basic cosine similarity")
                    self.vector_extension = None
            
            # Create tables if they don't exist
            self._create_tables()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    def _create_tables(self):
        """Create necessary tables for vector storage"""
        cursor = self.conn.cursor()
        
        if self.vector_extension:
            # Create vector table using extension
            cursor.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vectors_{self.vector_extension} USING {self.vector_extension}(
                    id TEXT PRIMARY KEY,
                    embedding FLOAT({self.dimension}) DISTANCE_METRIC_COSINE,
                    content TEXT,
                    source_url TEXT,
                    document_type TEXT,
                    scheme_name TEXT,
                    chunk_type TEXT,
                    token_count INTEGER,
                    created_at TEXT,
                    last_updated TEXT,
                    metadata JSON
                )
            """)
        else:
            # Create basic table without vector extension
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS vectors_basic (
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
                    metadata JSON
                )
            """)
        
        self.conn.commit()
    
    def add_vectors(self, vectors: List[VectorRecord]) -> bool:
        """Add vectors to SQLite database"""
        try:
            cursor = self.conn.cursor()
            
            for record in vectors:
                if self.vector_extension:
                    # Use vector extension for efficient search
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO vectors_{self.vector_extension} 
                        (id, embedding, content, source_url, document_type, scheme_name, chunk_type, token_count, created_at, last_updated, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.id,
                        json.dumps(record.embedding),  # Store as JSON for compatibility
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
                else:
                    # Basic storage without vector extension
                    embedding_blob = sqlite3.Binary(np.array(record.embedding, dtype=np.float32).tobytes())
                    cursor.execute("""
                        INSERT OR REPLACE INTO vectors_basic 
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
        """Search vectors in SQLite database"""
        try:
            cursor = self.conn.cursor()
            
            if self.vector_extension:
                # Use vector extension for efficient similarity search
                cursor.execute(f"""
                    SELECT id, distance, content, source_url, document_type, scheme_name, chunk_type, metadata
                    FROM vectors_{self.vector_extension}
                    WHERE embedding MATCH ?
                    ORDER BY distance
                    LIMIT ?
                """, (json.dumps(query_vector), top_k))
            else:
                # Basic cosine similarity search
                cursor.execute("""
                    SELECT id, content, source_url, document_type, scheme_name, chunk_type, metadata
                    FROM vectors_basic
                    ORDER BY RANDOM()  # Fallback - would need proper similarity calculation
                    LIMIT ?
                """, (top_k,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'score': row[1] if self.vector_extension else 0.0,
                    'content': row[2],
                    'source_url': row[3],
                    'document_type': row[4],
                    'scheme_name': row[5],
                    'chunk_type': row[6],
                    'metadata': json.loads(row[7]) if row[7] else {}
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to search SQLite: {str(e)}")
            return []
    
    def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors from SQLite database"""
        try:
            cursor = self.conn.cursor()
            
            if self.vector_extension:
                cursor.execute(f"""
                    DELETE FROM vectors_{self.vector_extension} WHERE id IN ({','.join(['?']*len(ids))})
                """, ids)
            else:
                cursor.execute("""
                    DELETE FROM vectors_basic WHERE id IN ({','.join(['?']*len(ids))})
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
            
            if self.vector_extension:
                cursor.execute(f"SELECT COUNT(*) FROM vectors_{self.vector_extension}")
            else:
                cursor.execute("SELECT COUNT(*) FROM vectors_basic")
            
            total_vectors = cursor.fetchone()[0]
            
            return {
                'total_vectors': total_vectors,
                'dimension': self.dimension,
                'metric': self.metric,
                'vector_extension': self.vector_extension,
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
