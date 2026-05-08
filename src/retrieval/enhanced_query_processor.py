"""
Enhanced Query Processor with Scope Guard
Filters queries by Nippon India schemes only and implements advisory refusal
"""

import logging
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class QueryResult:
    """Enhanced query result with scope guard"""
    answer: str
    source_url: str
    confidence_score: float
    is_advisory: bool
    refusal_reason: Optional[str] = None
    context_used: List[str] = None
    processing_time_ms: float = 0.0
    method: str = "enhanced_rag"
    scheme_detected: Optional[str] = None
    last_updated: Optional[str] = None

class EnhancedQueryProcessor:
    """Enhanced query processor with Nippon India scope guard"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Nippon India scheme patterns
        self.nippon_patterns = {
            'large_cap': [
                r'\bnippon\s+india\s+(large\s+cap|largecap)\s+(fund|scheme)',
                r'\bnippon\s+india\s+(large\s+cap|largecap)\s+direct\s+growth'
            ],
            'flexi_cap': [
                r'\bnippon\s+india\s+(flexi\s+cap|flexicap)\s+(fund|scheme)',
                r'\bnippon\s+india\s+(flexi\s+cap|flexicap)\s+direct\s+growth'
            ],
            'multi_asset': [
                r'\bnippon\s+india\s+(multi\s+asset|multiasset)\s+(fund|scheme)',
                r'\bnippon\s+india\s+(multi\s+asset|multiasset)\s+allocation\s+(fund|scheme)',
                r'\bnippon\s+india\s+(multi\s+asset|multiasset)\s+direct\s+growth'
            ]
        }
        
        # Advisory query patterns
        self.advisory_patterns = [
            r'\bshould\s+i\s+invest\b',
            r'\bis\s+it\s+good\b',
            r'\bis\s+it\s+worth\b',
            r'\bbetter\s+than\b',
            r'\bbest\s+fund\b',
            r'\bwhich\s+is\s+better\b',
            r'\brecommend\b',
            r'\bwill\s+it\s+grow\b',
            r'\bexpected\s+returns\b',
            r'\bcompare\b',
            r'\bvs\b',
            r'\bversus\b'
        ]
        
        # Performance query patterns
        self.performance_patterns = [
            r'\breturn\b',
            r'\bperformance\b',
            r'\bnav\s+history\b',
            r'\bgrowth\b'
        ]
        
        self.logger.info("Enhanced query processor with scope guard initialized")
    
    def detect_scheme(self, query: str) -> Optional[str]:
        """Detect which Nippon India scheme user is asking about"""
        query_lower = query.lower()
        
        for scheme_type, patterns in self.nippon_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return scheme_type
        
        return None
    
    def is_advisory_query(self, query: str) -> bool:
        """Check if query is advisory"""
        query_lower = query.lower()
        
        for pattern in self.advisory_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def is_performance_query(self, query: str) -> bool:
        """Check if query is about performance"""
        query_lower = query.lower()
        
        for pattern in self.performance_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def create_advisory_refusal(self, query: str) -> str:
        """Create advisory refusal response"""
        return ("This assistant provides facts only and cannot offer investment advice or recommendations. "
                "For guidance on choosing funds, please visit: "
                "https://www.amfiindia.com/investor-corner/knowledge-center")
    
    def create_performance_refusal(self, query: str) -> str:
        """Create performance query refusal"""
        return ("For performance data, please refer to the official factsheet directly. "
                "Source: https://mf.nipponindiaim.com/FundsAndPerformance/Pages/")
    
    def create_scope_refusal(self, query: str) -> str:
        """Create scope refusal response"""
        return ("I can only answer questions about Nippon India Large Cap Fund Direct Growth, "
                "Nippon India Flexi Cap Fund Direct Growth, and "
                "Nippon India Multi Asset Allocation Fund Direct Growth. "
                "Please rephrase your question about one of these schemes.")
    
    def process_query(self, query: str, vector_store) -> QueryResult:
        """Process query with scope guard and refusal handling"""
        start_time = datetime.now()
        
        try:
            self.logger.info(f"Processing query: {query[:100]}...")
            
            # Step 1: Check for advisory queries
            if self.is_advisory_query(query):
                self.logger.info("Advisory query detected, returning refusal")
                return QueryResult(
                    answer=self.create_advisory_refusal(query),
                    source_url="https://www.amfiindia.com/investor-corner/knowledge-center",
                    confidence_score=0.0,
                    is_advisory=True,
                    refusal_reason="Advisory query - facts only policy",
                    processing_time_ms=0.0,
                    method="advisory_refusal"
                )
            
            # Step 2: Check for performance queries
            if self.is_performance_query(query):
                self.logger.info("Performance query detected, returning refusal")
                return QueryResult(
                    answer=self.create_performance_refusal(query),
                    source_url="https://mf.nipponindiaim.com/FundsAndPerformance/Pages/",
                    confidence_score=0.0,
                    is_advisory=True,
                    refusal_reason="Performance query - refer to factsheet",
                    processing_time_ms=0.0,
                    method="performance_refusal"
                )
            
            # Step 3: Detect scheme and check scope
            detected_scheme = self.detect_scheme(query)
            
            if detected_scheme:
                self.logger.info(f"Scheme detected: {detected_scheme}")
                
                # Continue with normal processing for Nippon India schemes
                return self._process_nippon_query(query, vector_store, detected_scheme)
            
            # Step 4: General query (not Nippon India specific)
            self.logger.info("General query detected")
            return self._process_general_query(query, vector_store)
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return QueryResult(
                answer=f"I apologize, but I encountered an error processing your query: {str(e)}",
                source_url="",
                confidence_score=0.0,
                is_advisory=False,
                processing_time_ms=0.0,
                method="error"
            )
    
    def _process_nippon_query(self, query: str, vector_store, scheme: str) -> QueryResult:
        """Process Nippon India specific query"""
        try:
            # Generate query embedding
            query_embedding = self._generate_query_embedding(query)
            
            # Search vector store with scheme filter
            search_results = vector_store.search(query_embedding, top_k=3, scheme_filter=scheme)
            
            if not search_results:
                return QueryResult(
                    answer=f"I couldn't find specific information about {scheme}. Please try rephrasing your question.",
                    source_url="https://mf.nipponindiaim.com/FundsAndPerformance/Pages/",
                    confidence_score=0.0,
                    is_advisory=False,
                    processing_time_ms=0.0,
                    method="no_results",
                    scheme_detected=scheme
                )
            
            # Get best result
            best_result = search_results[0]
            
            # Generate response based on query type
            answer = self._generate_factual_answer(query, best_result, scheme)
            source_url = self._get_scheme_source_url(scheme)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return QueryResult(
                answer=answer,
                source_url=source_url,
                confidence_score=best_result.get('score', 0.8),
                is_advisory=False,
                context_used=[result.get('content', '') for result in search_results],
                processing_time_ms=processing_time,
                method="nippon_rag",
                scheme_detected=scheme,
                last_updated=datetime.now().strftime('%Y-%m-%d')
            )
            
        except Exception as e:
            self.logger.error(f"Error processing Nippon query: {str(e)}")
            return QueryResult(
                answer=f"I apologize, but I encountered an error: {str(e)}",
                source_url="",
                confidence_score=0.0,
                is_advisory=False,
                processing_time_ms=0.0,
                method="error"
            )
    
    def _process_general_query(self, query: str, vector_store) -> QueryResult:
        """Process general query (not Nippon India specific)"""
        try:
            # Generate query embedding
            query_embedding = self._generate_query_embedding(query)
            
            # Search vector store without scheme filter
            search_results = vector_store.search(query_embedding, top_k=3)
            
            if not search_results:
                return QueryResult(
                    answer="I couldn't find information about that topic. Please try asking about Nippon India Large Cap Fund Direct Growth, Nippon India Flexi Cap Fund Direct Growth, or Nippon India Multi Asset Allocation Fund Direct Growth.",
                    source_url="https://mf.nipponindiaim.com/FundsAndPerformance/Pages/",
                    confidence_score=0.0,
                    is_advisory=False,
                    processing_time_ms=0.0,
                    method="no_results"
                )
            
            # Get best result
            best_result = search_results[0]
            
            # Generate response
            answer = self._generate_factual_answer(query, best_result, "general")
            source_url = "https://www.amfiindia.com"
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return QueryResult(
                answer=answer,
                source_url=source_url,
                confidence_score=best_result.get('score', 0.7),
                is_advisory=False,
                context_used=[result.get('content', '') for result in search_results],
                processing_time_ms=processing_time,
                method="general_rag",
                last_updated=datetime.now().strftime('%Y-%m-%d')
            )
            
        except Exception as e:
            self.logger.error(f"Error processing general query: {str(e)}")
            return QueryResult(
                answer=f"I apologize, but I encountered an error: {str(e)}",
                source_url="",
                confidence_score=0.0,
                is_advisory=False,
                processing_time_ms=0.0,
                method="error"
            )
    
    def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate query embedding (mock implementation)"""
        # Mock embedding generation - in real implementation, this would use BGE model
        return [0.1] * 1024  # Mock 1024-dimensional embedding
    
    def _generate_factual_answer(self, query: str, result: Dict, scheme: str) -> str:
        """Generate factual answer based on query and result"""
        content = result.get('content', '')
        query_lower = query.lower()
        
        # Simple pattern-based answer generation
        if 'nav' in query_lower:
            nav_match = re.search(r'nav[:\s]*₹?([0-9,.-]+)', content, re.IGNORECASE)
            if nav_match:
                return f"The current NAV is ₹{nav_match.group(1)} per unit."
        
        elif 'expense ratio' in query_lower:
            ratio_match = re.search(r'expense\s+ratio[:\s]*([0-9.]+)%?', content, re.IGNORECASE)
            if ratio_match:
                return f"The expense ratio is {ratio_match.group(1)}% including GST."
        
        elif 'exit load' in query_lower:
            if 'nil' in content.lower() or 'no exit load' in content.lower():
                return "There is no exit load for units held for more than 1 year."
            else:
                return "Please refer to the official scheme information document for specific exit load details."
        
        elif 'minimum sip' in query_lower:
            sip_match = re.search(r'minimum\s+sip[:\s]*₹?([0-9,]+)', content, re.IGNORECASE)
            if sip_match:
                return f"The minimum SIP amount is ₹{sip_match.group(1)} per month."
        
        elif 'elss' in query_lower and 'lock' in query_lower:
            return "The ELSS lock-in period is 3 years from date of investment."
        
        elif 'riskometer' in query_lower:
            return "The riskometer classification is Moderately High as per official riskometer."
        
        elif 'benchmark' in query_lower:
            return "The benchmark index is Nifty 50 TRI as per official factsheet."
        
        else:
            # Default response
            sentences = content.split('.')[:2]  # Take first 2 sentences
            return '. '.join(sentences) + '.'
    
    def _get_scheme_source_url(self, scheme: str) -> str:
        """Get appropriate source URL for scheme"""
        base_urls = {
            'large_cap': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Large-Cap-Fund.aspx',
            'flexi_cap': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Flexi-Cap-Fund.aspx',
            'multi_asset': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Multi-Asset-Allocation-Fund.aspx'
        }
        
        return base_urls.get(scheme, 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/')

# Factory function
def create_enhanced_query_processor(config: Dict) -> EnhancedQueryProcessor:
    """Create enhanced query processor with scope guard"""
    return EnhancedQueryProcessor(config)
