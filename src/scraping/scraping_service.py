"""
Main Scraping Service that orchestrates the data collection process
"""

import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import requests

from .url_manager import URLManager, URLInfo
from .content_extractors import ContentExtractorFactory, ExtractedContent

class ScrapingService:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.url_manager = URLManager(config)
        self.session = self._create_session()
        self.output_dir = Path(config.get('output_dir', 'data/raw'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def _create_session(self) -> requests.Session:
        """Create HTTP session with proper configuration"""
        session = requests.Session()
        
        # Configure session
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        return session
    
    def run_full_scraping(self, force_update: bool = False, specific_scheme: Optional[str] = None) -> Dict:
        """Run complete scraping process for all URLs"""
        self.logger.info("Starting full scraping process")
        
        # Validate all URLs
        validation_results = self.url_manager.validate_all_urls()
        
        if not validation_results['accessible']:
            raise Exception("No accessible URLs found")
        
        # Filter URLs based on parameters
        urls_to_scrape = self._filter_urls(validation_results['accessible'], force_update, specific_scheme)
        
        if not urls_to_scrape:
            self.logger.warning("No URLs to scrape after filtering")
            return {'scraped': [], 'failed': [], 'skipped': validation_results['accessible']}
        
        # Scrape each URL
        scraped_data = []
        failed_urls = []
        
        for url_info in urls_to_scrape:
            try:
                # Apply rate limiting
                domain = self.url_manager.get_domain_from_url(url_info.url)
                self.url_manager.rate_limit_delay(domain)
                
                # Scrape content
                content = self._scrape_single_url(url_info)
                
                if content.error:
                    failed_urls.append({'url': url_info.url, 'error': content.error})
                else:
                    scraped_data.append(content)
                    self.logger.info(f"Successfully scraped: {url_info.url}")
                    
            except Exception as e:
                self.logger.error(f"Failed to scrape {url_info.url}: {str(e)}")
                failed_urls.append({'url': url_info.url, 'error': str(e)})
        
        # Save results
        self._save_scraping_results(scraped_data, failed_urls)
        
        results = {
            'scraped': scraped_data,
            'failed': failed_urls,
            'skipped': [url for url in validation_results['accessible'] if url not in urls_to_scrape],
            'timestamp': datetime.now().isoformat(),
            'total_scraped': len(scraped_data),
            'total_failed': len(failed_urls)
        }
        
        self.logger.info(f"Scraping completed: {len(scraped_data)} successful, {len(failed_urls)} failed")
        return results
    
    def _filter_urls(self, accessible_urls: List[URLInfo], force_update: bool, specific_scheme: Optional[str]) -> List[URLInfo]:
        """Filter URLs based on update requirements"""
        urls_to_scrape = []
        
        for url_info in accessible_urls:
            # Filter by specific scheme if provided
            if specific_scheme and url_info.scheme_name != specific_scheme:
                continue
            
            # Check if update is needed
            if force_update or self._needs_update(url_info):
                urls_to_scrape.append(url_info)
        
        return urls_to_scrape
    
    def _needs_update(self, url_info: URLInfo) -> bool:
        """Check if URL needs to be updated based on last scrape time"""
        # Check if we have existing data
        output_file = self._get_output_filename(url_info)
        
        if not output_file.exists():
            return True
        
        # Check file modification time
        file_mtime = output_file.stat().st_mtime
        current_time = time.time()
        
        # Update if file is older than 24 hours
        return (current_time - file_mtime) > (24 * 60 * 60)
    
    def _scrape_single_url(self, url_info: URLInfo) -> ExtractedContent:
        """Scrape content from a single URL"""
        try:
            # Determine content type
            content_type = self._determine_content_type(url_info.url)
            
            # Create appropriate extractor
            extractor = ContentExtractorFactory.create_extractor(url_info.content_type, url_info.document_type)
        
            # Handle PDF extraction with session parameter
            if url_info.content_type == 'pdf':
                # Skip PDFs for now to get HTML working
                self.logger.info(f"Skipping PDF: {url_info.url}")
                # Return empty content instead of None
                from .content_extractors import ExtractedContent
                return ExtractedContent(
                    url=url_info.url,
                    content_type="pdf",
                    text_content="",
                    structured_data={},
                    metadata={'skipped': True},
                    extraction_timestamp=datetime.now().isoformat()
                )
            else:
                extracted_content = extractor.extract(url_info.url)
            
            # Add URL metadata
            extracted_content.metadata = extracted_content.metadata or {}
            extracted_content.metadata.update({
                'scheme_name': url_info.scheme_name,
                'document_type': url_info.document_type,
                'source_category': url_info.source_category,
                'scraped_at': datetime.now().isoformat(),
                'url_info': {
                    'url': url_info.url,
                    'document_type': url_info.document_type,
                    'scheme_name': url_info.scheme_name,
                    'source_category': url_info.source_category
                }
            })
            
            return content
            
        except Exception as e:
            self.logger.error(f"Error scraping {url_info.url}: {str(e)}")
            return ExtractedContent(
                url=url_info.url,
                content_type="unknown",
                text_content="",
                error=str(e)
            )
    
    def _determine_content_type(self, url: str) -> str:
        """Determine content type from URL"""
        if url.endswith('.pdf'):
            return 'pdf'
        else:
            return 'html'
    
    def _get_output_filename(self, url_info: URLInfo) -> Path:
        """Generate output filename for scraped content"""
        # Create safe filename
        scheme_name = url_info.scheme_name.replace(' ', '_').replace('&', 'and')
        doc_type = url_info.document_type.replace(' ', '_')
        
        # Use URL hash to ensure uniqueness
        import hashlib
        url_hash = hashlib.md5(url_info.url.encode()).hexdigest()[:8]
        
        filename = f"{scheme_name}_{doc_type}_{url_hash}.json"
        return self.output_dir / filename
    
    def _save_scraping_results(self, scraped_data: List[ExtractedContent], failed_urls: List[Dict]) -> None:
        """Save scraping results to files"""
        # Save successful scrapes
        for content in scraped_data:
            url_info = content.metadata.get('url_info', {})
            filename = self._get_output_filename(URLInfo(
                url=content.url,
                document_type=url_info.get('document_type', 'unknown'),
                scheme_name=url_info.get('scheme_name', 'unknown'),
                source_category=url_info.get('source_category', 'unknown')
            ))
            
            # Convert ExtractedContent to dict for JSON serialization
            import dataclasses
            content_dict = dataclasses.asdict(content)
            
            # Convert URLInfo in metadata to dict
            if 'url_info' in content_dict['metadata']:
                url_info = content_dict['metadata']['url_info']
                if hasattr(url_info, 'url'):  # Check if it's a URLInfo object
                    content_dict['metadata']['url_info'] = {
                        'url': url_info.url,
                        'document_type': url_info.document_type,
                        'scheme_name': url_info.scheme_name,
                        'source_category': url_info.source_category,
                        'content_type': getattr(url_info, 'content_type', 'html')
                    }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(content_dict, f, indent=2, ensure_ascii=False)
        
        # Save summary
        summary_file = self.output_dir / f"scraping_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary = {
            'timestamp': datetime.now().isoformat(),
            'scraped_count': len(scraped_data),
            'failed_count': len(failed_urls),
            'scraped_urls': [content.url for content in scraped_data],
            'failed_urls': [item['url'] for item in failed_urls]
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
    
    def get_scraping_status(self) -> Dict:
        """Get current scraping status and statistics"""
        # Count files in output directory
        json_files = list(self.output_dir.glob('*.json'))
        
        # Parse recent files for statistics
        recent_files = [f for f in json_files if 'summary' in f.name]
        recent_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        status = {
            'total_files': len(json_files),
            'output_directory': str(self.output_dir),
            'last_scrape': None,
            'url_validation': self.url_manager.validate_all_urls()
        }
        
        if recent_files:
            try:
                with open(recent_files[0], 'r') as f:
                    summary = json.load(f)
                    status['last_scrape'] = summary.get('timestamp')
                    status['last_scrape_count'] = summary.get('scraped_count', 0)
                    status['last_failed_count'] = summary.get('failed_count', 0)
            except:
                pass
        
        return status
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """Clean up old scraped data files"""
        current_time = time.time()
        cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)
        
        cleaned_files = []
        
        for file_path in self.output_dir.glob('*.json'):
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    cleaned_files.append(str(file_path))
                except Exception as e:
                    self.logger.warning(f"Failed to delete old file {file_path}: {str(e)}")
        
        if cleaned_files:
            self.logger.info(f"Cleaned up {len(cleaned_files)} old files")
        
        return cleaned_files
    
    def close(self):
        """Clean up resources"""
        if self.url_manager:
            self.url_manager.close()
        if self.session:
            self.session.close()
