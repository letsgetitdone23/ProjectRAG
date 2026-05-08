#!/usr/bin/env python3
"""
Script for processing scraped data
"""

import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from processing.data_processors import DataProcessor
from processing.source_handlers import SourceHandlerFactory

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('processing.log')
        ]
    )

def load_config():
    """Load configuration"""
    config = {
        'input_dir': os.getenv('INPUT_DIR', 'data/raw'),
        'output_dir': os.getenv('OUTPUT_DIR', 'data/processed'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }
    
    # Load YAML config if available
    config_file = Path(__file__).parent.parent / "config" / "scraping_config.yaml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, 'r') as f:
                yaml_config = yaml.safe_load(f)
                config.update(yaml_config.get('data_processing', {}))
        except Exception as e:
            logging.warning(f"Failed to load YAML config: {e}")
    
    return config

def load_scraped_data(input_dir: Path) -> list:
    """Load all scraped data files"""
    scraped_files = list(input_dir.glob('*.json'))
    scraped_data = []
    
    for file_path in scraped_files:
        if 'summary' not in file_path.name and 'failed' not in file_path.name:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    scraped_data.append(data)
            except Exception as e:
                logging.warning(f"Failed to load {file_path}: {e}")
    
    return scraped_data

def main():
    """Main processing function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config()
        logger.info("Starting data processing")
        
        # Create output directory
        output_dir = Path(config['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load scraped data
        input_dir = Path(config['input_dir'])
        scraped_data = load_scraped_data(input_dir)
        
        if not scraped_data:
            logger.warning("No scraped data found to process")
            sys.exit(0)
        
        logger.info(f"Processing {len(scraped_data)} scraped files")
        
        # Initialize processor
        processor = DataProcessor(config)
        
        # Process each file
        processed_data = []
        failed_files = []
        
        for i, raw_content in enumerate(scraped_data):
            try:
                logger.info(f"Processing file {i+1}/{len(scraped_data)}: {raw_content.get('url', 'unknown')}")
                
                # Process content
                processed = processor.process_content(raw_content)
                
                # Apply source-specific handler
                source_category = raw_content.get('metadata', {}).get('url_info', {}).get('source_category', '')
                document_type = raw_content.get('metadata', {}).get('url_info', {}).get('document_type', '')
                
                handler = SourceHandlerFactory.create_handler(source_category, document_type)
                handler_result = handler.process(raw_content)
                
                # Combine results
                combined_result = {
                    'url': processed.original_url,
                    'cleaned_content': processed.cleaned_content,
                    'metadata': {
                        **processed.metadata,
                        **handler_result.metadata
                    },
                    'structured_data': handler_result.structured_data,
                    'tables': handler_result.tables,
                    'quality_score': processed.quality_score,
                    'content_hash': processed.content_hash,
                    'is_duplicate': processed.is_duplicate,
                    'advisory_content_detected': processed.advisory_content_detected,
                    'validation_errors': processed.validation_errors,
                    'quality_indicators': handler_result.quality_indicators
                }
                
                processed_data.append(combined_result)
                
                # Skip duplicates and advisory content
                if processed.is_duplicate:
                    logger.info(f"Skipping duplicate content: {processed.original_url}")
                    continue
                
                if processed.advisory_content_detected:
                    logger.warning(f"Skipping advisory content: {processed.original_url}")
                    continue
                
                if processed.quality_score < 0.6:
                    logger.warning(f"Low quality content: {processed.original_url} (score: {processed.quality_score})")
                    continue
                
            except Exception as e:
                logger.error(f"Failed to process {raw_content.get('url', 'unknown')}: {str(e)}")
                failed_files.append({
                    'url': raw_content.get('url', 'unknown'),
                    'error': str(e)
                })
        
        # Save processed data
        output_file = output_dir / f"processed_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=2, ensure_ascii=False)
        
        # Save failed files
        if failed_files:
            failed_file = output_dir / f"failed_processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump(failed_files, f, indent=2)
        
        # Save processing stats
        stats = processor.get_processing_stats()
        stats_file = output_dir / f"processing_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Processing completed:")
        logger.info(f"  - Successfully processed: {len(processed_data)} files")
        logger.info(f"  - Failed: {len(failed_files)} files")
        logger.info(f"  - Output saved to: {output_file}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
