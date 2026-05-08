#!/usr/bin/env python3
"""
Test BGE embedding generation
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

from embedding.embedding_generator import EmbeddingGenerator

def test_bge():
    """Test BGE embedding generation"""
    generator = EmbeddingGenerator("BAAI/bge-large-en-v1.5")
    
    # Test with simple text
    test_text = "This is a test chunk about mutual funds."
    
    try:
        result = generator.generate_embeddings([{"id": "test", "content": test_text}])
        print(f"Success: Generated {len(result)} embeddings")
        print(f"Embedding dimension: {len(result[0].embedding) if result else 0}")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bge()
