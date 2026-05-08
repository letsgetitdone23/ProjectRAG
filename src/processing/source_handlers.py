"""
Source-Specific Handlers for different types of websites and document structures
"""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import json

@dataclass
class ProcessedData:
    content: str
    structured_data: Dict
    metadata: Dict
    tables: List[Dict]
    quality_indicators: Dict

class AMCPageHandler:
    """Handler for AMC official pages with dynamic content"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process(self, content: Dict) -> ProcessedData:
        """Process AMC official page content"""
        text_content = content.get('text_content', '')
        structured_data = content.get('structured_data', {})
        metadata = content.get('metadata', {})
        tables = content.get('tables', [])
        
        # Extract specific AMC information
        amc_data = self._extract_amc_specific_data(text_content, metadata)
        
        # Process tables for fund information
        processed_tables = self._process_fund_tables(tables)
        
        # Extract fund performance data
        performance_data = self._extract_performance_data(text_content, tables)
        
        # Combine all structured data
        combined_structured = {
            **structured_data,
            **amc_data,
            'performance_data': performance_data,
            'source_type': 'amc_official'
        }
        
        # Quality indicators
        quality = self._assess_quality(text_content, combined_structured)
        
        return ProcessedData(
            content=text_content,
            structured_data=combined_structured,
            metadata=metadata,
            tables=processed_tables,
            quality_indicators=quality
        )
    
    def _extract_amc_specific_data(self, text: str, metadata: Dict) -> Dict:
        """Extract AMC-specific information"""
        data = {}
        
        # Extract fund information patterns
        patterns = {
            'fund_manager': r'Fund\s*Manager[:\s]*([A-Za-z\s\.]+)',
            'inception_date': r'Inception\s*Date[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})',
            'fund_type': r'Fund\s*Type[:\s]*([A-Za-z\s-]+)',
            'investment_objective': r'Investment\s*Objective[:\s]*([^.]+)',
            'asset_allocation': r'Asset\s*Allocation[:\s]*([^.]+)',
            'benchmark_index': r'Benchmark[:\s]*([A-Za-z\s&-]+)',
            'riskometer': r'Riskometer[:\s]*(Very\s*High|High|Moderate|Low)',
            'category': r'Category[:\s]*([A-Za-z\s-]+)',
            'plan_type': r'Plan\s*Type[:\s]*([A-Za-z\s-]+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data[key] = match.group(1).strip()
        
        return data
    
    def _process_fund_tables(self, tables: List[Dict]) -> List[Dict]:
        """Process and enhance fund information tables"""
        processed_tables = []
        
        for table in tables:
            processed_table = table.copy()
            
            # Identify table type
            table_type = self._identify_table_type(table)
            processed_table['table_type'] = table_type
            
            # Extract key metrics based on table type
            if table_type == 'performance':
                metrics = self._extract_performance_metrics(table)
                processed_table['key_metrics'] = metrics
            elif table_type == 'portfolio':
                holdings = self._extract_portfolio_holdings(table)
                processed_table['holdings'] = holdings
            elif table_type == 'expense':
                expense_info = self._extract_expense_info(table)
                processed_table['expense_info'] = expense_info
            
            processed_tables.append(processed_table)
        
        return processed_tables
    
    def _identify_table_type(self, table: Dict) -> str:
        """Identify the type of information in the table"""
        headers = [h.lower() for h in table.get('headers', [])]
        
        if any('return' in h or 'performance' in h for h in headers):
            return 'performance'
        elif any('holding' in h or 'portfolio' in h or 'security' in h for h in headers):
            return 'portfolio'
        elif any('expense' in h or 'ratio' in h or 'load' in h for h in headers):
            return 'expense'
        elif any('nav' in h for h in headers):
            return 'nav'
        else:
            return 'general'
    
    def _extract_performance_metrics(self, table: Dict) -> Dict:
        """Extract performance metrics from table"""
        metrics = {}
        data = table.get('data', [])
        headers = table.get('headers', [])
        
        # Look for common performance periods
        for row in data:
            if len(row) > 1:
                period = str(row[0]).lower()
                value = str(row[1]) if len(row) > 1 else ''
                
                if any(keyword in period for keyword in ['1 year', '1yr', 'annual']):
                    metrics['1_year_return'] = value
                elif any(keyword in period for keyword in ['3 year', '3yr']):
                    metrics['3_year_return'] = value
                elif any(keyword in period for keyword in ['5 year', '5yr']):
                    metrics['5_year_return'] = value
                elif any(keyword in period for keyword in ['since inception', 'inception']):
                    metrics['inception_return'] = value
        
        return metrics
    
    def _extract_portfolio_holdings(self, table: Dict) -> List[Dict]:
        """Extract portfolio holdings from table"""
        holdings = []
        data = table.get('data', [])
        headers = table.get('headers', [])
        
        # Find column indices
        name_col = next((i for i, h in enumerate(headers) if 'name' in h.lower() or 'security' in h.lower()), 0)
        percentage_col = next((i for i, h in enumerate(headers) if '%' in h or 'allocation' in h.lower()), 1)
        
        for row in data:
            if len(row) > max(name_col, percentage_col):
                holding = {
                    'name': str(row[name_col]).strip(),
                    'percentage': str(row[percentage_col]).strip()
                }
                holdings.append(holding)
        
        return holdings[:10]  # Return top 10 holdings
    
    def _extract_expense_info(self, table: Dict) -> Dict:
        """Extract expense information from table"""
        expense_info = {}
        data = table.get('data', [])
        headers = table.get('headers', [])
        
        for row in data:
            if len(row) > 1:
                metric = str(row[0]).lower()
                value = str(row[1]) if len(row) > 1 else ''
                
                if 'expense' in metric or 'ratio' in metric:
                    expense_info['expense_ratio'] = value
                elif 'exit' in metric and 'load' in metric:
                    expense_info['exit_load'] = value
                elif 'entry' in metric and 'load' in metric:
                    expense_info['entry_load'] = value
        
        return expense_info
    
    def _extract_performance_data(self, text: str, tables: List[Dict]) -> Dict:
        """Extract performance data from text and tables"""
        performance_data = {}
        
        # Extract NAV information
        nav_pattern = r'NAV[:\s]*₹?([0-9,.-]+)'
        nav_match = re.search(nav_pattern, text)
        if nav_match:
            performance_data['current_nav'] = nav_match.group(1)
        
        # Extract performance numbers from text
        performance_patterns = {
            '1_year_return': r'1\s*year[:\s]*([0-9.]+%?)',
            '3_year_return': r'3\s*year[:\s]*([0-9.]+%?)',
            '5_year_return': r'5\s*year[:\s]*([0-9.]+%?)',
            'annualized_return': r'annualized[:\s]*([0-9.]+%?)'
        }
        
        for key, pattern in performance_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                performance_data[key] = match.group(1)
        
        return performance_data
    
    def _assess_quality(self, content: str, structured_data: Dict) -> Dict:
        """Assess quality of processed data"""
        quality = {
            'completeness_score': 0.0,
            'data_richness': 0.0,
            'freshness_indicators': []
        }
        
        # Check for key information
        key_fields = ['fund_manager', 'expense_ratio', 'nav', 'benchmark_index', 'riskometer']
        found_fields = sum(1 for field in key_fields if field in structured_data)
        quality['completeness_score'] = found_fields / len(key_fields)
        
        # Check data richness
        data_points = len(structured_data) + len(content.split())
        quality['data_richness'] = min(1.0, data_points / 1000)  # Normalize
        
        # Check for freshness indicators
        freshness_patterns = [
            r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b',  # Dates
            r'\bNAV\s*as\s*on\b',  # NAV dates
            r'\bupdated\s*on\b'
        ]
        
        for pattern in freshness_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                quality['freshness_indicators'].append(pattern)
        
        return quality

class PDFDocumentHandler:
    """Handler for PDF documents (SIDs, KIMs, etc.)"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process(self, content: Dict) -> ProcessedData:
        """Process PDF document content"""
        text_content = content.get('text_content', '')
        structured_data = content.get('structured_data', {})
        metadata = content.get('metadata', {})
        
        # Extract document-specific information
        doc_data = self._extract_document_data(text_content, metadata)
        
        # Extract scheme information
        scheme_data = self._extract_scheme_information(text_content)
        
        # Extract legal and compliance information
        compliance_data = self._extract_compliance_data(text_content)
        
        # Process tables from PDF
        processed_tables = self._process_pdf_tables(content.get('tables', []))
        
        # Combine structured data
        combined_structured = {
            **structured_data,
            **doc_data,
            **scheme_data,
            **compliance_data,
            'source_type': 'pdf_document'
        }
        
        # Quality assessment
        quality = self._assess_pdf_quality(text_content, combined_structured)
        
        return ProcessedData(
            content=text_content,
            structured_data=combined_structured,
            metadata=metadata,
            tables=processed_tables,
            quality_indicators=quality
        )
    
    def _extract_document_data(self, text: str, metadata: Dict) -> Dict:
        """Extract document metadata"""
        data = {}
        
        # Document type identification
        if 'scheme information document' in text.lower() or 'sid' in text.lower():
            data['document_type'] = 'SID'
        elif 'key information memorandum' in text.lower() or 'kim' in text.lower():
            data['document_type'] = 'KIM'
        elif 'factsheet' in text.lower():
            data['document_type'] = 'Factsheet'
        else:
            data['document_type'] = 'Unknown'
        
        # Extract document dates
        date_patterns = {
            'issue_date': r'Issue\s*Date[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})',
            'effective_date': r'Effective\s*Date[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})',
            'last_updated': r'Last\s*Updated[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})'
        }
        
        for key, pattern in date_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data[key] = match.group(1)
        
        return data
    
    def _extract_scheme_information(self, text: str) -> Dict:
        """Extract scheme-specific information"""
        data = {}
        
        # Scheme details
        scheme_patterns = {
            'scheme_name': r'Scheme\s*Name[:\s]*([A-Za-z0-9\s&-]+)',
            'option_type': r'Option[:\s]*([A-Za-z\s-]+)',
            'plan_type': r'Plan[:\s]*([A-Za-z\s-]+)',
            'nfo_open': r'NFO\s*Opens?[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})',
            'nfo_closes': r'NFO\s*Closes?[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})',
            'minimum_application_amount': r'Minimum\s*Application\s*Amount[:\s]*₹?([0-9,]+)',
            'additional_purchase_amount': r'Additional\s*Purchase\s*Amount[:\s]*₹?([0-9,]+)',
            'minimum_sip_amount': r'Minimum\s*SIP\s*Amount[:\s]*₹?([0-9,]+)',
            'sip_frequency': r'SIP\s*Frequency[:\s]*([A-Za-z\s-]+)'
        }
        
        for key, pattern in scheme_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data[key] = match.group(1).strip()
        
        return data
    
    def _extract_compliance_data(self, text: str) -> Dict:
        """Extract compliance and regulatory information"""
        data = {}
        
        # Risk factors
        risk_section_match = re.search(r'Risk\s*Factors[:\s]*(.*?)(?=\n\n|\n[A-Z])', text, re.DOTALL | re.IGNORECASE)
        if risk_section_match:
            data['risk_factors'] = risk_section_match.group(1).strip()[:500]  # Limit length
        
        # Compliance information
        compliance_patterns = {
            'ar_n': r'AR\s*N[:\s]*([A-Z0-9/]+)',
            'ria_code': r'RIA\s*Code[:\s]*([A-Z0-9]+)',
            'arn': r'ARN[:\s]*([A-Z0-9]+)',
            'sebi_registration': r'SEBI\s*Registration[:\s]*([A-Z0-9/]+)'
        }
        
        for key, pattern in compliance_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data[key] = match.group(1)
        
        return data
    
    def _process_pdf_tables(self, tables: List[Dict]) -> List[Dict]:
        """Process tables extracted from PDF"""
        processed_tables = []
        
        for table in tables:
            processed_table = table.copy()
            
            # Clean table data (PDF extraction can be messy)
            cleaned_data = []
            for row in table.get('data', []):
                cleaned_row = [str(cell).strip() for cell in row if cell and str(cell).strip()]
                if cleaned_row:
                    cleaned_data.append(cleaned_row)
            
            processed_table['data'] = cleaned_data
            processed_table['table_type'] = self._identify_pdf_table_type(cleaned_data, table.get('headers', []))
            
            processed_tables.append(processed_table)
        
        return processed_tables
    
    def _identify_pdf_table_type(self, data: List[List[str]], headers: List[str]) -> str:
        """Identify PDF table type"""
        if not data or not headers:
            return 'unknown'
        
        header_text = ' '.join(headers).lower()
        
        if any(keyword in header_text for keyword in ['expense', 'ratio', 'load']):
            return 'expense'
        elif any(keyword in header_text for keyword in ['return', 'performance']):
            return 'performance'
        elif any(keyword in header_text for keyword in ['holding', 'portfolio', 'allocation']):
            return 'portfolio'
        elif any(keyword in header_text for keyword in ['nav', 'net asset']):
            return 'nav'
        else:
            return 'general'
    
    def _assess_pdf_quality(self, content: str, structured_data: Dict) -> Dict:
        """Assess quality of PDF processing"""
        quality = {
            'text_clarity': 0.0,
            'structure_completeness': 0.0,
            'information_density': 0.0
        }
        
        # Text clarity (check for extraction artifacts)
        artifact_patterns = [r'\s{3,}', r'[^a-zA-Z0-9\s.,;:!?%&₹()-]{2,}']
        artifact_count = sum(len(re.findall(pattern, content)) for pattern in artifact_patterns)
        quality['text_clarity'] = max(0.0, 1.0 - (artifact_count / 100))
        
        # Structure completeness
        key_sections = ['scheme_name', 'document_type', 'expense_ratio', 'risk_factors']
        found_sections = sum(1 for section in key_sections if section in structured_data)
        quality['structure_completeness'] = found_sections / len(key_sections)
        
        # Information density
        word_count = len(content.split())
        quality['information_density'] = min(1.0, word_count / 2000)  # Normalize
        
        return quality

