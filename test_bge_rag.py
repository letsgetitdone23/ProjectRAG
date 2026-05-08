#!/usr/bin/env python3
"""
Test RAG service with BGE embeddings
"""

import sys
import logging
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

from retrieval.rag_service import create_rag_service

def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_bge_rag():
    """Test RAG service with BGE embeddings"""
    logger = logging.getLogger(__name__)
    
    try:
        # Create RAG service with BGE configuration
        config = {
            'query_processor': {
                'embedding_model': 'BAAI/bge-large-en-v1.5',
                'max_sentences': 3,
                'require_source': True,
                'facts_only': True,
                'llm': {
                    'type': 'template'
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
        
        logger.info("Creating RAG service with BGE model...")
        rag_service = create_rag_service(config)
        logger.info("RAG service created successfully")
        
        # Test query
        test_query = "What is NAV of Nippon India Large Cap Fund?"
        logger.info(f"Testing query: {test_query}")
        
        result = rag_service.process_query(test_query)
        
        logger.info(f"Query result:")
        logger.info(f"  Answer: {result.answer}")
        logger.info(f"  Source URL: {result.source_url}")
        logger.info(f"  Confidence: {result.confidence_score:.2f}")
        logger.info(f"  Processing Time: {result.processing_time_ms:.2f}ms")
        
        # Health check
        health = rag_service.health_check()
        logger.info(f"Health status: {health['status']}")
        
        return True
        
    except Exception as e:
        logger.error(f"RAG test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_logging()
    success = test_bge_rag()
    sys.exit(0 if success else 1)
