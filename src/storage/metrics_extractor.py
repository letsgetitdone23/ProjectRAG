"""
Metrics Extractor for extracting key mutual fund data from scraped content
"""

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

@dataclass
class FundMetrics:
    """Data structure for key mutual fund metrics"""
    scheme_name: str
    amc_name: str
    
    # NAV data
    current_nav: Optional[float] = None
    nav_date: Optional[str] = None
    nav_change: Optional[float] = None
    nav_change_percentage: Optional[float] = None
    
    # Minimum investment
    lump_sum_minimum: Optional[float] = None
    sip_minimum: Optional[float] = None
    additional_purchase_minimum: Optional[float] = None
    sip_frequency: Optional[str] = None
    
    # Fund size
    aum: Optional[float] = None  # in crores
    aum_date: Optional[str] = None
    aum_change: Optional[float] = None
    number_of_folios: Optional[int] = None
    
    # Expense ratio
    expense_ratio: Optional[float] = None
    exit_load: Optional[float] = None
    entry_load: Optional[float] = None
    
    # Ratings
    value_research_rating: Optional[int] = None
    morningstar_rating: Optional[int] = None
    crisil_rating: Optional[str] = None
    riskometer_level: Optional[str] = None
    
    # Metadata
    last_updated: Optional[str] = None
    data_sources: List[str] = None
    extraction_timestamp: Optional[str] = None
    quality_score: Optional[float] = None
    source_urls: List[str] = None
    
    def __post_init__(self):
        if self.data_sources is None:
            self.data_sources = []
        if self.source_urls is None:
            self.source_urls = []
        if self.extraction_timestamp is None:
            self.extraction_timestamp = datetime.now().isoformat()

