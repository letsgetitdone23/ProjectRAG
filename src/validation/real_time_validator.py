"""
Real-time Data Validator
Validates RAG responses against multiple sources for accuracy
"""

import logging
import requests
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Result of validation process"""
    is_valid: bool
    confidence: float
    sources: List[Dict]
    recommended_value: Optional[str]
    discrepancy_detected: bool
    last_updated: Optional[str]

class RealTimeValidator:
    """Validates RAG responses against multiple sources"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Source configurations
        self.sources = {
            'amfi': {
                'name': 'AMFI Official',
                'base_url': 'https://www.amfiindia.com',
                'reliability': 0.95,
                'update_frequency': 'daily'
            },
            'groww': {
                'name': 'Groww Aggregator',
                'base_url': 'https://groww.in',
                'reliability': 0.85,
                'update_frequency': 'real-time'
            },
            'official_amc': {
                'name': 'Official AMC Website',
                'base_url': 'https://www.nipponindiamf.com',
                'reliability': 0.90,
                'update_frequency': 'daily'
            }
        }
    
    def validate_nav(self, fund_name: str, our_nav: str, our_source: str) -> ValidationResult:
        """Validate NAV against multiple sources"""
        self.logger.info(f"Validating NAV for {fund_name}")
        
        sources_data = []
        discrepancies = []
        
        # Fetch from all sources
        for source_key, source_config in self.sources.items():
            try:
                nav_data = self._fetch_nav_from_source(source_key, source_config, fund_name)
                if nav_data:
                    sources_data.append(nav_data)
                    
                    # Check for discrepancy
                    if self._compare_nav_values(our_nav, nav_data['nav']):
                        discrepancies.append({
                            'source': source_config['name'],
                            'their_nav': nav_data['nav'],
                            'our_nav': our_nav,
                            'difference': abs(float(our_nav.replace('₹', '').replace(',', '')) - float(nav_data['nav'].replace('₹', '').replace(',', '')))
                        })
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source_config['name']}: {str(e)}")
        
        # Calculate validation result
        return self._calculate_validation_result(sources_data, our_nav, our_source, discrepancies)
    
    def validate_expense_ratio(self, fund_name: str, our_ratio: str, our_source: str) -> ValidationResult:
        """Validate expense ratio against multiple sources"""
        self.logger.info(f"Validating expense ratio for {fund_name}")
        
        sources_data = []
        discrepancies = []
        
        # Fetch from all sources
        for source_key, source_config in self.sources.items():
            try:
                ratio_data = self._fetch_expense_ratio_from_source(source_key, source_config, fund_name)
                if ratio_data:
                    sources_data.append(ratio_data)
                    
                    # Check for discrepancy
                    if self._compare_percentage_values(our_ratio, ratio_data['ratio']):
                        discrepancies.append({
                            'source': source_config['name'],
                            'their_ratio': ratio_data['ratio'],
                            'our_ratio': our_ratio,
                            'difference': abs(float(our_ratio.replace('%', '')) - float(ratio_data['ratio'].replace('%', '')))
                        })
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source_config['name']}: {str(e)}")
        
        return self._calculate_validation_result(sources_data, our_ratio, our_source, discrepancies)
    
    def validate_exit_load(self, fund_name: str, our_load: str, our_source: str) -> ValidationResult:
        """Validate exit load details against multiple sources"""
        self.logger.info(f"Validating exit load for {fund_name}")
        
        sources_data = []
        discrepancies = []
        
        for source_key, source_config in self.sources.items():
            try:
                load_data = self._fetch_exit_load_from_source(source_key, source_config, fund_name)
                if load_data:
                    sources_data.append(load_data)
                    
                    if our_load.lower() != load_data['load'].lower():
                        discrepancies.append({
                            'source': source_config['name'],
                            'their_load': load_data['load'],
                            'our_load': our_load
                        })
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source_config['name']}: {str(e)}")
        
        return self._calculate_validation_result(sources_data, our_load, our_source, discrepancies)
    
    def validate_minimum_sip(self, fund_name: str, our_sip: str, our_source: str) -> ValidationResult:
        """Validate minimum SIP amount against multiple sources"""
        self.logger.info(f"Validating minimum SIP for {fund_name}")
        
        sources_data = []
        discrepancies = []
        
        for source_key, source_config in self.sources.items():
            try:
                sip_data = self._fetch_minimum_sip_from_source(source_key, source_config, fund_name)
                if sip_data:
                    sources_data.append(sip_data)
                    
                    if our_sip != sip_data['sip']:
                        discrepancies.append({
                            'source': source_config['name'],
                            'their_sip': sip_data['sip'],
                            'our_sip': our_sip
                        })
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source_config['name']}: {str(e)}")
        
        return self._calculate_validation_result(sources_data, our_sip, our_source, discrepancies)
    
    def validate_elss_lockin(self, fund_name: str, our_lockin: str, our_source: str) -> ValidationResult:
        """Validate ELSS lock-in period against multiple sources"""
        self.logger.info(f"Validating ELSS lock-in for {fund_name}")
        
        sources_data = []
        discrepancies = []
        
        for source_key, source_config in self.sources.items():
            try:
                lockin_data = self._fetch_elss_lockin_from_source(source_key, source_config, fund_name)
                if lockin_data:
                    sources_data.append(lockin_data)
                    
                    if our_lockin.lower() != lockin_data['lockin'].lower():
                        discrepancies.append({
                            'source': source_config['name'],
                            'their_lockin': lockin_data['lockin'],
                            'our_lockin': our_lockin
                        })
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source_config['name']}: {str(e)}")
        
        return self._calculate_validation_result(sources_data, our_lockin, our_source, discrepancies)
    
    def validate_riskometer(self, fund_name: str, our_risk: str, our_source: str) -> ValidationResult:
        """Validate riskometer classification against multiple sources"""
        self.logger.info(f"Validating riskometer for {fund_name}")
        
        sources_data = []
        discrepancies = []
        
        for source_key, source_config in self.sources.items():
            try:
                risk_data = self._fetch_riskometer_from_source(source_key, source_config, fund_name)
                if risk_data:
                    sources_data.append(risk_data)
                    
                    if our_risk.lower() != risk_data['risk'].lower():
                        discrepancies.append({
                            'source': source_config['name'],
                            'their_risk': risk_data['risk'],
                            'our_risk': our_risk
                        })
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source_config['name']}: {str(e)}")
        
        return self._calculate_validation_result(sources_data, our_risk, our_source, discrepancies)
    
    def validate_benchmark(self, fund_name: str, our_benchmark: str, our_source: str) -> ValidationResult:
        """Validate benchmark index against multiple sources"""
        self.logger.info(f"Validating benchmark for {fund_name}")
        
        sources_data = []
        discrepancies = []
        
        for source_key, source_config in self.sources.items():
            try:
                benchmark_data = self._fetch_benchmark_from_source(source_key, source_config, fund_name)
                if benchmark_data:
                    sources_data.append(benchmark_data)
                    
                    if our_benchmark.lower() != benchmark_data['benchmark'].lower():
                        discrepancies.append({
                            'source': source_config['name'],
                            'their_benchmark': benchmark_data['benchmark'],
                            'our_benchmark': our_benchmark
                        })
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source_config['name']}: {str(e)}")
        
        return self._calculate_validation_result(sources_data, our_benchmark, our_source, discrepancies)
    
    def _fetch_nav_from_source(self, source_key: str, source_config: Dict, fund_name: str) -> Optional[Dict]:
        """Fetch NAV from specific source"""
        # Mock implementation - replace with actual scraping
        if source_key == 'groww':
            return {
                'source': source_config['name'],
                'nav': '₹101.17',
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        elif source_key == 'amfi':
            return {
                'source': source_config['name'],
                'nav': '₹101.25',
                'last_updated': (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        elif source_key == 'official_amc':
            return {
                'source': source_config['name'],
                'nav': '₹101.10',
                'last_updated': (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        return None
    
    def _fetch_expense_ratio_from_source(self, source_key: str, source_config: Dict, fund_name: str) -> Optional[Dict]:
        """Fetch expense ratio from specific source"""
        # Mock implementation
        if source_key == 'groww':
            return {
                'source': source_config['name'],
                'ratio': '1.25%',
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        elif source_key == 'amfi':
            return {
                'source': source_config['name'],
                'ratio': '1.22%',
                'last_updated': (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        return None
    
    def _fetch_exit_load_from_source(self, source_key: str, source_config: Dict, fund_name: str) -> Optional[Dict]:
        """Fetch exit load from specific source"""
        # Mock implementation
        if source_key == 'groww':
            return {
                'source': source_config['name'],
                'load': 'Nil for units after 1 year',
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        return None
    
    def _fetch_minimum_sip_from_source(self, source_key: str, source_config: Dict, fund_name: str) -> Optional[Dict]:
        """Fetch minimum SIP from specific source"""
        # Mock implementation
        if source_key == 'groww':
            return {
                'source': source_config['name'],
                'sip': '₹500',
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        return None
    
    def _fetch_elss_lockin_from_source(self, source_key: str, source_config: Dict, fund_name: str) -> Optional[Dict]:
        """Fetch ELSS lock-in period from specific source"""
        # Mock implementation
        if source_key == 'amfi':
            return {
                'source': source_config['name'],
                'lockin': '3 years',
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        return None
    
    def _fetch_riskometer_from_source(self, source_key: str, source_config: Dict, fund_name: str) -> Optional[Dict]:
        """Fetch riskometer from specific source"""
        # Mock implementation
        if source_key == 'groww':
            return {
                'source': source_config['name'],
                'risk': 'Moderately High',
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        return None
    
    def _fetch_benchmark_from_source(self, source_key: str, source_config: Dict, fund_name: str) -> Optional[Dict]:
        """Fetch benchmark from specific source"""
        # Mock implementation
        if source_key == 'amfi':
            return {
                'source': source_config['name'],
                'benchmark': 'Nifty 50 TRI',
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'reliability': source_config['reliability']
            }
        return None
    
    def _compare_nav_values(self, our_nav: str, their_nav: str) -> bool:
        """Compare NAV values"""
        our_value = float(our_nav.replace('₹', '').replace(',', ''))
        their_value = float(their_nav.replace('₹', '').replace(',', ''))
        return abs(our_value - their_value) > 0.01  # 1 paisa difference threshold
    
    def _compare_percentage_values(self, our_value: str, their_value: str) -> bool:
        """Compare percentage values"""
        our_pct = float(our_value.replace('%', ''))
        their_pct = float(their_value.replace('%', ''))
        return abs(our_pct - their_pct) > 0.01  # 0.01% difference threshold
    
    def _calculate_validation_result(self, sources_data: List[Dict], our_value: str, our_source: str, discrepancies: List[Dict]) -> ValidationResult:
        """Calculate overall validation result"""
        if not sources_data:
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                sources=[],
                recommended_value=None,
                discrepancy_detected=True,
                last_updated=None
            )
        
        # Find most reliable source
        most_reliable = max(sources_data, key=lambda x: x['reliability'])
        
        # Calculate confidence based on source agreement
        agreement_count = len([s for s in sources_data if s['value'] == most_reliable['value']])
        confidence = agreement_count / len(sources_data)
        
        # Determine if discrepancy exists
        discrepancy_detected = len(discrepancies) > 0
        
        # Get most recent update
        last_updated = max([s['last_updated'] for s in sources_data])
        
        return ValidationResult(
            is_valid=confidence > 0.7,  # 70% agreement threshold
            confidence=confidence,
            sources=sources_data,
            recommended_value=most_reliable['value'],
            discrepancy_detected=discrepancy_detected,
            last_updated=last_updated
        )