class PerformancePageHandler:
    """Handler for performance pages with tabular data and charts"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process(self, content: Dict) -> ProcessedData:
        """Process performance page content"""
        text_content = content.get('text_content', '')
        structured_data = content.get('structured_data', {})
        metadata = content.get('metadata', {})
        tables = content.get('tables', [])
        
        # Extract performance metrics
        performance_data = self._extract_comprehensive_performance(text_content, tables)
        
        # Process performance tables
        processed_tables = self._process_performance_tables(tables)
        
        # Extract benchmark information
        benchmark_data = self._extract_benchmark_data(text_content)
        
        # Combine structured data
        combined_structured = {
            **structured_data,
            **performance_data,
            **benchmark_data,
            'source_type': 'performance_page'
        }
        
        # Quality assessment
        quality = self._assess_performance_quality(text_content, combined_structured)
        
        return ProcessedData(
            content=text_content,
            structured_data=combined_structured,
            metadata=metadata,
            tables=processed_tables,
            quality_indicators=quality
        )
    
    def _extract_comprehensive_performance(self, text: str, tables: List[Dict]) -> Dict:
        """Extract comprehensive performance data"""
        performance_data = {}
        
        # Extract current NAV
        nav_pattern = r'NAV[:\s]*₹?([0-9,.-]+)'
        nav_match = re.search(nav_pattern, text, re.IGNORECASE)
        if nav_match:
            performance_data['current_nav'] = nav_match.group(1)
        
        # Extract NAV date
        nav_date_pattern = r'NAV\s*as\s*on[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})'
        nav_date_match = re.search(nav_date_pattern, text, re.IGNORECASE)
        if nav_date_match:
            performance_data['nav_date'] = nav_date_match.group(1)
        
        # Extract returns from text
        return_patterns = {
            '1_month_return': r'1\s*month[:\s]*([0-9.]+%?)',
            '3_month_return': r'3\s*month[:\s]*([0-9.]+%?)',
            '6_month_return': r'6\s*month[:\s]*([0-9.]+%?)',
            '1_year_return': r'1\s*year[:\s]*([0-9.]+%?)',
            '3_year_return': r'3\s*year[:\s]*([0-9.]+%?)',
            '5_year_return': r'5\s*year[:\s]*([0-9.]+%?)',
            '10_year_return': r'10\s*year[:\s]*([0-9.]+%?)',
            'since_inception': r'since\s*inception[:\s]*([0-9.]+%?)'
        }
        
        for key, pattern in return_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                performance_data[key] = match.group(1)
        
        return performance_data
    
    def _process_performance_tables(self, tables: List[Dict]) -> List[Dict]:
        """Process performance-specific tables"""
        processed_tables = []
        
        for table in tables:
            processed_table = table.copy()
            
            # Identify and process performance table
            if self._is_performance_table(table):
                performance_metrics = self._extract_table_performance_metrics(table)
                processed_table['performance_metrics'] = performance_metrics
                processed_table['table_type'] = 'performance_detailed'
            else:
                processed_table['table_type'] = 'general'
            
            processed_tables.append(processed_table)
        
        return processed_tables
    
    def _is_performance_table(self, table: Dict) -> bool:
        """Check if table contains performance data"""
        headers = [h.lower() for h in table.get('headers', [])]
        data = table.get('data', [])
        
        # Check headers
        performance_keywords = ['return', 'performance', 'year', 'period', 'nav', 'growth']
        if any(keyword in ' '.join(headers) for keyword in performance_keywords):
            return True
        
        # Check data content
        if data:
            first_row = ' '.join(str(cell) for cell in data[0]).lower()
            return any(keyword in first_row for keyword in performance_keywords)
        
        return False
    
    def _extract_table_performance_metrics(self, table: Dict) -> Dict:
        """Extract detailed performance metrics from table"""
        metrics = {}
        data = table.get('data', [])
        headers = table.get('headers', [])
        
        for row in data:
            if len(row) >= 2:
                period = str(row[0]).lower().strip()
                value = str(row[1]).strip()
                
                # Map various period formats to standard keys
                if '1 month' in period or '1m' in period:
                    metrics['1_month_return'] = value
                elif '3 month' in period or '3m' in period:
                    metrics['3_month_return'] = value
                elif '6 month' in period or '6m' in period:
                    metrics['6_month_return'] = value
                elif '1 year' in period or '1y' in period or 'annual' in period:
                    metrics['1_year_return'] = value
                elif '3 year' in period or '3y' in period:
                    metrics['3_year_return'] = value
                elif '5 year' in period or '5y' in period:
                    metrics['5_year_return'] = value
                elif 'inception' in period:
                    metrics['since_inception'] = value
        
        return metrics
    
    def _extract_benchmark_data(self, text: str) -> Dict:
        """Extract benchmark information"""
        benchmark_data = {}
        
        # Benchmark name
        benchmark_pattern = r'Benchmark[:\s]*([A-Za-z\s&-]+)'
        benchmark_match = re.search(benchmark_pattern, text, re.IGNORECASE)
        if benchmark_match:
            benchmark_data['benchmark_name'] = benchmark_match.group(1).strip()
        
        # Benchmark returns
        benchmark_return_patterns = {
            'benchmark_1_year': r'Benchmark.*1\s*year[:\s]*([0-9.]+%?)',
            'benchmark_3_year': r'Benchmark.*3\s*year[:\s]*([0-9.]+%?)',
            'benchmark_5_year': r'Benchmark.*5\s*year[:\s]*([0-9.]+%?)'
        }
        
        for key, pattern in benchmark_return_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                benchmark_data[key] = match.group(1)
        
        return benchmark_data
    
    def _assess_performance_quality(self, content: str, structured_data: Dict) -> Dict:
        """Assess quality of performance data"""
        quality = {
            'data_freshness': 0.0,
            'completeness': 0.0,
            'accuracy_indicators': []
        }
        
        # Check for recent data
        if 'nav_date' in structured_data:
            quality['data_freshness'] = 1.0
            quality['accuracy_indicators'].append('Recent NAV data available')
        
        # Check performance completeness
        performance_periods = ['1_month_return', '3_month_return', '1_year_return', '3_year_return', '5_year_return']
        found_periods = sum(1 for period in performance_periods if period in structured_data)
        quality['completeness'] = found_periods / len(performance_periods)
        
        # Check for benchmark comparison
        if 'benchmark_name' in structured_data:
            quality['accuracy_indicators'].append('Benchmark data available')
        
        return quality

class SourceHandlerFactory:
    """Factory to create appropriate source handlers"""
    
    @staticmethod
    def create_handler(source_category: str, document_type: str) -> Any:
        """Create appropriate handler based on source and document type"""
        if source_category == 'amc_official':
            if document_type in ['sid', 'kim', 'factsheet']:
                return PDFDocumentHandler()
            elif document_type == 'performance_page':
                return PerformancePageHandler()
            else:
                return AMCPageHandler()
        elif source_category == 'groww_aggregator':
            return AMCPageHandler()  # Use generic handler for aggregator pages
        elif source_category == 'regulatory':
            return AMCPageHandler()  # Use generic handler for regulatory pages
        else:
            return AMCPageHandler()  # Default handler
