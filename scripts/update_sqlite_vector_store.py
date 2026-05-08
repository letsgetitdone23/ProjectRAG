#!/usr/bin/env python3
"""
Update SQLite Vector Store
Updates local SQLite database with latest BGE embeddings
"""

import sys
import json
import logging
import os
from datetime import datetime
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from storage.vector_store import VectorStoreFactory

def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Main update function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting SQLite vector store update...")
        
        # Load latest embeddings
        embeddings_dir = Path('data/embeddings')
        embedding_files = sorted(embeddings_dir.glob('embeddings_*.json'), reverse=True)
        
        if not embedding_files:
            logger.error("No embedding files found")
            return {'success': False, 'error': 'No embedding files available'}
        
        latest_embedding_file = embedding_files[0]
        logger.info(f"Loading embeddings from: {latest_embedding_file}")
        
        with open(latest_embedding_file, 'r', encoding='utf-8') as f:
            embeddings_data = json.load(f)
        
        # Load latest chunks
        chunks_dir = Path('data/chunks')
        chunk_files = sorted(chunks_dir.glob('chunks_*.json'), reverse=True)
        
        if not chunk_files:
            logger.error("No chunk files found")
            return {'success': False, 'error': 'No chunk files available'}
        
        latest_chunk_file = chunk_files[0]
        logger.info(f"Loading chunks from: {latest_chunk_file}")
        
        with open(latest_chunk_file, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        
        # Initialize SQLite vector store
        vector_store_config = {
            'type': 'sqlite',
            'database_path': os.environ.get('DATABASE_PATH', './data/vector_store.db'),
            'dimension': 1024,
            'metric': 'cosine',
            'index_name': os.environ.get('COLLECTION_NAME', 'mutual-fund-faq-bge')
        }
        
        logger.info("Initializing SQLite vector store...")
        vector_store = VectorStoreFactory.create_store(vector_store_config)
        
        # Convert embeddings to VectorRecord format
        vector_records = []
        for emb_data in embeddings_data:
            # Find corresponding chunk
            chunk = next((c for c in chunks_data if c['id'] == emb_data['chunk_id']), None)
            if chunk:
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
            # Get vector store statistics
            stats = vector_store.get_stats()
            logger.info(f"SQLite vector store updated successfully: {stats}")
            
            result = {
                'success': True,
                'vectors_added': len(vector_records),
                'collection_name': vector_store_config.get('index_name'),
                'database_path': vector_store_config.get('database_path'),
                'stats': stats,
                'embedding_file': str(latest_embedding_file),
                'chunk_file': str(latest_chunk_file)
            }
        else:
            result = {
                'success': False,
                'error': 'Failed to add vectors to SQLite'
            }
        
        # Set GitHub Actions output
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'w') as f:
                f.write(f"success={result['success']}\n")
                f.write(f"vectors_added={result.get('vectors_added', 0)}\n")
                f.write(f"collection_name={result.get('collection_name', '')}\n")
                f.write(f"database_path={result.get('database_path', '')}\n")
        
        return result
        
    except Exception as e:
        logger.error(f"SQLite vector store update failed: {str(e)}")
        
        # Set GitHub Actions output for failure
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'w') as f:
                f.write(f"success=false\n")
                f.write(f"error={str(e)}\n")
        
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    import os
    result = main()
    sys.exit(0 if result.get('success', False) else 1)
