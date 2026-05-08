#!/usr/bin/env python3
"""
Simple RAG Test without complex imports
Test basic RAG functionality
"""

import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

def main():
    """Simple RAG test"""
    print("🤖 Testing RAG System (Simplified)")
    print("=" * 50)
    
    try:
        # Test basic imports
        print("🔧 Testing imports...")
        
        # Test vector store
        from storage.vector_store import VectorStoreFactory
        print("✅ Vector store import successful")
        
        # Test SQLite vector store
        vector_store_config = {
            'type': 'sqlite',
            'database_path': './data/vector_store.db',
            'dimension': 1024,
            'metric': 'cosine'
        }
        
        vector_store = VectorStoreFactory.create_store(vector_store_config)
        print("✅ SQLite vector store created")
        
        # Test embedding generation
        from embedding.embedding_service import EmbeddingService
        embedding_config = {
            'model_name': 'BAAI/bge-large-en-v1.5',
            'batch_size': 32,
            'max_length': 512
        }
        
        embedding_service = EmbeddingService(embedding_config)
        print("✅ Embedding service created")
        
        # Test query processing without LLM (template-based)
        print("\n📝 Testing template-based response generation...")
        
        # Sample query
        query = "What is the NAV of Nippon India Large Cap Fund Direct Growth?"
        
        # Generate query embedding
        query_embedding = embedding_service.generate_embedding(query)
        print(f"✅ Query embedding generated (dim: {len(query_embedding)})")
        
        # Search vector store
        search_results = vector_store.search(query_embedding, top_k=3)
        print(f"✅ Found {len(search_results)} relevant chunks")
        
        if search_results:
            best_result = search_results[0]
            print(f"📋 Best chunk score: {best_result['score']:.3f}")
            print(f"🔗 Source: {best_result.get('source_url', 'N/A')}")
            print(f"📄 Content preview: {best_result['content'][:100]}...")
            
            # Simple template response
            answer = f"Based on the latest available information, the NAV details for Nippon India Large Cap Fund Direct Growth can be found in the official documentation. Please refer to the fund's fact sheet for the most current NAV information."
            
            print(f"\n🎯 Template Response:")
            print(f"📋 Question: {query}")
            print(f"💬 Answer: {answer}")
            print(f"🔗 Source: {best_result.get('source_url', 'N/A')}")
            print(f"📊 Confidence: {best_result['score']:.3f}")
        
        else:
            print("❌ No relevant chunks found")
        
        print("\n" + "=" * 50)
        print("✅ Simple RAG test completed!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
