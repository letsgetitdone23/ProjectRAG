#!/usr/bin/env python3
"""
Test RAG Query Processing
Test the complete RAG pipeline with Groq LLM
"""

import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

from retrieval.rag_service import RAGService
from storage.vector_store import VectorStoreFactory

def main():
    """Test RAG query processing"""
    print("🤖 Testing RAG System with Groq LLM")
    print("=" * 50)
    
    # Configuration
    config = {
        'rag_config': {
            'llm': {
                'type': 'groq',
                'model': 'llama-3-8b-instruct',
                'api_key': os.environ.get('GROQ_API_KEY', 'dummy_key'),
                'temperature': 0.1,
                'max_tokens': 200
            },
            'embedding_model': 'BAAI/bge-large-en-v1.5',
            'max_sentences': 3,
            'require_source': True,
            'facts_only': True,
            'confidence_threshold': 0.3
        },
        'vector_store': {
            'type': 'sqlite',
            'database_path': './data/vector_store.db',
            'dimension': 1024,
            'metric': 'cosine'
        }
    }
    
    try:
        # Initialize RAG service
        print("🔧 Initializing RAG service...")
        rag_service = RAGService(config)
        
        # Test query
        query = "What is the NAV of Nippon India Large Cap Fund Direct Growth?"
        
        print(f"📝 Processing Query: {query}")
        print("-" * 50)
        
        # Process query
        result = rag_service.process_query(query)
        
        # Display results
        print("🎯 RAG Response:")
        print(f"📋 Question: {query}")
        print(f"💬 Answer: {result.answer}")
        print(f"🔗 Source URL: {result.source_url}")
        print(f"📊 Confidence Score: {result.confidence_score:.3f}")
        print(f"⚠️  Is Advisory: {result.is_advisory}")
        
        if hasattr(result, 'method'):
            print(f"🤖 Generation Method: {result.method}")
        
        if hasattr(result, 'processing_time_ms'):
            print(f"⏱️  Processing Time: {result.processing_time_ms:.2f}ms")
        
        if result.refusal_reason:
            print(f"🚫 Refusal Reason: {result.refusal_reason}")
        
        print("=" * 50)
        print("✅ RAG Query Processing Complete!")
        
        # Get service stats
        stats = rag_service.get_service_stats()
        print(f"\n📊 Service Statistics:")
        print(f"   Total Queries: {stats['service_info']['queries_processed']}")
        print(f"   Advisory Refusals: {stats['service_info']['advisory_queries_refused']}")
        print(f"   Uptime: {stats['service_info']['uptime_seconds']:.2f}s")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
