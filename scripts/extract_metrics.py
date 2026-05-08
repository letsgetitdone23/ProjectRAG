#!/usr/bin/env python3
"""
Script to extract and store key mutual fund metrics from processed data
"""

import os
import sys
import logging
import json
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from storage.metrics_extractor import MetricsExtractor, FundMetrics
from storage.metrics_storage import MetricsStorage

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('metrics_extraction.log')
        ]
    )

def load_config():
    """Load configuration"""
    config = {
        'input_dir': os.getenv('INPUT_DIR', 'data/processed'),
        'output_dir': os.getenv('OUTPUT_DIR', 'data/metrics'),
        'base_dir': os.getenv('BASE_DIR', 'data'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }
    
    # Load YAML config if available
    config_file = Path(__file__).parent.parent / "config" / "data_storage_schema.yaml"
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

def group_data_by_scheme(processed_data: list) -> dict:
    """Group processed data by scheme name"""
    grouped_data = {}
    
    for item in processed_data:
        scheme_name = item.get('metadata', {}).get('url_info', {}).get('scheme_name', 'Unknown')
        
        if scheme_name not in grouped_data:
            grouped_data[scheme_name] = []
        
        grouped_data[scheme_name].append(item)
    
    return grouped_data

def main():
    """Main metrics extraction function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config()
        logger.info("Starting metrics extraction")
        
        # Create output directory
        output_dir = Path(config['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load processed data
        input_dir = Path(config['input_dir'])
        processed_data = load_processed_data(input_dir)
        
        if not processed_data:
            logger.warning("No processed data found for metrics extraction")
            sys.exit(0)
        
        logger.info(f"Processing {len(processed_data)} data items for metrics extraction")
        
        # Group data by scheme
        grouped_data = group_data_by_scheme(processed_data)
        logger.info(f"Found {len(grouped_data)} schemes: {list(grouped_data.keys())}")
        
        # Initialize components
        extractor = MetricsExtractor(config)
        storage = MetricsStorage(config)
        
        # Process each scheme
        extracted_metrics = {}
        
        for scheme_name, scheme_data in grouped_data.items():
            logger.info(f"Extracting metrics for {scheme_name}")
            
            # Extract metrics from each data item
            scheme_metrics = []
            
            for item in scheme_data:
                try:
                    metrics = extractor.extract_metrics_from_content(item)
                    if metrics.quality_score > 0.3:  # Only keep decent quality data
                        scheme_metrics.append(metrics)
                except Exception as e:
                    logger.warning(f"Failed to extract metrics from {item.get('url', 'unknown')}: {e}")
            
            # Consolidate metrics from multiple sources
            if scheme_metrics:
                consolidated_metrics = extractor.consolidate_metrics(scheme_metrics)
                extracted_metrics[scheme_name] = consolidated_metrics
                
                # Store metrics
                storage.store_metrics(consolidated_metrics, scheme_name)
                
                logger.info(f"Extracted metrics for {scheme_name}:")
                logger.info(f"  - NAV: {consolidated_metrics.current_nav}")
                logger.info(f"  - SIP: {consolidated_metrics.sip_minimum}")
                logger.info(f"  - AUM: {consolidated_metrics.aum}")
                logger.info(f"  - Expense Ratio: {consolidated_metrics.expense_ratio}")
                logger.info(f"  - Quality Score: {consolidated_metrics.quality_score}")
            else:
                logger.warning(f"No valid metrics extracted for {scheme_name}")
        
        # Generate summary report
        summary = storage.get_metrics_summary()
        
        # Save summary
        summary_file = output_dir / f"metrics_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Metrics extraction completed:")
        logger.info(f"  - Schemes processed: {len(extracted_metrics)}")
        logger.info(f"  - Summary saved to: {summary_file}")
        
        # Log quality summary
        if summary.get('data_quality'):
            quality = summary['data_quality']
            logger.info(f"  - Average quality score: {quality.get('average_quality_score', 0):.2f}")
            logger.info(f"  - Quality range: {quality.get('min_quality_score', 0):.2f} - {quality.get('max_quality_score', 0):.2f}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Metrics extraction failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
