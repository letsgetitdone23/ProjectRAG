"""
URL Manager for handling URL validation, accessibility checks, and rate limiting
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

@dataclass
class URLInfo:
    url: str
    document_type: str
    scheme_name: str
    source_category: str
    content_type: str = 'html'
    last_checked: Optional[float] = None
    is_accessible: bool = False
    response_time: Optional[float] = None
    status_code: Optional[int] = None

class URLManager:
    def __init__(self, config: Dict):
        self.config = config
        self.session = self._create_session()
        self.logger = logging.getLogger(__name__)
        self.urls = self._initialize_urls()
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy and rate limiting"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        return session
    
    def _initialize_urls(self) -> List[URLInfo]:
        """Initialize URLs from configuration"""
        urls = []
        
        # AMC Primary Sources
        urls.extend([
            URLInfo(
                url="https://groww.in/mutual-funds/amc/nippon-india-mutual-funds",
                document_type="amc_page",
                scheme_name="Nippon India Mutual Funds",
                source_category="groww_aggregator",
                content_type="html"
            ),
            URLInfo(
                url="https://groww.in/mutual-funds/nippon-india-large-cap-fund-direct-growth",
                document_type="scheme_page",
                scheme_name="Large Cap Fund",
                source_category="groww_aggregator",
                content_type="html"
            ),
            URLInfo(
                url="https://groww.in/mutual-funds/nippon-india-flexi-cap-fund-direct-growth",
                document_type="scheme_page",
                scheme_name="Flexi Cap Fund",
                source_category="groww_aggregator",
                content_type="html"
            ),
            URLInfo(
                url="https://groww.in/mutual-funds/nippon-india-multi-asset-allocation-fund-direct-growth",
                document_type="scheme_page",
                scheme_name="Multi Asset Allocation Fund",
                source_category="groww_aggregator",
                content_type="html"
            ),
            
            # Official AMC Documents
            URLInfo(
                url="https://mf.nipponindiaim.com/InvestorServices/SIDEquity/NipponIndia-Large-Cap-Fund.pdf",
                document_type="sid",
                scheme_name="Large Cap Fund",
                source_category="amc_official",
                content_type="pdf"
            ),
            URLInfo(
                url="https://mf.nipponindiaim.com/campaigns/NipponIndiaFlexiCapFund/pdf/Nippon-India-Flexicap-Fund-SID.pdf",
                document_type="sid",
                scheme_name="Flexi Cap Fund",
                source_category="amc_official",
                content_type="pdf"
            ),
            URLInfo(
                url="https://mf.nipponindiaim.com/InvestorServices/SIDEquity/SID-NipponIndia-Multi-Asset-Allocation-Fund.pdf",
                document_type="sid",
                scheme_name="Multi Asset Allocation Fund",
                source_category="amc_official",
                content_type="pdf"
            ),
            
            # Performance Pages
            URLInfo(
                url="https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Large-Cap-Fund.aspx",
                document_type="performance_page",
                scheme_name="Large Cap Fund",
                source_category="amc_official",
                content_type="html"
            ),
            URLInfo(
                url="https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Flexi-Cap-Fund.aspx",
                document_type="performance_page",
                scheme_name="Flexi Cap Fund",
                source_category="amc_official",
                content_type="html"
            ),
            URLInfo(
                url="https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Multi-Asset-Allocation-Fund.aspx",
                document_type="performance_page",
                scheme_name="Multi Asset Allocation Fund",
                source_category="amc_official",
                content_type="html"
            ),
            
            # Regulatory Sources
            URLInfo(
                url="https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doGetFundDetails=yes&mfId=46&type=2",
                document_type="regulatory_data",
                scheme_name="Nippon India Mutual Funds",
                source_category="regulatory",
                content_type="html"
            ),
            URLInfo(
                url="https://www.amfiindia.com/otherdata/fund-performance",
                document_type="performance_data",
                scheme_name="Nippon India Mutual Funds",
                source_category="regulatory",
                content_type="html"
            )
        ])
        
        return urls
    
    def validate_url(self, url_info: URLInfo) -> bool:
        """Check if URL is accessible and get metadata"""
        try:
            start_time = time.time()
            
            # Use HEAD request first to check accessibility
            response = self.session.head(url_info.url, timeout=30)
            
            if response.status_code == 405:  # Method not allowed, try GET
                response = self.session.get(url_info.url, timeout=30, stream=True)
                response.close()
            
            end_time = time.time()
            
            # Update URL info
            url_info.last_checked = time.time()
            url_info.is_accessible = response.status_code == 200
            url_info.response_time = end_time - start_time
            url_info.status_code = response.status_code
            
            self.logger.info(f"URL validation: {url_info.url} - Status: {response.status_code}, Time: {url_info.response_time:.2f}s")
            
            return url_info.is_accessible
            
        except requests.exceptions.RequestException as e:
            url_info.last_checked = time.time()
            url_info.is_accessible = False
            url_info.response_time = None
            url_info.status_code = None
            
            self.logger.error(f"URL validation failed for {url_info.url}: {str(e)}")
            return False
    
    def validate_all_urls(self) -> Dict[str, List[URLInfo]]:
        """Validate all URLs and return categorized results"""
        results = {
            'accessible': [],
            'inaccessible': [],
            'errors': []
        }
        
        for url_info in self.urls:
            if self.validate_url(url_info):
                if url_info.is_accessible:
                    results['accessible'].append(url_info)
                else:
                    results['inaccessible'].append(url_info)
            else:
                results['errors'].append(url_info)
        
        return results
    
    def get_accessible_urls(self, scheme_name: Optional[str] = None, document_type: Optional[str] = None) -> List[URLInfo]:
        """Get list of accessible URLs, optionally filtered"""
        accessible_urls = [url for url in self.urls if url.is_accessible]
        
        if scheme_name:
            accessible_urls = [url for url in accessible_urls if url.scheme_name == scheme_name]
        
        if document_type:
            accessible_urls = [url for url in accessible_urls if url.document_type == document_type]
        
        return accessible_urls
    
    def get_url_by_scheme_and_type(self, scheme_name: str, document_type: str) -> Optional[URLInfo]:
        """Get specific URL by scheme name and document type"""
        for url_info in self.urls:
            if url_info.scheme_name == scheme_name and url_info.document_type == document_type:
                return url_info
        return None
    
    def rate_limit_delay(self, domain: str) -> None:
        """Apply rate limiting based on domain"""
        domain_configs = {
            'groww.in': 2.0,  # 2 seconds between requests
            'nipponindiaim.com': 1.5,  # 1.5 seconds between requests
            'sebi.gov.in': 3.0,  # 3 seconds between requests
            'amfiindia.com': 2.5  # 2.5 seconds between requests
        }
        
        delay = domain_configs.get(domain, 1.0)
        time.sleep(delay)
    
    def get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def close(self):
        """Close the session"""
        if self.session:
            self.session.close()
