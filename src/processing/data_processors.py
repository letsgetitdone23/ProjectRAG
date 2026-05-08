"""
Data Processors for cleaning, validating, and transforming scraped content
"""

import re
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass
import hashlib

@dataclass
class ProcessedContent:
    original_url: str
    cleaned_content: str
    metadata: Dict
    quality_score: float
    processing_timestamp: str
    content_hash: str
    is_duplicate: bool = False
    advisory_content_detected: bool = False
    validation_errors: List[str] = None

class TextCleaner:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.financial_abbreviations = {
            'ELSS': 'Equity Linked Savings Scheme',
            'SIP': 'Systematic Investment Plan',
            'NAV': 'Net Asset Value',
            'AUM': 'Assets Under Management',
            'KYC': 'Know Your Customer',
            'PAN': 'Permanent Account Number',
            'ETF': 'Exchange Traded Fund',
            'FMP': 'Fixed Maturity Plan',
            'FOF': 'Fund of Funds',
            'MF': 'Mutual Fund'
        }
        
        self.advisory_patterns = [
            r'\b(invest|investment|investing)\b.*\b(advice|advise|recommendation|suggest)\b',
            r'\b(should|would|could|might)\b.*\b(invest|buy|sell|hold)\b',
            r'\b(best|better|worst|top|bottom)\b.*\b(fund|scheme|investment)\b',
            r'\b(good|bad|excellent|poor)\b.*\b(investment|return|performance)\b',
            r'\b(expect|anticipate|forecast|predict)\b.*\b(return|growth|performance)\b',
            r'\b(guarantee|assure|promise)\b.*\b(return|profit|gain)\b'
        ]
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep important ones
        text = re.sub(r'[^\w\s.,;:!?%&₹()-]', ' ', text)
        
        # Normalize line breaks
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Remove common navigation and footer text
        text = self._remove_navigation_text(text)
        
        # Expand financial abbreviations
        text = self._expand_abbreviations(text)
        
        # Normalize numbers and dates
        text = self._normalize_numbers(text)
        text = self._normalize_dates(text)
        
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _remove_navigation_text(self, text: str) -> str:
        """Remove common navigation and boilerplate text"""
        navigation_patterns = [
            r'Home|About|Contact|Login|Register|Sign\s+in|Sign\s+up',
            r'Privacy\s+Policy|Terms\s+of\s+Service|Disclaimer',
            r'Cookie\s+Policy|GDPR|Data\s+Protection',
            r'Back\s+to\s+top|Scroll\s+to\s+top',
            r'Facebook|Twitter|LinkedIn|Instagram|YouTube',
            r'©\s*\d{4}.*All\s+rights\s+reserved',
            r'Click\s+here|Learn\s+more|Read\s+more'
        ]
        
        for pattern in navigation_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text
    
    def _expand_abbreviations(self, text: str) -> str:
        """Expand financial abbreviations"""
        for abbr, expansion in self.financial_abbreviations.items():
            # Only expand if abbreviation appears as whole word
            pattern = r'\b' + re.escape(abbr) + r'\b'
            text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
        
        return text
    
    def _normalize_numbers(self, text: str) -> str:
        """Normalize number formats"""
        # Indian number format (crore, lakh)
        text = re.sub(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*cr', r'\1 crore', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*lakh', r'\1 lakh', text, flags=re.IGNORECASE)
        
        # Currency symbols
        text = re.sub(r'₹\s*(\d+(?:,\d{3})*(?:\.\d+)?)', r'INR \1', text)
        text = re.sub(r'Rs\.?\s*(\d+(?:,\d{3})*(?:\.\d+)?)', r'INR \1', text)
        
        # Percentages
        text = re.sub(r'(\d+(?:\.\d+)?)\s*%?', r'\1%', text)
        
        return text
    
    def _normalize_dates(self, text: str) -> str:
        """Normalize date formats"""
        # Various date formats to standard format
        date_patterns = [
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', r'\3-\2-\1'),  # DD/MM/YYYY
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', r'\3-\2-\1'),  # DD-MM-YYYY
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', r'\1-\2-\3'),  # YYYY/MM/DD
        ]
        
        for pattern, replacement in date_patterns:
            text = re.sub(pattern, replacement, text)
        
        return text

class ContentValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.required_fields = ['expense_ratio', 'nav', 'fund_name']
        self.facts_only_keywords = [
            'fact', 'data', 'information', 'details', 'specification',
            'ratio', 'percentage', 'amount', 'value', 'rate', 'period',
            'date', 'time', 'duration', 'minimum', 'maximum', 'limit'
        ]
        
        self.prohibited_keywords = [
            'advice', 'advise', 'recommendation', 'suggest', 'opinion',
            'best', 'worst', 'better', 'good', 'bad', 'excellent', 'poor',
            'should', 'would', 'could', 'might', 'expect', 'predict',
            'guarantee', 'promise', 'assure', 'forecast'
        ]
    
    def validate_content(self, content: str, metadata: Dict) -> Dict:
        """Validate content for facts-only compliance"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'advisory_content_detected': False,
            'completeness_score': 0.0,
            'factual_score': 0.0
        }
        
        # Check for advisory content
        advisory_check = self._check_advisory_content(content)
        validation_result['advisory_content_detected'] = advisory_check['detected']
        if advisory_check['detected']:
            validation_result['errors'].extend(advisory_check['violations'])
            validation_result['is_valid'] = False
        
        # Check completeness
        completeness = self._check_completeness(content, metadata)
        validation_result['completeness_score'] = completeness['score']
        validation_result['warnings'].extend(completeness['missing_fields'])
        
        # Check factual nature
        factual_score = self._calculate_factual_score(content)
        validation_result['factual_score'] = factual_score
        
        if factual_score < 0.7:
            validation_result['warnings'].append('Content may contain non-factual information')
        
        return validation_result
    
    def _check_advisory_content(self, content: str) -> Dict:
        """Check for advisory content patterns"""
        detected = False
        violations = []
        
        text_lower = content.lower()
        
        # Check for advisory patterns
        advisory_patterns = [
            r'\b(invest|investment|investing)\b.*\b(advice|advise|recommendation|suggest)\b',
            r'\b(should|would|could|might)\b.*\b(invest|buy|sell|hold)\b',
            r'\b(best|better|worst|top|bottom)\b.*\b(fund|scheme|investment)\b',
            r'\b(good|bad|excellent|poor)\b.*\b(investment|return|performance)\b',
            r'\b(expect|anticipate|forecast|predict)\b.*\b(return|growth|performance)\b',
            r'\b(guarantee|assure|promise)\b.*\b(return|profit|gain)\b'
        ]
        
        for pattern in advisory_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                detected = True
                violations.append(f"Advisory pattern detected: {pattern}")
        
        return {'detected': detected, 'violations': violations}
    
    def _check_completeness(self, content: str, metadata: Dict) -> Dict:
        """Check if content contains required information"""
        missing_fields = []
        found_fields = []
        
        # Check for key mutual fund information
        key_patterns = {
            'expense_ratio': r'expense\s*ratio[:\s]*([0-9.]+%?)',
            'nav': r'nav[:\s]*₹?([0-9,.-]+)',
            'fund_name': r'fund\s*name[:\s]*([a-zA-Z\s&-]+)',
            'exit_load': r'exit\s*load[:\s]*([0-9.]+%?)',
            'risk_level': r'risk[:\s]*(low|moderate|high|very\s*high)',
            'category': r'category[:\s]*([a-zA-Z\s-]+)',
            'minimum_investment': r'minimum\s*investment[:\s]*₹?([0-9,]+)',
            'sip_amount': r'sip[:\s]*₹?([0-9,]+)'
        }
        
        for field, pattern in key_patterns.items():
            if re.search(pattern, content.lower()):
                found_fields.append(field)
            else:
                missing_fields.append(field)
        
        # Calculate completeness score
        total_fields = len(key_patterns)
        found_count = len(found_fields)
        score = found_count / total_fields if total_fields > 0 else 0.0
        
        return {'score': score, 'missing_fields': missing_fields, 'found_fields': found_fields}
    
    def _calculate_factual_score(self, content: str) -> float:
        """Calculate score based on factual vs. advisory content"""
        text_lower = content.lower()
        
        # Count factual keywords
        factual_count = sum(1 for keyword in self.facts_only_keywords if keyword in text_lower)
        
        # Count prohibited keywords
        prohibited_count = sum(1 for keyword in self.prohibited_keywords if keyword in text_lower)
        
        # Calculate score (higher is more factual)
        total_keywords = factual_count + prohibited_count
        if total_keywords == 0:
            return 1.0  # Assume factual if no keywords found
        
        factual_score = factual_count / total_keywords
        return factual_score

class DuplicateDetector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.seen_hashes: Set[str] = set()
        self.content_cache: Dict[str, Dict] = {}
    
    def is_duplicate(self, content: str, url: str) -> tuple[bool, Optional[str]]:
        """Check if content is duplicate"""
        # Generate content hash
        content_hash = self._generate_content_hash(content)
        
        # Check if hash exists
        if content_hash in self.seen_hashes:
            original_url = self.content_cache.get(content_hash, {}).get('url')
            return True, original_url
        
        # Store new content
        self.seen_hashes.add(content_hash)
        self.content_cache[content_hash] = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'content_length': len(content)
        }
        
        return False, None
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content"""
        # Normalize content for hashing
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def get_duplicate_stats(self) -> Dict:
        """Get duplicate detection statistics"""
        return {
            'total_content_hashes': len(self.seen_hashes),
            'cache_size': len(self.content_cache),
            'memory_usage_estimate': len(str(self.content_cache))  # Rough estimate
        }

