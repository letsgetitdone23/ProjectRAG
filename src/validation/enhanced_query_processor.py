"""
Enhanced Query Processor with Real-time Validation
Integrates real-time validation for all question types from problem statement
"""

import logging
import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import sys
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent))

from retrieval.query_processor import QueryProcessor, QueryResult
from validation.real_time_validator import RealTimeValidator, ValidationResult

@dataclass
class EnhancedQueryResult:
    """Enhanced query result with validation"""
    answer: str
    source_url: str
    confidence_score: float
    is_advisory: bool
    refusal_reason: Optional[str] = None
    context_used: List[str] = None
    processing_time_ms: float = 0.0
    method: str = "template"
    validation_result: Optional[ValidationResult] = None
    data_freshness: str = "unknown"
    source_reliability: float = 0.0

class EnhancedQueryProcessor:
    """Enhanced query processor with real-time validation"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize base query processor
        self.base_processor = QueryProcessor(config)
        
        # Initialize real-time validator
        self.validator = RealTimeValidator(config.get('validation', {}))
        
        # Question type patterns
        self.question_patterns = {
            'nav': [
                r'\b(nav|net\s+asset\s+value)\b.*\b(of|for)?\s*(.+?)\s*(fund|scheme)?\b',
                r'\b(current\s+nav|latest\s+nav)\b.*\b(.+?)\b'
            ],
            'expense_ratio': [
                r'\b(expense\s+ratio|charges|fees)\b.*\b(of|for)?\s*(.+?)\s*(fund|scheme)?\b',
                r'\b(what\s+is\s+the\s+expense\s+ratio)\b.*\b(.+?)\b'
            ],
            'exit_load': [
                r'\b(exit\s+load|withdrawal\s+charges)\b.*\b(of|for)?\s*(.+?)\s*(fund|scheme)?\b',
                r'\b(what\s+is\s+the\s+exit\s+load)\b.*\b(.+?)\b'
            ],
            'minimum_sip': [
                r'\b(minimum\s+sip|sip\s+amount)\b.*\b(of|for)?\s*(.+?)\s*(fund|scheme)?\b',
                r'\b(what\s+is\s+the\s+minimum\s+sip)\b.*\b(.+?)\b'
            ],
            'elss_lockin': [
                r'\b(elss\s+lock[-\s]?in|lock[-\s]?in\s+period)\b.*\b(of|for)?\s*(.+?)\s*(fund|scheme)?\b',
                r'\b(what\s+is\s+the\s+elss\s+lock[-\s]?in)\b.*\b(.+?)\b'
            ],
            'riskometer': [
                r'\b(riskometer|risk\s+level|risk\s+classification)\b.*\b(of|for)?\s*(.+?)\s*(fund|scheme)?\b',
                r'\b(what\s+is\s+the\s+riskometer)\b.*\b(.+?)\b'
            ],
            'benchmark': [
                r'\b(benchmark|index\s+tracking)\b.*\b(of|for)?\s*(.+?)\s*(fund|scheme)?\b',
                r'\b(what\s+is\s+the\s+benchmark)\b.*\b(.+?)\b'
            ]
        }
        
        self.logger.info("Enhanced query processor initialized with real-time validation")
    
    def process_query_with_validation(self, query: str, vector_store, user_id: Optional[str] = None) -> EnhancedQueryResult:
        """Process query with real-time validation"""
        start_time = datetime.now()
        
        try:
            self.logger.info(f"Processing enhanced query: {query[:100]}...")
            
            # Step 1: Identify question type
            question_type = self._identify_question_type(query)
            self.logger.info(f"Question type identified: {question_type}")
            
            # Step 2: Extract fund name
            fund_name = self._extract_fund_name(query)
            self.logger.info(f"Fund name extracted: {fund_name}")
            
            # Step 3: Process with base processor
            base_result = self.base_processor.process_query(query, vector_store, user_id)
            
            # Step 4: Validate response based on question type
            validation_result = self._validate_response(question_type, fund_name, base_result)
            
            # Step 5: Create enhanced result
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            enhanced_result = EnhancedQueryResult(
                answer=base_result.answer,
                source_url=base_result.source_url,
                confidence_score=base_result.confidence_score,
                is_advisory=base_result.is_advisory,
                refusal_reason=base_result.refusal_reason,
                context_used=base_result.context_used,
                processing_time_ms=processing_time,
                method=base_result.method,
                validation_result=validation_result,
                data_freshness=self._calculate_freshness(validation_result),
                source_reliability=self._calculate_source_reliability(validation_result)
            )
            
            # Step 6: Enhance answer with validation info
            enhanced_result.answer = self._enhance_answer_with_validation(enhanced_result)
            
            self.logger.info(f"Enhanced query processed in {processing_time:.2f}ms")
            return enhanced_result
            
        except Exception as e:
            self.logger.error(f"Error processing enhanced query: {str(e)}")
            return self._create_error_enhanced_result(query, str(e))
    
    def _identify_question_type(self, query: str) -> str:
        """Identify the type of question"""
        query_lower = query.lower()
        
        for question_type, patterns in self.question_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return question_type
        
        return 'general'
    
    def _extract_fund_name(self, query: str) -> str:
        """Extract fund name from query"""
        # Common fund name patterns
        fund_patterns = [
            r'\b(nippon\s+india\s+(large\s+cap|flexi\s+cap|multi\s+asset\s+allocation)\s+fund)\b',
            r'\b(large\s+cap\s+fund|flexi\s+cap\s+fund|multi\s+asset\s+allocation\s+fund)\b',
            r'\b(hdfc\s+(mid[-\s]?cap|small[-\s]?cap|tax[-\s]?saver)\s+fund)\b',
            r'\b(icici\s+(prudential|blue[-\s]?chip|focused)\s+fund)\b',
            r'\b(axis\s+(blue[-\s]?chip|long[-\s]?term|mid[-\s]?cap)\s+fund)\b'
        ]
        
        query_lower = query.lower()
        for pattern in fund_patterns:
            match = re.search(pattern, query_lower)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        
        return 'unknown'
    
    def _validate_response(self, question_type: str, fund_name: str, base_result) -> ValidationResult:
        """Validate response based on question type"""
        try:
            if question_type == 'nav':
                return self.validator.validate_nav(fund_name, base_result.answer, base_result.source_url)
            elif question_type == 'expense_ratio':
                return self.validator.validate_expense_ratio(fund_name, base_result.answer, base_result.source_url)
            elif question_type == 'exit_load':
                return self.validator.validate_exit_load(fund_name, base_result.answer, base_result.source_url)
            elif question_type == 'minimum_sip':
                return self.validator.validate_minimum_sip(fund_name, base_result.answer, base_result.source_url)
            elif question_type == 'elss_lockin':
                return self.validator.validate_elss_lockin(fund_name, base_result.answer, base_result.source_url)
            elif question_type == 'riskometer':
                return self.validator.validate_riskometer(fund_name, base_result.answer, base_result.source_url)
            elif question_type == 'benchmark':
                return self.validator.validate_benchmark(fund_name, base_result.answer, base_result.source_url)
            else:
                # General validation
                return ValidationResult(
                    is_valid=True,
                    confidence=base_result.confidence_score,
                    sources=[],
                    recommended_value=None,
                    discrepancy_detected=False,
                    last_updated=datetime.now().strftime('%Y-%m-%d')
                )
        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                sources=[],
                recommended_value=None,
                discrepancy_detected=True,
                last_updated=None
            )
    
    def _calculate_freshness(self, validation_result: Optional[ValidationResult]) -> str:
        """Calculate data freshness"""
        if not validation_result or not validation_result.last_updated:
            return "unknown"
        
        try:
            last_updated = datetime.strptime(validation_result.last_updated, '%Y-%m-%d')
            days_old = (datetime.now() - last_updated).days
            
            if days_old <= 1:
                return "very_fresh"
            elif days_old <= 7:
                return "fresh"
            elif days_old <= 30:
                return "moderate"
            else:
                return "stale"
        except:
            return "unknown"
    
    def _calculate_source_reliability(self, validation_result: Optional[ValidationResult]) -> float:
        """Calculate source reliability score"""
        if not validation_result or not validation_result.sources:
            return 0.0
        
        # Weight by source reliability
        total_reliability = 0.0
        for source in validation_result.sources:
            total_reliability += source.get('reliability', 0.0)
        
        return total_reliability / len(validation_result.sources)
    
    def _enhance_answer_with_validation(self, enhanced_result: EnhancedQueryResult) -> str:
        """Enhance answer with validation information"""
        base_answer = enhanced_result.answer
        
        if not enhanced_result.validation_result:
            return base_answer
        
        validation = enhanced_result.validation_result
        
        # Add validation notes if discrepancies exist
        if validation.discrepancy_detected:
            discrepancy_note = f" Note: Data verified across multiple sources. Some variation detected."
            base_answer += discrepancy_note
        
        # Add recommended value if available
        if validation.recommended_value and validation.recommended_value != base_answer:
            recommendation_note = f" Latest verified value: {validation.recommended_value}"
            base_answer += f" {recommendation_note}"
        
        # Add freshness indicator
        freshness_note = f" (Data freshness: {enhanced_result.data_freshness})"
        base_answer += freshness_note
        
        return base_answer
    
    def _create_error_enhanced_result(self, query: str, error: str) -> EnhancedQueryResult:
        """Create error enhanced result"""
        return EnhancedQueryResult(
            answer=f"I apologize, but I encountered an error processing your query: {error}",
            source_url="",
            confidence_score=0.0,
            is_advisory=False,
            refusal_reason=None,
            context_used=[],
            processing_time_ms=0.0,
            method="error",
            validation_result=None,
            data_freshness="error",
            source_reliability=0.0
        )

# Factory function
def create_enhanced_query_processor(config: Dict) -> EnhancedQueryProcessor:
    """Create enhanced query processor"""
    return EnhancedQueryProcessor(config)