class MetricsExtractor:
    """Extracts key metrics from scraped content"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.extraction_patterns = self._load_extraction_patterns()
        
    def _load_extraction_patterns(self) -> Dict:
        """Load extraction patterns from config or use defaults"""
        patterns = {
            'nav': [
                r'NAV[:\s]*₹?([0-9,.-]+)',
                r'Net Asset Value[:\s]*₹?([0-9,.-]+)',
                r'NAV as on[:\s]*([0-9,.-]+)',
                r'Current NAV[:\s]*₹?([0-9,.-]+)'
            ],
            'nav_date': [
                r'NAV as on[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})',
                r'as on[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})',
                r'dated[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/]\d{4})'
            ],
            'sip_amount': [
                r'Minimum SIP[:\s]*₹?([0-9,]+)',
                r'SIP Amount[:\s]*₹?([0-9,]+)',
                r'Systematic Investment Plan[:\s]*₹?([0-9,]+)',
                r'Minimum SIP Amount[:\s]*₹?([0-9,]+)'
            ],
            'lump_sum': [
                r'Minimum Investment[:\s]*₹?([0-9,]+)',
                r'Minimum Application[:\s]*₹?([0-9,]+)',
                r'Minimum Lump Sum[:\s]*₹?([0-9,]+)'
            ],
            'aum': [
                r'AUM[:\s]*₹?([0-9,.-]+)\s*(cr|crore|Cr|Crore)',
                r'Assets Under Management[:\s]*₹?([0-9,.-]+)\s*(cr|crore)',
                r'Fund Size[:\s]*₹?([0-9,.-]+)\s*(cr|crore)'
            ],
            'expense_ratio': [
                r'Expense Ratio[:\s]*([0-9.]+%?)',
                r'Total Expense Ratio[:\s]*([0-9.]+%?)',
                r'TER[:\s]*([0-9.]+%?)',
                r'Annual Expense[:\s]*([0-9.]+%?)'
            ],
            'exit_load': [
                r'Exit Load[:\s]*([0-9.]+%?)',
                r'Exit Load[:\s]*([0-9.]+%?)\s*if',
                r'Contingent Exit Load[:\s]*([0-9.]+%?)'
            ],
            'value_research_rating': [
                r'Value Research[:\s]*([1-5])\s*(?:star|★)',
                r'VR Rating[:\s]*([1-5])\s*(?:star|★)'
            ],
            'morningstar_rating': [
                r'Morningstar[:\s]*([1-5])\s*(?:star|★)',
                r'Morningstar Rating[:\s]*([1-5])\s*(?:star|★)'
            ],
            'crisil_rating': [
                r'CRISIL[:\s]*([A-Z]+)',
                r'Rating[:\s]*([A-Z]{1,3})'
            ],
            'riskometer': [
                r'Riskometer[:\s]*(Very High|High|Moderate|Low)',
                r'Risk Level[:\s]*(Very High|High|Moderate|Low)',
                r'Risk[:\s]*(Very High|High|Moderate|Low)'
            ]
        }
        return patterns
    
    def extract_metrics_from_content(self, content: Dict) -> FundMetrics:
        """Extract metrics from a single content item"""
        try:
            # Get basic info
            url_info = content.get('metadata', {}).get('url_info', {})
            scheme_name = url_info.get('scheme_name', 'Unknown')
            amc_name = url_info.get('amc', 'Unknown AMC')
            source_url = content.get('url', '')
            
            # Create metrics object
            metrics = FundMetrics(
                scheme_name=scheme_name,
                amc_name=amc_name,
                source_urls=[source_url]
            )
            
            # Extract from text content
            text_content = content.get('text_content', '')
            structured_data = content.get('structured_data', {})
            tables = content.get('tables', [])
            
            # Extract from text
            self._extract_from_text(text_content, metrics)
            
            # Extract from structured data
            self._extract_from_structured_data(structured_data, metrics)
            
            # Extract from tables
            self._extract_from_tables(tables, metrics)
            
            # Set data sources
            document_type = url_info.get('document_type', 'unknown')
            source_category = url_info.get('source_category', 'unknown')
            metrics.data_sources = [f"{source_category}:{document_type}"]
            
            # Calculate quality score
            metrics.quality_score = self._calculate_quality_score(metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error extracting metrics from content: {str(e)}")
            return FundMetrics(scheme_name="Error", amc_name="Error")
    
    def _extract_from_text(self, text: str, metrics: FundMetrics) -> None:
        """Extract metrics from text content"""
        text_lower = text.lower()
        
        # Extract NAV
        nav_match = self._find_first_match(text_lower, self.extraction_patterns['nav'])
        if nav_match:
            metrics.current_nav = self._parse_number(nav_match)
        
        # Extract NAV date
        nav_date_match = self._find_first_match(text, self.extraction_patterns['nav_date'])
        if nav_date_match:
            metrics.nav_date = nav_date_match
        
        # Extract SIP amount
        sip_match = self._find_first_match(text_lower, self.extraction_patterns['sip_amount'])
        if sip_match:
            metrics.sip_minimum = self._parse_number(sip_match)
        
        # Extract lump sum minimum
        lump_sum_match = self._find_first_match(text_lower, self.extraction_patterns['lump_sum'])
        if lump_sum_match:
            metrics.lump_sum_minimum = self._parse_number(lump_sum_match)
        
        # Extract AUM
        aum_match = self._find_first_match(text_lower, self.extraction_patterns['aum'])
        if aum_match:
            metrics.aum = self._parse_number(aum_match)
        
        # Extract expense ratio
        expense_match = self._find_first_match(text_lower, self.extraction_patterns['expense_ratio'])
        if expense_match:
            metrics.expense_ratio = self._parse_percentage(expense_match)
        
        # Extract exit load
        exit_load_match = self._find_first_match(text_lower, self.extraction_patterns['exit_load'])
        if exit_load_match:
            metrics.exit_load = self._parse_percentage(exit_load_match)
        
        # Extract ratings
        vr_match = self._find_first_match(text, self.extraction_patterns['value_research_rating'])
        if vr_match:
            metrics.value_research_rating = int(vr_match)
        
        morningstar_match = self._find_first_match(text, self.extraction_patterns['morningstar_rating'])
        if morningstar_match:
            metrics.morningstar_rating = int(morningstar_match)
        
        crisil_match = self._find_first_match(text, self.extraction_patterns['crisil_rating'])
        if crisil_match:
            metrics.crisil_rating = crisil_match
        
        riskometer_match = self._find_first_match(text, self.extraction_patterns['riskometer'])
        if riskometer_match:
            metrics.riskometer_level = riskometer_match
    
    def _extract_from_structured_data(self, structured_data: Dict, metrics: FundMetrics) -> None:
        """Extract metrics from structured data"""
        # Extract from performance data
        performance_data = structured_data.get('performance_data', {})
        if performance_data:
            if not metrics.current_nav and 'current_nav' in performance_data:
                metrics.current_nav = self._parse_number(performance_data['current_nav'])
            if not metrics.nav_date and 'nav_date' in performance_data:
                metrics.nav_date = performance_data['nav_date']
        
        # Extract from scheme data
        scheme_data = structured_data.get('scheme_data', {})
        if scheme_data:
            if not metrics.sip_minimum and 'minimum_sip_amount' in scheme_data:
                metrics.sip_minimum = self._parse_number(scheme_data['minimum_sip_amount'])
            if not metrics.lump_sum_minimum and 'minimum_application_amount' in scheme_data:
                metrics.lump_sum_minimum = self._parse_number(scheme_data['minimum_application_amount'])
        
        # Extract from AMC data
        amc_data = structured_data.get('amc_data', {})
        if amc_data:
            if not metrics.expense_ratio and 'expense_ratio' in amc_data:
                metrics.expense_ratio = self._parse_percentage(amc_data['expense_ratio'])
            if not metrics.exit_load and 'exit_load' in amc_data:
                metrics.exit_load = self._parse_percentage(amc_data['exit_load'])
    
    def _extract_from_tables(self, tables: List[Dict], metrics: FundMetrics) -> None:
        """Extract metrics from table data"""
        for table in tables:
            table_data = table.get('data', [])
            headers = table.get('headers', [])
            
            # Look for key metrics in tables
            for i, row in enumerate(table_data):
                if len(row) >= 2:
                    key = str(row[0]).lower().strip()
                    value = str(row[1]).strip()
                    
                    # NAV
                    if 'nav' in key and not metrics.current_nav:
                        metrics.current_nav = self._parse_number(value)
                    
                    # SIP
                    elif 'sip' in key and not metrics.sip_minimum:
                        metrics.sip_minimum = self._parse_number(value)
                    
                    # AUM
                    elif 'aum' in key or 'assets' in key and not metrics.aum:
                        metrics.aum = self._parse_number(value)
                    
                    # Expense Ratio
                    elif 'expense' in key and not metrics.expense_ratio:
                        metrics.expense_ratio = self._parse_percentage(value)
                    
                    # Exit Load
                    elif 'exit' in key and 'load' in key and not metrics.exit_load:
                        metrics.exit_load = self._parse_percentage(value)
    
    def _find_first_match(self, text: str, patterns: List[str]) -> Optional[str]:
        """Find first matching pattern"""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _parse_number(self, value: str) -> Optional[float]:
        """Parse number string and return float"""
        try:
            # Remove commas and convert to float
            cleaned = re.sub(r'[^\d.-]', '', value)
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None
    
    def _parse_percentage(self, value: str) -> Optional[float]:
        """Parse percentage string and return float"""
        try:
            # Remove % and convert to float
            cleaned = re.sub(r'[^\d.-]', '', value)
            result = float(cleaned) if cleaned else None
            return result / 100 if result and result > 1 else result  # Convert if > 1
        except (ValueError, TypeError):
            return None
    
    def _calculate_quality_score(self, metrics: FundMetrics) -> float:
        """Calculate quality score based on extracted data completeness"""
        score = 0.0
        total_fields = 12  # Total key fields we expect
        
        # Key fields and their weights
        field_weights = {
            'current_nav': 2,
            'sip_minimum': 2,
            'aum': 2,
            'expense_ratio': 2,
            'exit_load': 1,
            'value_research_rating': 1,
            'morningstar_rating': 1,
            'crisil_rating': 1
        }
        
        total_weight = sum(field_weights.values())
        earned_weight = 0
        
        for field, weight in field_weights.items():
            if getattr(metrics, field) is not None:
                earned_weight += weight
        
        score = earned_weight / total_weight if total_weight > 0 else 0.0
        return round(score, 2)
    
    def consolidate_metrics(self, metrics_list: List[FundMetrics]) -> FundMetrics:
        """Consolidate metrics from multiple sources"""
        if not metrics_list:
            return FundMetrics(scheme_name="Unknown", amc_name="Unknown")
        
        # Use the first one as base
        consolidated = FundMetrics(
            scheme_name=metrics_list[0].scheme_name,
            amc_name=metrics_list[0].amc_name
        )
        
        # Consolidate from all sources
        for metrics in metrics_list:
            # NAV - prefer most recent
            if metrics.current_nav and not consolidated.current_nav:
                consolidated.current_nav = metrics.current_nav
                consolidated.nav_date = metrics.nav_date
            
            # SIP - prefer lowest minimum
            if metrics.sip_minimum:
                if not consolidated.sip_minimum or metrics.sip_minimum < consolidated.sip_minimum:
                    consolidated.sip_minimum = metrics.sip_minimum
            
            # AUM - prefer highest (most recent)
            if metrics.aum:
                if not consolidated.aum or metrics.aum > consolidated.aum:
                    consolidated.aum = metrics.aum
                    consolidated.aum_date = metrics.aum_date
            
            # Expense ratio - prefer lowest
            if metrics.expense_ratio:
                if not consolidated.expense_ratio or metrics.expense_ratio < consolidated.expense_ratio:
                    consolidated.expense_ratio = metrics.expense_ratio
            
            # Exit load - prefer lowest
            if metrics.exit_load:
                if not consolidated.exit_load or metrics.exit_load < consolidated.exit_load:
                    consolidated.exit_load = metrics.exit_load
            
            # Ratings - prefer highest available
            if metrics.value_research_rating:
                if not consolidated.value_research_rating or metrics.value_research_rating > consolidated.value_research_rating:
                    consolidated.value_research_rating = metrics.value_research_rating
            
            if metrics.morningstar_rating:
                if not consolidated.morningstar_rating or metrics.morningstar_rating > consolidated.morningstar_rating:
                    consolidated.morningstar_rating = metrics.morningstar_rating
            
            # CRISIL rating - keep first available
            if metrics.crisil_rating and not consolidated.crisil_rating:
                consolidated.crisil_rating = metrics.crisil_rating
            
            # Riskometer - keep first available
            if metrics.riskometer_level and not consolidated.riskometer_level:
                consolidated.riskometer_level = metrics.riskometer_level
            
            # Merge data sources
            consolidated.data_sources.extend(metrics.data_sources)
            consolidated.source_urls.extend(metrics.source_urls)
        
        # Remove duplicates and update timestamp
        consolidated.data_sources = list(set(consolidated.data_sources))
        consolidated.source_urls = list(set(consolidated.source_urls))
        consolidated.extraction_timestamp = datetime.now().isoformat()
        consolidated.quality_score = self._calculate_quality_score(consolidated)
        
        return consolidated
    
    def save_metrics_to_file(self, metrics: FundMetrics, output_dir: Path) -> str:
        """Save metrics to JSON file"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        scheme_name_safe = re.sub(r'[^a-zA-Z0-9_]', '_', metrics.scheme_name.lower())
        filename = f"{scheme_name_safe}_metrics.json"
        filepath = output_dir / filename
        
        # Convert to dict
        metrics_dict = {
            'scheme_name': metrics.scheme_name,
            'amc_name': metrics.amc_name,
            'nav': {
                'current_nav': metrics.current_nav,
                'nav_date': metrics.nav_date,
                'nav_change': metrics.nav_change,
                'nav_change_percentage': metrics.nav_change_percentage
            },
            'minimum_investment': {
                'lump_sum_minimum': metrics.lump_sum_minimum,
                'sip_minimum': metrics.sip_minimum,
                'additional_purchase_minimum': metrics.additional_purchase_minimum,
                'sip_frequency': metrics.sip_frequency
            },
            'fund_size': {
                'aum': metrics.aum,
                'aum_date': metrics.aum_date,
                'aum_change': metrics.aum_change,
                'number_of_folios': metrics.number_of_folios
            },
            'expense_ratio': {
                'expense_ratio': metrics.expense_ratio,
                'exit_load': metrics.exit_load,
                'entry_load': metrics.entry_load
            },
            'ratings': {
                'value_research_rating': metrics.value_research_rating,
                'morningstar_rating': metrics.morningstar_rating,
                'crisil_rating': metrics.crisil_rating,
                'riskometer_level': metrics.riskometer_level
            },
            'metadata': {
                'last_updated': metrics.last_updated,
                'data_sources': metrics.data_sources,
                'extraction_timestamp': metrics.extraction_timestamp,
                'quality_score': metrics.quality_score,
                'source_urls': metrics.source_urls
            }
        }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metrics_dict, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
