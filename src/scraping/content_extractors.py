"""
Content Extractors for different types of web content and documents
"""

import requests
import logging
from typing import Dict, List, Optional, Union
from bs4 import BeautifulSoup, Tag
import PyPDF2
import pdfplumber
import pandas as pd
from io import BytesIO, StringIO
import re
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

@dataclass
class ExtractedContent:
    url: str
    content_type: str
    text_content: str
    structured_data: Optional[Dict] = None
    metadata: Optional[Dict] = None
    links: Optional[List[str]] = None
    tables: Optional[List[Dict]] = None
    extraction_timestamp: Optional[str] = None
    error: Optional[str] = None

class HTMLExtractor:
    """Extract content from HTML pages"""
    
    def __init__(self):
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
    
    def extract(self, url: str) -> ExtractedContent:
        """Extract content from HTML page"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            self._remove_unwanted_elements(soup)
            
            # Extract text content
            text_content = self._extract_text_content(soup)
            
            # Extract structured data
            structured_data = self._extract_structured_data(soup)
            
            # Extract metadata
            metadata = self._extract_metadata(soup, response)
            
            # Extract links
            links = self._extract_links(soup, url)
            
            # Extract tables
            tables = self._extract_tables(soup)
            
            return ExtractedContent(
                url=url,
                content_type="html",
                text_content=text_content,
                structured_data=structured_data,
                metadata=metadata,
                links=links,
                tables=tables
            )
            
        except Exception as e:
            self.logger.error(f"HTML extraction failed for {url}: {str(e)}")
            return ExtractedContent(
                url=url,
                content_type="html",
                text_content="",
                error=str(e)
            )
    
    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove navigation, ads, and other unwanted elements"""
        unwanted_selectors = [
            'nav', 'header', 'footer', 'aside',
            '.navigation', '.menu', '.ads', '.advertisement',
            '.cookie-banner', '.popup', '.modal',
            'script', 'style', 'noscript'
        ]
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
    
    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """Extract clean text content preserving structure"""
        # Get main content areas
        main_content = soup.find('main') or soup.find('div', class_=re.compile(r'content|main'))
        
        if not main_content:
            main_content = soup
        
        # Extract text with structure preservation
        text_parts = []
        
        # Process headings
        for heading in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            text_parts.append(f"\n{heading.name.upper()}: {heading.get_text().strip()}")
        
        # Process paragraphs
        for paragraph in main_content.find_all('p'):
            text = paragraph.get_text().strip()
            if text:
                text_parts.append(f"\n{text}")
        
        # Process lists
        for list_elem in main_content.find_all(['ul', 'ol']):
            list_items = []
            for li in list_elem.find_all('li'):
                item_text = li.get_text().strip()
                if item_text:
                    list_items.append(f"• {item_text}")
            
            if list_items:
                text_parts.append("\n" + "\n".join(list_items))
        
        return "\n".join(text_parts).strip()
    
    def _extract_structured_data(self, soup: BeautifulSoup) -> Dict:
        """Extract structured data from the page"""
        structured_data = {}
        
        # Extract JSON-LD data
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        if json_ld_scripts:
            structured_data['json_ld'] = []
            for script in json_ld_scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    structured_data['json_ld'].append(data)
                except:
                    pass
        
        # Extract meta tags
        meta_tags = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property')
            meta_content = meta.get('content')
            if name and meta_content:
                meta_tags[name] = meta_content
        
        if meta_tags:
            structured_data['meta_tags'] = meta_tags
        
        return structured_data
    
    def _extract_metadata(self, soup: BeautifulSoup, response: requests.Response) -> Dict:
        """Extract metadata from the page"""
        metadata = {}
        
        # Basic metadata
        metadata['title'] = soup.title.get_text().strip() if soup.title else ""
        metadata['url'] = response.url
        metadata['status_code'] = response.status_code
        metadata['content_type'] = response.headers.get('content-type', '')
        metadata['last_modified'] = response.headers.get('last-modified', '')
        
        # Extract specific mutual fund data
        fund_data = self._extract_fund_data(soup)
        metadata.update(fund_data)
        
        return metadata
    
    def _extract_fund_data(self, soup: BeautifulSoup) -> Dict:
        """Extract specific mutual fund information"""
        fund_data = {}
        
        # Common fund information patterns
        patterns = {
            'expense_ratio': r'expense\s*ratio[:\s]*([0-9.]+%?)',
            'exit_load': r'exit\s*load[:\s]*([0-9.]+%?)',
            'nav': r'nav[:\s]*₹?([0-9,.-]+)',
            'aum': r'aum[:\s]*₹?([0-9,.-]+\s*(?:cr|crore|lakh|thousand))',
            'risk_level': r'risk[:\s]*(low|moderate|high|very\s*high)',
            'category': r'category[:\s]*([a-z\s-]+)',
            'benchmark': r'benchmark[:\s]*([a-z\s&-]+)'
        }
        
        text_content = soup.get_text().lower()
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text_content)
            if match:
                fund_data[key] = match.group(1).strip()
        
        return fund_data
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all links from the page"""
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Convert relative URLs to absolute
            if href.startswith('/'):
                href = urljoin(base_url, href)
            elif not href.startswith(('http://', 'https://')):
                href = urljoin(base_url, href)
            
            # Filter relevant links
            if self._is_relevant_link(href):
                links.append(href)
        
        return list(set(links))  # Remove duplicates
    
    def _is_relevant_link(self, url: str) -> bool:
        """Check if link is relevant for mutual fund information"""
        relevant_patterns = [
            r'.*factsheet.*',
            r'.*sid.*',
            r'.*kim.*',
            r'.*performance.*',
            r'.*nav.*',
            r'.*portfolio.*'
        ]
        
        for pattern in relevant_patterns:
            if re.match(pattern, url.lower()):
                return True
        
        return False
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract tables from the page"""
        tables = []
        
        for table in soup.find_all('table'):
            try:
                # Convert table to DataFrame
                df = pd.read_html(StringIO(str(table)))[0]
                
                # Clean and process table data
                table_data = {
                    'headers': df.columns.tolist(),
                    'data': df.values.tolist(),
                    'title': table.get('title', ''),
                    'summary': self._summarize_table(df)
                }
                
                tables.append(table_data)
                
            except Exception as e:
                self.logger.warning(f"Failed to extract table: {str(e)}")
                continue
        
        return tables
    
    def _summarize_table(self, df: pd.DataFrame) -> str:
        """Generate a summary of table content"""
        if df.empty:
            return "Empty table"
        
        summary = f"Table with {len(df)} rows and {len(df.columns)} columns"
        
        # Try to identify table type based on headers
        headers = [col.lower() for col in df.columns]
        
        if any('nav' in header for header in headers):
            summary += " - NAV data"
        elif any('expense' in header for header in headers):
            summary += " - Expense information"
        elif any('holding' in header for header in headers):
            summary += " - Portfolio holdings"
        elif any('return' in header for header in headers):
            summary += " - Performance returns"
        
        return summary

