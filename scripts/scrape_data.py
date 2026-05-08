#!/usr/bin/env python3
"""
Main script for scraping mutual fund data
"""

import os
import sys
import logging
import json
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from scraping.scraping_service import ScrapingService

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('scraping.log')
        ]
    )

def load_config():
    """Load configuration from environment and config files"""
    config = {
        'output_dir': os.getenv('OUTPUT_DIR', 'data/raw'),
        'force_update': os.getenv('FORCE_UPDATE', 'false').lower() == 'true',
        'specific_scheme': os.getenv('SPECIFIC_SCHEME', ''),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }
    
    # Load YAML config if available
    config_file = Path(__file__).parent.parent / "config" / "scraping_config.yaml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, 'r') as f:
                yaml_config = yaml.safe_load(f)
                config.update(yaml_config)
        except Exception as e:
            logging.warning(f"Failed to load YAML config: {e}")
    
    return config

def main():
    """Main scraping function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config()
        logger.info("Starting data scraping process")
        
        # Initialize scraping service
        scraping_service = ScrapingService(config)
        
        # Run scraping
        results = scraping_service.run_full_scraping(
            force_update=config.get('force_update', False),
            specific_scheme=config.get('specific_scheme') or None
        )
        
        # Log results
        logger.info(f"Scraping completed successfully:")
        logger.info(f"  - Scraped: {results['total_scraped']} URLs")
        logger.info(f"  - Failed: {results['total_failed']} URLs")
        logger.info(f"  - Skipped: {len(results['skipped'])} URLs")
        
        # Save results summary
        safe_summary = {
            'timestamp': results['timestamp'],
            'total_scraped': results['total_scraped'],
            'total_failed': results['total_failed'],
            'failed': results['failed']
        }
        summary_file = Path(config['output_dir']) / f"scraping_summary_{results['timestamp'].replace(':', '-')}.json"
        with open(summary_file, 'w') as f:
            json.dump(safe_summary, f, indent=2)
        
        logger.info(f"Results saved to: {summary_file}")
        
        # Cleanup
        scraping_service.close()
        
        # Exit with appropriate code
        if results['total_failed'] > 0:
            logger.warning(f"Failed to scrape {results['total_failed']} URLs")
            sys.exit(1)
        else:
            logger.info("All URLs scraped successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
