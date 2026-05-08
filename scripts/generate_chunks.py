#!/usr/bin/env python3
"""
Script to generate chunks from processed data using hybrid chunking strategy
"""

import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from chunking.chunking_strategy import ChunkingProcessor

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('chunking.log')
        ]
    )

def load_config():
    """Load configuration"""
    config = {
        'input_dir': os.getenv('INPUT_DIR', 'data/processed'),
        'output_dir': os.getenv('OUTPUT_DIR', 'data/chunks'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }
    
    # Load YAML config if available
    config_file = Path(__file__).parent.parent / "config" / "chunking_config.yaml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, 'r') as f:
                yaml_config = yaml.safe_load(f)
                config.update(yaml_config)
        except Exception as e:
            logging.warning(f"Failed to load YAML config: {e}")
    
    return config

def load_processed_data(input_dir: Path) -> list:
    """Load processed data files"""
    processed_files = list(input_dir.glob('processed_data_*.json'))
    processed_data = []
    
    for file_path in processed_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                processed_data.extend(data)
        except Exception as e:
            logging.warning(f"Failed to load {file_path}: {e}")
    
    return processed_data

def main():
    """Main chunking function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config()
        logger.info("Starting chunking process")
        
        # Create output directory
        output_dir = Path(config['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load processed data
        input_dir = Path(config['input_dir'])
        processed_data = load_processed_data(input_dir)
        
        if not processed_data:
            logger.warning("No processed data found for chunking")
            sys.exit(0)
        
        logger.info(f"Loaded {len(processed_data)} processed documents")
        
        # Initialize chunking processor
        processor = ChunkingProcessor(config)
        
        # Process documents
        chunks = processor.process_documents(processed_data)
        
        if not chunks:
            logger.warning("No chunks generated")
            sys.exit(0)
        
        # Save chunks
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"chunks_{timestamp}.json"
        processor.save_chunks(chunks, str(output_file))
        
        # Generate statistics
        stats = processor.get_chunking_stats(chunks)
        
        # Save statistics
        stats_file = output_dir / f"chunking_stats_{timestamp}.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        
        # Log results
        logger.info(f"Chunking completed successfully:")
        logger.info(f"  - Total chunks: {stats.get('total_chunks', 0)}")
        logger.info(f"  - Chunk types: {stats.get('chunk_types', {})}")
        logger.info(f"  - Average tokens: {stats.get('token_stats', {}).get('avg_tokens', 0):.1f}")
        logger.info(f"  - Average quality: {stats.get('quality_stats', {}).get('avg_quality', 0):.2f}")
        logger.info(f"  - Chunks saved to: {output_file}")
        logger.info(f"  - Stats saved to: {stats_file}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Chunking failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