class PDFExtractor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract(self, url: str, session: requests.Session) -> ExtractedContent:
        """Extract content from PDF document"""
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            
            pdf_content = BytesIO(response.content)
            
            # Try pdfplumber first (better for complex layouts)
            text_content = self._extract_with_pdfplumber(pdf_content)
            
            # Fallback to PyPDF2 if pdfplumber fails
            if not text_content:
                text_content = self._extract_with_pypdf2(pdf_content)
            
            # Extract structured data
            structured_data = self._extract_pdf_structured_data(text_content)
            
            # Extract metadata
            metadata = self._extract_pdf_metadata(pdf_content, response)
            
            return ExtractedContent(
                url=url,
                content_type="pdf",
                text_content=text_content,
                structured_data=structured_data,
                metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"PDF extraction failed for {url}: {str(e)}")
            return ExtractedContent(
                url=url,
                content_type="pdf",
                text_content="",
                error=str(e)
            )
    
    def _extract_with_pdfplumber(self, pdf_content: BytesIO) -> str:
        """Extract text using pdfplumber"""
        try:
            with pdfplumber.open(pdf_content) as pdf:
                text_parts = []
                
                for page in pdf.pages:
                    # Extract text
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                    
                    # Extract tables
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            # Convert table to readable text
                            table_text = self._table_to_text(table)
                            text_parts.append(table_text)
                
                return "\n".join(text_parts)
                
        except Exception as e:
            self.logger.warning(f"pdfplumber extraction failed: {str(e)}")
            return ""
    
    def _extract_with_pypdf2(self, pdf_content: BytesIO) -> str:
        """Extract text using PyPDF2 as fallback"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_content)
            text_parts = []
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            return "\n".join(text_parts)
            
        except Exception as e:
            self.logger.warning(f"PyPDF2 extraction failed: {str(e)}")
            return ""
    
    def _table_to_text(self, table: List[List[str]]) -> str:
        """Convert table data to readable text"""
        if not table:
            return ""
        
        text_parts = []
        
        # Add headers
        if table[0]:
            headers = " | ".join([cell.strip() if cell else "" for cell in table[0]])
            text_parts.append(f"TABLE: {headers}")
        
        # Add data rows
        for row in table[1:]:
            if row:
                row_text = " | ".join([cell.strip() if cell else "" for cell in row])
                text_parts.append(row_text)
        
        return "\n".join(text_parts)
    
    def _extract_pdf_structured_data(self, text_content: str) -> Dict:
        """Extract structured data from PDF text"""
        structured_data = {}
        
        # Extract key information patterns
        patterns = {
            'fund_name': r'Fund\s*Name[:\s]*([A-Za-z\s&-]+)',
            'expense_ratio': r'Expense\s*Ratio[:\s]*([0-9.]+%?)',
            'exit_load': r'Exit\s*Load[:\s]*([0-9.]+%?)',
            'riskometer': r'Riskometer[:\s]*(Very\s*High|High|Moderate|Low)',
            'benchmark': r'Benchmark[:\s]*([A-Za-z\s&-]+)',
            'min_investment': r'Minimum\s*Investment[:\s]*₹?([0-9,]+)',
            'sip_amount': r'SIP[:\s]*₹?([0-9,]+)'
        }
        
        for key, pattern in patterns.items():
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches:
                structured_data[key] = matches[0].strip()
        
        return structured_data
    
    def _extract_pdf_metadata(self, pdf_content: BytesIO, response: requests.Response) -> Dict:
        """Extract metadata from PDF"""
        metadata = {}
        
        # Basic response metadata
        metadata['url'] = response.url
        metadata['content_type'] = response.headers.get('content-type', '')
        metadata['content_length'] = len(response.content)
        
        try:
            # PDF metadata
            pdf_reader = PyPDF2.PdfReader(pdf_content)
            if pdf_reader.metadata:
                pdf_metadata = pdf_reader.metadata
                metadata.update({
                    'title': pdf_metadata.get('/Title', ''),
                    'author': pdf_metadata.get('/Author', ''),
                    'creator': pdf_metadata.get('/Creator', ''),
                    'producer': pdf_metadata.get('/Producer', ''),
                    'creation_date': str(pdf_metadata.get('/CreationDate', '')),
                    'modification_date': str(pdf_metadata.get('/ModDate', ''))
                })
            
            metadata['page_count'] = len(pdf_reader.pages)
            
        except Exception as e:
            self.logger.warning(f"Failed to extract PDF metadata: {str(e)}")
        
        return metadata

class ContentExtractorFactory:
    @staticmethod
    def create_extractor(content_type: str, document_type: str) -> Union[HTMLExtractor, PDFExtractor]:
        """Factory method to create appropriate extractor"""
        if content_type.lower() in ['html', 'text/html']:
            return HTMLExtractor()
        elif content_type.lower() in ['pdf', 'application/pdf']:
            return PDFExtractor()
        else:
            raise ValueError(f"Unsupported content type: {content_type}")
