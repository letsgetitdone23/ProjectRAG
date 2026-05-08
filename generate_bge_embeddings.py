#!/usr/bin/env python3
"""
Simple BGE embedding generation
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import sys

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

from embedding.embedding_generator import EmbeddingGenerator

def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Generate embeddings with BGE model"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load chunks
        chunks_file = "data/chunks/chunks_20260506_184536.json"
        logger.info(f"Loading chunks from: {chunks_file}")
        
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        logger.info(f"Loaded {len(chunks)} chunks")
        
        # Create BGE generator
        generator = EmbeddingGenerator("BAAI/bge-large-en-v1.5")
        logger.info("Using BGE Large English v1.5 model")
        
        # Generate embeddings
        logger.info("Generating embeddings...")
        results = generator.generate_embeddings(chunks)
        
        # Save embeddings
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"data/embeddings/embeddings_{timestamp}.json"
        
        # Simple save
        embeddings_data = []
        for result in results:
            embeddings_data.append({
                'chunk_id': result.chunk_id,
                'embedding': result.embedding,
                'embedding_dimension': result.embedding_dimension,
                'model_name': result.model_name,
                'generation_timestamp': result.generation_timestamp,
                'processing_time_ms': result.processing_time_ms,
                'cache_hit': result.cache_hit
            })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, indent=2)
        
        logger.info(f"Successfully generated {len(embeddings_data)} embeddings")
        logger.info(f"Embeddings saved to: {output_file}")
        logger.info(f"Embedding dimension: {len(embeddings_data[0]['embedding']) if embeddings_data else 0}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