class ChangeDetector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.previous_content: Dict[str, Dict] = {}
    
    def detect_changes(self, url: str, current_content: str, current_metadata: Dict) -> Dict:
        """Detect changes compared to previous content"""
        changes = {
            'has_changes': False,
            'content_changes': [],
            'metadata_changes': [],
            'change_summary': ''
        }
        
        # Get previous content
        previous = self.previous_content.get(url, {})
        
        if not previous:
            # First time seeing this content
            changes['has_changes'] = True
            changes['change_summary'] = 'New content detected'
        else:
            # Compare content
            content_diff = self._compare_content(previous.get('content', ''), current_content)
            if content_diff:
                changes['has_changes'] = True
                changes['content_changes'] = content_diff
            
            # Compare metadata
            metadata_diff = self._compare_metadata(previous.get('metadata', {}), current_metadata)
            if metadata_diff:
                changes['has_changes'] = True
                changes['metadata_changes'] = metadata_diff
        
        # Update stored content
        self.previous_content[url] = {
            'content': current_content,
            'metadata': current_metadata,
            'timestamp': datetime.now().isoformat()
        }
        
        return changes
    
    def _compare_content(self, old_content: str, new_content: str) -> List[str]:
        """Compare content and return differences"""
        differences = []
        
        # Length difference
        old_len = len(old_content)
        new_len = len(new_content)
        
        if abs(old_len - new_len) > 100:  # Significant length change
            differences.append(f"Content length changed from {old_len} to {new_len} characters")
        
        # Word count difference
        old_words = len(old_content.split())
        new_words = len(new_content.split())
        
        if abs(old_words - new_words) > 10:  # Significant word count change
            differences.append(f"Word count changed from {old_words} to {new_words}")
        
        # Check for new key information
        key_patterns = {
            'expense_ratio': r'expense\s*ratio[:\s]*([0-9.]+%?)',
            'nav': r'nav[:\s]*₹?([0-9,.-]+)',
            'exit_load': r'exit\s*load[:\s]*([0-9.]+%?)'
        }
        
        for field, pattern in key_patterns.items():
            old_match = re.search(pattern, old_content.lower())
            new_match = re.search(pattern, new_content.lower())
            
            if old_match != new_match:
                if new_match and not old_match:
                    differences.append(f"New {field} information added")
                elif old_match and not new_match:
                    differences.append(f"{field} information removed")
                elif old_match and new_match and old_match.group(1) != new_match.group(1):
                    differences.append(f"{field} value changed")
        
        return differences
    
    def _compare_metadata(self, old_metadata: Dict, new_metadata: Dict) -> List[str]:
        """Compare metadata and return differences"""
        differences = []
        
        # Check for new metadata fields
        for key in new_metadata:
            if key not in old_metadata:
                differences.append(f"New metadata field: {key}")
            elif old_metadata[key] != new_metadata[key]:
                differences.append(f"Metadata field {key} changed")
        
        return differences

