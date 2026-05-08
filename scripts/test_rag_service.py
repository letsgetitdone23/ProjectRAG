#!/usr/bin/env python3
"""
Test script for RAG service
"""

import os
import sys
import logging
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from retrieval.rag_service import create_rag_service

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def load_config():
    """Load RAG configuration"""
    config = {
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
            'index_name': 'mutual-fund-faq',
            'dimension': 1024,
            'metric': 'cosine',
            'persist_directory': './chroma_db'
        }
    }
    return config

def test_rag_service():
    """Test the RAG service with sample queries"""
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config()
        logger.info("Creating RAG service...")
        
        # Create RAG service
        rag_service = create_rag_service(config)
        logger.info("RAG service created successfully")
        
        # Test queries
        test_queries = [
            "What is the NAV of Nippon India Large Cap Fund?",
            "What is the expense ratio of Flexi Cap Fund?",
            "Tell me about Nippon India Multi Asset Allocation Fund",
            "What is the minimum SIP amount?",
            "Should I invest in Nippon India funds?"  # This should trigger advisory refusal
        ]
        
        logger.info("Testing RAG service with sample queries...")
        logger.info("=" * 60)
        
        for i, query in enumerate(test_queries, 1):
            logger.info(f"\nTest Query {i}: {query}")
            logger.info("-" * 40)
            
            try:
                # Process query
                result = rag_service.process_query(query)
                
                # Display results
                logger.info(f"Answer: {result.answer}")
                logger.info(f"Source URL: {result.source_url}")
                logger.info(f"Last Updated: {result.last_updated}")
                logger.info(f"Confidence Score: {result.confidence_score:.2f}")
                logger.info(f"Is Advisory: {result.is_advisory}")
                
                if result.is_advisory:
                    logger.info(f"Refusal Reason: {result.refusal_reason}")
                
                logger.info(f"Processing Time: {result.processing_time_ms:.2f}ms")
                
            except Exception as e:
                logger.error(f"Error processing query: {str(e)}")
        
        logger.info("\n" + "=" * 60)
        logger.info("Testing completed successfully!")
        
        # Get service statistics
        stats = rag_service.get_service_stats()
        logger.info(f"\nService Statistics:")
        logger.info(f"  - Total Queries: {stats['service_info']['queries_processed']}")
        logger.info(f"  - Advisory Refusals: {stats['service_info']['advisory_queries_refused']}")
        logger.info(f"  - Uptime: {stats['service_info']['uptime_seconds']:.2f}s")
        
        # Health check
        health = rag_service.health_check()
        logger.info(f"\nHealth Status: {health['status']}")
        for component, status in health['components'].items():
            logger.info(f"  - {component}: {status.get('status', 'unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"RAG service test failed: {str(e)}")
        return False

def main():
    """Main test function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting RAG service test...")
    
    success = test_rag_service()
    
    if success:
        logger.info("RAG service test completed successfully!")
        sys.exit(0)
    else:
        logger.error("RAG service test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
