#!/usr/bin/env python3
"""
Update ChromaDB Cloud with New Embeddings
Updates ChromaDB cloud collection with latest BGE embeddings
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
        logger.info("Starting ChromaDB cloud update...")
        
        # Check if update is needed
        update_vector_store = os.environ.get('UPDATE_VECTOR_STORE', 'false').lower() == 'true'
        
        if not update_vector_store:
            logger.info("Vector store update skipped (UPDATE_VECTOR_STORE=false)")
            return {'success': True, 'message': 'Update skipped'}
        
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
        
        # Initialize ChromaDB vector store
        vector_store_config = {
            'type': 'chromadb',
            'index_name': os.environ.get('COLLECTION_NAME', 'mutual-fund-faq-bge'),
            'dimension': 1024,
            'metric': 'cosine',
            'persist_directory': './chroma_db_bge'
        }
        
        # Add ChromaDB configuration
        if 'CHROMA_HOST' in os.environ:
            vector_store_config.update({
                'chroma_settings': {
                    'chroma_server_host': os.environ.get('CHROMA_HOST'),
                    'chroma_server_http_port': int(os.environ.get('CHROMA_PORT', 8000)),
                    'chroma_server_headers': {
                        'X-Chroma-Token': os.environ.get('CHROMA_API_KEY', '')
                    }
                }
            })
        
        logger.info("Initializing ChromaDB vector store...")
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
        
        # Add vectors to ChromaDB
        logger.info("Adding vectors to ChromaDB cloud...")
        success = vector_store.add_vectors(vector_records)
        
        if success:
            # Get vector store statistics
            stats = vector_store.get_stats()
            logger.info(f"ChromaDB updated successfully: {stats}")
            
            result = {
                'success': True,
                'vectors_added': len(vector_records),
                'collection_name': vector_store_config.get('index_name'),
                'stats': stats,
                'chunk_file': str(latest_chunk_file),
                'embedding_file': str(latest_embedding_file)
            }
        else:
            result = {
                'success': False,
                'error': 'Failed to add vectors to ChromaDB'
            }
        
        # Set GitHub Actions output
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'w') as f:
                f.write(f"success={result['success']}\n")
                f.write(f"vectors_added={result.get('vectors_added', 0)}\n")
                f.write(f"collection_name={result.get('collection_name', '')}\n")
        
        return result
        
    except Exception as e:
        logger.error(f"ChromaDB update failed: {str(e)}")
        
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
