#!/usr/bin/env python3
"""
Latest Data Scraping Script
Scrapes latest mutual fund data from various sources
"""

import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from scraping.scraping_service import ScrapingService

def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Main scraping function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting latest data scraping...")
        
        # Initialize scraping service
        config = {
            'scraping': {
                'max_retries': 3,
                'request_delay': 1.0,
                'concurrent_requests': 5
            },
            'sources': {
                'amfi': {
                    'enabled': True,
                    'base_url': 'https://www.amfiindia.com',
                    'rate_limit': 10  # requests per minute
                },
                'fund_houses': {
                    'enabled': True,
                    'sources': [
                        {'name': 'HDFC', 'url': 'https://www.hdfcfund.com'},
                        {'name': 'ICICI', 'url': 'https://www.iciciprualamc.com'},
                        {'name': 'Axis', 'url': 'https://www.axismutualfund.com'}
                    ],
                    'rate_limit': 5
                }
            }
        }
        
        scraping_service = ScrapingService(config)
        
        # Scrape AMFI data
        logger.info("Scraping AMFI mutual fund data...")
        amfi_data = scraping_service.scrape_amfi_data()
        
        # Scrape fund house data
        logger.info("Scraping fund house data...")
        fund_house_data = scraping_service.scrape_fund_house_data()
        
        # Combine all data
        all_data = {
            'scraped_at': datetime.now().isoformat(),
            'amfi_data': amfi_data,
            'fund_house_data': fund_house_data,
            'total_funds': len(amfi_data.get('funds', [])) + sum(len(data.get('funds', [])) for data in fund_house_data.values()),
            'sources_scraped': list(fund_house_data.keys()),
            'success': True
        }
        
        # Save scraped data
        output_dir = Path('data/scraped')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"latest_data_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Data saved to: {output_file}")
        logger.info(f"Total funds scraped: {all_data['total_funds']}")
        
        # Set GitHub Actions output
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'w') as f:
                f.write(f"success={all_data['success']}\n")
                f.write(f"count={all_data['total_funds']}\n")
        
        return all_data
        
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        
        # Set GitHub Actions output for failure
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'w') as f:
                f.write(f"success=false\n")
                f.write(f"error={str(e)}\n")
        
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get('success', False) else 1)
