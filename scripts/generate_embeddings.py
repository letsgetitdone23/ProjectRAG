#!/usr/bin/env python3
"""
Script to generate embeddings from chunks using Sentence-BERT
"""

import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from embedding.embedding_generator import EmbeddingProcessor

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('embedding_generation.log')
        ]
    )

def load_config():
    """Load configuration"""
    config_path = Path(__file__).parent.parent / "config" / "chunking_config.yaml"
    with open(config_path, 'r') as f:
        config = {}
        try:
            import yaml
            config = yaml.safe_load(f)
        except Exception as e:
            logging.warning(f"Failed to load YAML config: {e}")
    
    # Set default values if not present in config
    config.setdefault('input_dir', os.getenv('INPUT_DIR', 'data/chunks'))
    config.setdefault('output_dir', os.getenv('OUTPUT_DIR', 'data/embeddings'))
    config.setdefault('log_level', os.getenv('LOG_LEVEL', 'INFO'))
    
    return config

def find_latest_chunks_file(input_dir: Path) -> str:
    """Find the latest chunks file"""
    chunks_files = list(input_dir.glob('chunks_*.json'))
    
    if not chunks_files:
        raise FileNotFoundError(f"No chunks files found in {input_dir}")
    
    # Sort by modification time
    chunks_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest_file = chunks_files[0]
    
    logging.info(f"Using latest chunks file: {latest_file}")
    return str(latest_file)

def main():
    """Main embedding generation function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config()
        logger.info("Starting embedding generation")
        
        # Create output directory
        output_dir = Path(config['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find latest chunks file
        input_dir = Path(config['input_dir'])
        chunks_file = find_latest_chunks_file(input_dir)
        
        # Initialize embedding processor with BGE model
        embedding_config = {
            'embedding': {
                'model_name': 'BAAI/bge-large-en-v1.5',
                'batch_size': 32,
                'max_length': 512,
                'enable_caching': True
            }
        }
        
        processor = EmbeddingProcessor(embedding_config)
        
        # Process chunks and generate embeddings
        embeddings_file = processor.process_chunks(chunks_file, str(output_dir))
        
        logger.info(f"Embedding generation completed successfully")
        logger.info(f"Embeddings saved to: {embeddings_file}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
