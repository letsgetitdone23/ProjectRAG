#!/usr/bin/env python3
"""
Test SQLite Vector Store with BGE embeddings
"""

import sys
import json
import logging
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

from storage.sqlite_simple import SimpleSQLiteVectorStore as SQLiteVectorStore
from embedding.embedding_generator import EmbeddingGenerator

def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_sqlite_vector_store():
    """Test SQLite vector store with BGE embeddings"""
    logger = logging.getLogger(__name__)
    
    try:
        # Load existing embeddings
        embeddings_file = "data/embeddings/embeddings_20260506_223021.json"
        chunks_file = "data/chunks/chunks_20260506_184536.json"
        
        logger.info(f"Loading embeddings from: {embeddings_file}")
        logger.info(f"Loading chunks from: {chunks_file}")
        
        with open(embeddings_file, 'r', encoding='utf-8') as f:
            embeddings_data = json.load(f)
        
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        
        logger.info(f"Loaded {len(embeddings_data)} embeddings and {len(chunks_data)} chunks")
        
        # Create SQLite vector store directly
        config = {
            'database_path': './data/vector_store.db',
            'dimension': 1024,
            'metric': 'cosine'
        }
        
        logger.info("Creating SQLite vector store...")
        vector_store = SQLiteVectorStore(config)
        logger.info("SQLite vector store created successfully")
        
        # Convert embeddings to VectorRecord format
        vector_records = []
        for emb_data in embeddings_data:
            # Find corresponding chunk
            chunk = next((c for c in chunks_data if c['id'] == emb_data['chunk_id']), None)
            if chunk:
                # Create VectorRecord object
                from storage.vector_store import VectorRecord
                vector_record = VectorRecord(
                    id=emb_data['chunk_id'],
                    vector=emb_data['embedding'],
                    content=chunk['content'],
                    source_url=chunk.get('source_url', ''),
                    document_type=chunk.get('document_type', ''),
                    scheme_name=chunk.get('scheme_name', ''),
                    chunk_type=chunk.get('chunk_type', ''),
                    token_count=chunk.get('token_count', 0),
                    created_at=chunk.get('created_at', ''),
                    last_updated=chunk.get('last_updated', ''),
                    metadata=chunk.get('metadata', {})
                )
                vector_records.append(vector_record)
        
        logger.info(f"Prepared {len(vector_records)} vector records")
        
        # Add vectors to SQLite
        logger.info("Adding vectors to SQLite...")
        success = vector_store.add_vectors(vector_records)
        
        if success:
            logger.info("Successfully added vectors to SQLite")
            
            # Get statistics
            stats = vector_store.get_stats()
            logger.info(f"SQLite Stats: {stats}")
            
            # Test search
            logger.info("Testing vector search...")
            test_query = [0.1] * 1024  # Dummy query vector
            
            search_results = vector_store.search(test_query, top_k=3)
            logger.info(f"Search results: {len(search_results)} items found")
            
            for i, result in enumerate(search_results):
                logger.info(f"  Result {i+1}: {result.get('id', 'unknown')} (score: {result.get('score', 0):.3f})")
            
            return True
        else:
            logger.error("Failed to add vectors to SQLite")
            return False
        
    except Exception as e:
        logger.error(f"SQLite vector store test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_logging()
    success = test_sqlite_vector_store()
    sys.exit(0 if success else 1)
