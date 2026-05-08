"""
Metrics Storage for managing structured mutual fund data
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict

from metrics_extractor import FundMetrics, MetricsExtractor

class MetricsStorage:
    """Manages storage and retrieval of fund metrics"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.storage_config = config.get('storage_config', {})
        self.base_dir = Path(config.get('base_dir', 'data'))
        self.metrics_dir = self.base_dir / self.storage_config.get('metrics_files_dir', 'metrics')
        self.backup_dir = self.base_dir / self.storage_config.get('backup_dir', 'backups')
        
        # Ensure directories exist
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def store_metrics(self, metrics: FundMetrics, scheme_name: str = None) -> str:
        """Store metrics for a specific scheme"""
        try:
            # Determine scheme name if not provided
            if not scheme_name:
                scheme_name = metrics.scheme_name
            
            # Generate filename
            filename = self._generate_filename(scheme_name)
            filepath = self.metrics_dir / filename
            
            # Create backup of existing file
            if filepath.exists():
                self._create_backup(filepath)
            
            # Save current metrics
            metrics_dict = self._metrics_to_dict(metrics)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metrics_dict, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Stored metrics for {scheme_name} to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to store metrics for {scheme_name}: {str(e)}")
            raise
    
    def load_metrics(self, scheme_name: str) -> Optional[FundMetrics]:
        """Load metrics for a specific scheme"""
        try:
            filename = self._generate_filename(scheme_name)
            filepath = self.metrics_dir / filename
            
            if not filepath.exists():
                self.logger.warning(f"No metrics file found for {scheme_name}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metrics = self._dict_to_metrics(data)
            self.logger.info(f"Loaded metrics for {scheme_name}")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to load metrics for {scheme_name}: {str(e)}")
            return None
    
    def load_all_metrics(self) -> Dict[str, FundMetrics]:
        """Load all available metrics"""
        metrics_dict = {}
        
        try:
            for filepath in self.metrics_dir.glob("*_metrics.json"):
                scheme_name = self._extract_scheme_name_from_filename(filepath.name)
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                metrics = self._dict_to_metrics(data)
                metrics_dict[scheme_name] = metrics
            
            self.logger.info(f"Loaded {len(metrics_dict)} metric files")
            return metrics_dict
            
        except Exception as e:
            self.logger.error(f"Failed to load all metrics: {str(e)}")
            return {}
    
    def update_metrics(self, new_metrics: FundMetrics, scheme_name: str = None) -> bool:
        """Update metrics with new data"""
        try:
            # Load existing metrics
            existing_metrics = self.load_metrics(scheme_name or new_metrics.scheme_name)
            
            if existing_metrics:
                # Merge with existing data
                updated_metrics = self._merge_metrics(existing_metrics, new_metrics)
            else:
                # Use new metrics as is
                updated_metrics = new_metrics
            
            # Store updated metrics
            self.store_metrics(updated_metrics, scheme_name or new_metrics.scheme_name)
            
            self.logger.info(f"Updated metrics for {scheme_name or new_metrics.scheme_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update metrics: {str(e)}")
            return False
    
    def get_metrics_summary(self) -> Dict:
        """Get summary of all stored metrics"""
        summary = {
            'total_schemes': 0,
            'schemes': {},
            'last_updated': None,
            'data_quality': {}
        }
        
        try:
            all_metrics = self.load_all_metrics()
            summary['total_schemes'] = len(all_metrics)
            
            quality_scores = []
            
            for scheme_name, metrics in all_metrics.items():
                scheme_summary = {
                    'nav': metrics.current_nav,
                    'sip_minimum': metrics.sip_minimum,
                    'aum': metrics.aum,
                    'expense_ratio': metrics.expense_ratio,
                    'quality_score': metrics.quality_score,
                    'last_updated': metrics.last_updated,
                    'data_sources': metrics.data_sources
                }
                
                summary['schemes'][scheme_name] = scheme_summary
                quality_scores.append(metrics.quality_score)
                
                # Track latest update
                if metrics.last_updated:
                    if not summary['last_updated'] or metrics.last_updated > summary['last_updated']:
                        summary['last_updated'] = metrics.last_updated
            
            # Calculate overall quality
            if quality_scores:
                summary['data_quality'] = {
                    'average_quality_score': sum(quality_scores) / len(quality_scores),
                    'min_quality_score': min(quality_scores),
                    'max_quality_score': max(quality_scores)
                }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate metrics summary: {str(e)}")
            return summary
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old backup files"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cleaned_files = 0
            
            for filepath in self.backup_dir.glob("*"):
                if filepath.is_file():
                    file_mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        filepath.unlink()
                        cleaned_files += 1
            
            self.logger.info(f"Cleaned up {cleaned_files} old backup files")
            return cleaned_files
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {str(e)}")
            return 0
    
    def _generate_filename(self, scheme_name: str) -> str:
        """Generate filename for metrics file"""
        # Clean scheme name
        scheme_name_safe = scheme_name.lower().replace(' ', '_').replace('-', '_')
        scheme_name_safe = ''.join(c for c in scheme_name_safe if c.isalnum() or c == '_')
        
        return f"{scheme_name_safe}_metrics.json"
    
    def _extract_scheme_name_from_filename(self, filename: str) -> str:
        """Extract scheme name from filename"""
        # Remove _metrics.json suffix
        base_name = filename.replace('_metrics.json', '')
        
        # Convert back to readable format
        scheme_name = base_name.replace('_', ' ').title()
        return scheme_name
    
    def _create_backup(self, filepath: Path) -> None:
        """Create backup of existing file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{filepath.stem}_backup_{timestamp}{filepath.suffix}"
            backup_path = self.backup_dir / backup_filename
            
            # Copy file to backup location
            import shutil
            shutil.copy2(filepath, backup_path)
            
            self.logger.debug(f"Created backup: {backup_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to create backup: {str(e)}")
    
    def _metrics_to_dict(self, metrics: FundMetrics) -> Dict:
        """Convert FundMetrics to dictionary"""
        return {
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
    
    def _dict_to_metrics(self, data: Dict) -> FundMetrics:
        """Convert dictionary to FundMetrics"""
        # Extract nested data
        nav_data = data.get('nav', {})
        investment_data = data.get('minimum_investment', {})
        fund_size_data = data.get('fund_size', {})
        expense_data = data.get('expense_ratio', {})
        ratings_data = data.get('ratings', {})
        metadata = data.get('metadata', {})
        
        return FundMetrics(
            scheme_name=data.get('scheme_name', 'Unknown'),
            amc_name=data.get('amc_name', 'Unknown'),
            
            # NAV data
            current_nav=nav_data.get('current_nav'),
            nav_date=nav_data.get('nav_date'),
            nav_change=nav_data.get('nav_change'),
            nav_change_percentage=nav_data.get('nav_change_percentage'),
            
            # Investment data
            lump_sum_minimum=investment_data.get('lump_sum_minimum'),
            sip_minimum=investment_data.get('sip_minimum'),
            additional_purchase_minimum=investment_data.get('additional_purchase_minimum'),
            sip_frequency=investment_data.get('sip_frequency'),
            
            # Fund size data
            aum=fund_size_data.get('aum'),
            aum_date=fund_size_data.get('aum_date'),
            aum_change=fund_size_data.get('aum_change'),
            number_of_folios=fund_size_data.get('number_of_folios'),
            
            # Expense data
            expense_ratio=expense_data.get('expense_ratio'),
            exit_load=expense_data.get('exit_load'),
            entry_load=expense_data.get('entry_load'),
            
            # Ratings data
            value_research_rating=ratings_data.get('value_research_rating'),
            morningstar_rating=ratings_data.get('morningstar_rating'),
            crisil_rating=ratings_data.get('crisil_rating'),
            riskometer_level=ratings_data.get('riskometer_level'),
            
            # Metadata
            last_updated=metadata.get('last_updated'),
            data_sources=metadata.get('data_sources', []),
            extraction_timestamp=metadata.get('extraction_timestamp'),
            quality_score=metadata.get('quality_score'),
            source_urls=metadata.get('source_urls', [])
        )
    
    def _merge_metrics(self, existing: FundMetrics, new: FundMetrics) -> FundMetrics:
        """Merge existing metrics with new data"""
        merged = FundMetrics(
            scheme_name=existing.scheme_name,
            amc_name=existing.amc_name
        )
        
        # NAV - prefer newer data
        if new.current_nav and new.nav_date:
            merged.current_nav = new.current_nav
            merged.nav_date = new.nav_date
        else:
            merged.current_nav = existing.current_nav
            merged.nav_date = existing.nav_date
        
        # SIP - prefer lower minimum
        if new.sip_minimum and (not existing.sip_minimum or new.sip_minimum < existing.sip_minimum):
            merged.sip_minimum = new.sip_minimum
        else:
            merged.sip_minimum = existing.sip_minimum
        
        # AUM - prefer higher (more recent)
        if new.aum and (not existing.aum or new.aum > existing.aum):
            merged.aum = new.aum
            merged.aum_date = new.aum_date
        else:
            merged.aum = existing.aum
            merged.aum_date = existing.aum_date
        
        # Expense ratio - prefer lower
        if new.expense_ratio and (not existing.expense_ratio or new.expense_ratio < existing.expense_ratio):
            merged.expense_ratio = new.expense_ratio
        else:
            merged.expense_ratio = existing.expense_ratio
        
        # Exit load - prefer lower
        if new.exit_load and (not existing.exit_load or new.exit_load < existing.exit_load):
            merged.exit_load = new.exit_load
        else:
            merged.exit_load = existing.exit_load
        
        # Ratings - prefer higher available
        if new.value_research_rating and (not existing.value_research_rating or new.value_research_rating > existing.value_research_rating):
            merged.value_research_rating = new.value_research_rating
        else:
            merged.value_research_rating = existing.value_research_rating
        
        if new.morningstar_rating and (not existing.morningstar_rating or new.morningstar_rating > existing.morningstar_rating):
            merged.morningstar_rating = new.morningstar_rating
        else:
            merged.morningstar_rating = existing.morningstar_rating
        
        # CRISIL and riskometer - keep first available
        merged.crisil_rating = new.crisil_rating or existing.crisil_rating
        merged.riskometer_level = new.riskometer_level or existing.riskometer_level
        
        # Merge other fields
        merged.lump_sum_minimum = new.lump_sum_minimum or existing.lump_sum_minimum
        merged.additional_purchase_minimum = new.additional_purchase_minimum or existing.additional_purchase_minimum
        merged.sip_frequency = new.sip_frequency or existing.sip_frequency
        merged.nav_change = new.nav_change or existing.nav_change
        merged.nav_change_percentage = new.nav_change_percentage or existing.nav_change_percentage
        merged.aum_change = new.aum_change or existing.aum_change
        merged.number_of_folios = new.number_of_folios or existing.number_of_folios
        merged.entry_load = new.entry_load or existing.entry_load
        
        # Merge metadata
        merged.data_sources = list(set(existing.data_sources + new.data_sources))
        merged.source_urls = list(set(existing.source_urls + new.source_urls))
        merged.extraction_timestamp = new.extraction_timestamp or existing.extraction_timestamp
        merged.quality_score = new.quality_score or existing.quality_score
        
        return merged
