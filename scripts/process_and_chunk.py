#!/usr/bin/env python3
"""
Process and Chunk Latest Data
Processes scraped data and creates optimized chunks for embedding
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from chunking.chunking_service import ChunkingService

def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Main processing function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting data processing and chunking...")
        
        # Load latest scraped data
        scraped_data_dir = Path('data/scraped')
        latest_files = sorted(scraped_data_dir.glob('latest_data_*.json'), reverse=True)
        
        if not latest_files:
            logger.error("No scraped data found")
            return {'success': False, 'error': 'No scraped data available'}
        
        latest_file = latest_files[0]
        logger.info(f"Loading scraped data from: {latest_file}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            scraped_data = json.load(f)
        
        # Initialize chunking service
        chunking_config = {
            'chunking': {
                'max_chunk_size': int(os.environ.get('MAX_CHUNK_SIZE', 500)),
                'min_chunk_size': int(os.environ.get('MIN_CHUNK_SIZE', 200)),
                'overlap_size': 50,
                'chunking_strategy': os.environ.get('CHUNK_STRATEGY', 'hybrid'),
                'preserve_structure': True
            }
        }
        
        chunking_service = ChunkingService(chunking_config)
        
        # Process AMFI data
        all_chunks = []
        chunk_count = 0
        
        if 'amfi_data' in scraped_data:
            logger.info("Processing AMFI fund data...")
            amfi_chunks = chunking_service.process_amfi_data(scraped_data['amfi_data'])
            all_chunks.extend(amfi_chunks)
            chunk_count += len(amfi_chunks)
        
        # Process fund house data
        if 'fund_house_data' in scraped_data:
            logger.info("Processing fund house data...")
            for fund_house, house_data in scraped_data['fund_house_data'].items():
                house_chunks = chunking_service.process_fund_house_data(house_data, fund_house)
                all_chunks.extend(house_chunks)
                chunk_count += len(house_chunks)
        
        logger.info(f"Total chunks created: {chunk_count}")
        
        # Save chunks
        output_dir = Path('data/chunks')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"chunks_{timestamp}.json"
        
        chunks_data = {
            'chunks': all_chunks,
            'metadata': {
                'total_chunks': chunk_count,
                'created_at': datetime.now().isoformat(),
                'source_file': str(latest_file),
                'chunking_config': chunking_config,
                'scraped_at': scraped_data.get('scraped_at'),
                'amfi_funds': len(scraped_data.get('amfi_data', {}).get('funds', [])),
                'fund_houses': len(scraped_data.get('fund_house_data', {}))
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Chunks saved to: {output_file}")
        
        # Set GitHub Actions output
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'w') as f:
                f.write(f"chunk_count={chunk_count}\n")
                f.write(f"output_file={output_file}\n")
        
        return {
            'success': True,
            'chunk_count': chunk_count,
            'output_file': str(output_file),
            'amfi_funds': len(scraped_data.get('amfi_data', {}).get('funds', [])),
            'fund_houses': len(scraped_data.get('fund_house_data', {}))
        }
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        
        # Set GitHub Actions output for failure
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'w') as f:
                f.write(f"chunk_count=0\n")
                f.write(f"error={str(e)}\n")
        
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    import os
    result = main()
    sys.exit(0 if result.get('success', False) else 1)
