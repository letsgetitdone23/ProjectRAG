#!/usr/bin/env python3
"""
Script to update vector store with embeddings and chunks
"""

import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from storage.vector_store import VectorStoreManager

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('vector_store.log')
        ]
    )

def load_config():
    """Load configuration"""
    config = {
        'embeddings_dir': os.getenv('EMBEDDINGS_DIR', 'data/embeddings'),
        'chunks_dir': os.getenv('CHUNKS_DIR', 'data/chunks'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'query_processor': {
            'embedding_model': 'BAAI/bge-large-en-v1.5',
            'max_sentences': 3,
            'require_source': True,
            'facts_only': True,
            'llm': {
                'type': 'template'  # Use template-based responses for testing
            }
        },
        'vector_store': {
            'type': 'chromadb',
            'index_name': 'mutual-fund-faq-bge',
            'dimension': 1024,
            'metric': 'cosine',
            'persist_directory': './chroma_db_bge'
        }
    }
    
    # Add provider-specific config
    vector_store_config = {}
    if config['vector_store']['type'] == 'pinecone':
        vector_store_config.update({
            'api_key': os.getenv('PINECONE_API_KEY'),
            'environment': os.getenv('PINECONE_ENVIRONMENT')
        })
    elif config['vector_store']['type'] == 'weaviate':
        vector_store_config.update({
            'url': os.getenv('WEAVIATE_URL'),
            'api_key': os.getenv('WEAVIATE_API_KEY')
        })
    elif config['vector_store']['type'] == 'chromadb':
        vector_store_config.update({
            'persist_directory': os.getenv('CHROMADB_DIR', './chroma_db')
        })
    
    config['vector_store'] = vector_store_config
    return config

def find_latest_files(directory: Path, pattern: str) -> str:
    """Find the latest file matching pattern"""
    files = list(directory.glob(pattern))
    
    if not files:
        raise FileNotFoundError(f"No files found matching {pattern} in {directory}")
    
    # Sort by modification time
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest_file = files[0]
    
    logging.info(f"Using latest file: {latest_file}")
    return str(latest_file)

def main():
    """Main vector store update function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config()
        logger.info("Starting vector store update")
        
        # Find latest files
        embeddings_dir = Path(config['embeddings_dir'])
        chunks_dir = Path(config['chunks_dir'])
        
        embeddings_file = find_latest_files(embeddings_dir, 'embeddings_*.json')
        chunks_file = find_latest_files(chunks_dir, 'chunks_*.json')
        
        logger.info(f"Loading embeddings from: {embeddings_file}")
        logger.info(f"Loading chunks from: {chunks_file}")
        
        # Load data
        with open(embeddings_file, 'r', encoding='utf-8') as f:
            embeddings_data = json.load(f)
        
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        
        logger.info(f"Loaded {len(embeddings_data)} embeddings and {len(chunks_data)} chunks")
        
        # Initialize vector store manager
        vector_store_manager = VectorStoreManager(config['vector_store'])
        
        # Store embeddings
        success = vector_store_manager.store_embeddings(embeddings_data, chunks_data)
        
        if success:
            # Get store statistics
            stats = vector_store_manager.get_store_stats()
            
            logger.info("Vector store update completed successfully:")
            logger.info(f"  - Store stats: {stats}")
            
            # Save stats
            stats_file = Path(config['embeddings_dir']) / f"vector_store_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
            
            logger.info(f"  - Stats saved to: {stats_file}")
        else:
            logger.error("Vector store update failed")
            sys.exit(1)
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Vector store update failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