class DataProcessor:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.text_cleaner = TextCleaner()
        self.content_validator = ContentValidator()
        self.duplicate_detector = DuplicateDetector()
        self.change_detector = ChangeDetector()
        
    def process_content(self, raw_content: Dict) -> ProcessedContent:
        """Process raw scraped content"""
        try:
            # Extract basic information
            url = raw_content.get('url', '')
            text_content = raw_content.get('text_content', '')
            metadata = raw_content.get('metadata', {})
            
            # Clean text
            cleaned_content = self.text_cleaner.clean_text(text_content)
            
            # Generate content hash
            content_hash = hashlib.md5(cleaned_content.encode()).hexdigest()
            
            # Check for duplicates
            is_duplicate, original_url = self.duplicate_detector.is_duplicate(cleaned_content, url)
            
            # Validate content
            validation_result = self.content_validator.validate_content(cleaned_content, metadata)
            
            # Detect changes
            changes = self.change_detector.detect_changes(url, cleaned_content, metadata)
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(
                validation_result, len(cleaned_content), changes
            )
            
            # Create processed content
            processed = ProcessedContent(
                original_url=url,
                cleaned_content=cleaned_content,
                metadata={
                    **metadata,
                    'validation_result': validation_result,
                    'changes': changes,
                    'processing_timestamp': datetime.now().isoformat()
                },
                quality_score=quality_score,
                processing_timestamp=datetime.now().isoformat(),
                content_hash=content_hash,
                is_duplicate=is_duplicate,
                advisory_content_detected=validation_result['advisory_content_detected'],
                validation_errors=validation_result['errors']
            )
            
            if is_duplicate:
                self.logger.info(f"Duplicate content detected: {url} (original: {original_url})")
            
            if validation_result['advisory_content_detected']:
                self.logger.warning(f"Advisory content detected in: {url}")
            
            return processed
            
        except Exception as e:
            self.logger.error(f"Error processing content from {raw_content.get('url', 'unknown')}: {str(e)}")
            raise
    
    def _calculate_quality_score(self, validation_result: Dict, content_length: int, changes: Dict) -> float:
        """Calculate overall quality score"""
        score = 1.0
        
        # Penalize advisory content
        if validation_result['advisory_content_detected']:
            score -= 0.5
        
        # Penalize validation errors
        score -= len(validation_result['errors']) * 0.1
        
        # Reward completeness
        score += validation_result['completeness_score'] * 0.2
        
        # Reward factual nature
        score += validation_result['factual_score'] * 0.2
        
        # Penalize very short content
        if content_length < 100:
            score -= 0.3
        elif content_length < 500:
            score -= 0.1
        
        # Ensure score is within bounds
        return max(0.0, min(1.0, score))
    
    def get_processing_stats(self) -> Dict:
        """Get processing statistics"""
        return {
            'duplicate_detector': self.duplicate_detector.get_duplicate_stats(),
            'change_detector': {
                'tracked_urls': len(self.change_detector.previous_content)
            }
        }
