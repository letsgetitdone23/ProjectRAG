"""
Query Processing and Retrieval System for Mutual Fund FAQ Assistant
Handles query understanding, intent classification, and response generation
"""

import logging
import re
import json
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from storage.vector_store import VectorStoreManager
from llm.groq_client import create_groq_client
import numpy as np

# Try to import LLM clients
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

@dataclass
class QueryResult:
    """Result of query processing"""
    answer: str
    source_url: str
    last_updated: str
    confidence_score: float
    is_advisory: bool
    refusal_reason: Optional[str] = None
    context_used: List[str] = None
    processing_time_ms: float = 0.0

class QueryProcessor:
    """Processes user queries and generates responses"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Embedding model for query encoding
        self.embedding_model_name = config.get('embedding_model', 'sentence-transformers/all-MiniLM-L6-v2')
        self.embedding_model = None
        self._load_embedding_model()
        
        # LLM configuration
        self.llm_config = config.get('llm', {})
        self.llm_type = self.llm_config.get('type', 'groq')
        
        # Initialize LLM client
        self.llm_client = None
        self._initialize_llm_client()
        
        # Response constraints
        self.max_sentences = config.get('max_sentences', 3)
        self.require_source = config.get('require_source', True)
        self.facts_only = config.get('facts_only', True)
        
        # Advisory detection patterns
        self.advisory_patterns = [
            r'\b(invest|investment|investing)\b.*\b(advice|advise|recommendation|suggest)\b',
            r'\b(should|would|could|might)\b.*\b(invest|buy|sell|hold)\b',
            r'\b(best|better|worst|top|bottom)\b.*\b(fund|scheme|investment)\b',
            r'\b(good|bad|excellent|poor)\b.*\b(investment|return|performance)\b',
            r'\b(expect|anticipate|forecast|predict)\b.*\b(return|growth|performance)\b',
            r'\b(guarantee|assure|promise)\b.*\b(return|profit|gain)\b'
        ]
        
        # Mutual fund entity patterns
        self.entity_patterns = {
            'fund_names': [
                r'\b(nippon\s+india\s+(large\s+cap|flexi\s+cap|multi\s+asset\s+allocation)\s+fund)\b',
                r'\b(large\s+cap\s+fund|flexi\s+cap\s+fund|multi\s+asset\s+allocation\s+fund)\b'
            ],
            'amc_name': [r'\b(nippon\s+india\s+mutual\s+funds?)\b'],
            'metrics': [
                r'\b(nav|expense\s+ratio|exit\s+load|sip|aum|returns?)\b',
                r'\b(minimum\s+investment|lump\s+sum)\b'
            ],
            'time_periods': [
                r'\b(1\s+year|3\s+year|5\s+year|since\s+inception|monthly|quarterly|annually)\b'
            ]
        }
    
    def _load_embedding_model(self):
        """Load embedding model for query encoding"""
        try:
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            self.logger.info(f"Loaded embedding model: {self.embedding_model_name}")
        except Exception as e:
            self.logger.error(f"Failed to load embedding model: {str(e)}")
            raise
    
    def _initialize_llm_client(self):
        """Initialize LLM client based on configuration"""
        try:
            if self.llm_type == 'groq':
                self.llm_client = create_groq_client(self.llm_config)
                self.logger.info(f"Initialized Groq LLM client")
            elif self.llm_type == 'openai' and OPENAI_AVAILABLE:
                # Fallback to OpenAI if available
                self.llm_client = openai.OpenAI(api_key=self.llm_config.get('api_key'))
                self.logger.info(f"Initialized OpenAI LLM client")
            else:
                self.logger.warning(f"Unsupported LLM type: {self.llm_type}, using template responses only")
                self.llm_client = None
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM client: {str(e)}")
            self.llm_client = None
    
    def process_query(self, query: str, vector_store, max_retries: int = 3) -> QueryResult:
        """Main query processing pipeline"""
        start_time = datetime.now()
        
        try:
            self.logger.info(f"Processing query: {query[:100]}...")
            
            # Step 1: Query Understanding
            query_analysis = self._analyze_query(query)
            
            # Step 2: Advisory Content Detection
            advisory_result = self._detect_advisory_content(query)
            
            if advisory_result['is_advisory']:
                return self._create_advisory_refusal(query, advisory_result['reason'])
            
            # Step 3: Entity Extraction
            entities = self._extract_entities(query)
            
            # Step 4: Query Expansion
            expanded_query = self._expand_query(query, entities)
            
            # Step 5: Generate Query Embedding
            query_embedding = self._generate_query_embedding(expanded_query)
            
            # Step 6: Retrieve Relevant Chunks
            relevant_chunks = self._retrieve_relevant_chunks(query_embedding, vector_store, entities)
            
            if not relevant_chunks:
                return self._create_no_results_response(query)
            
            # Step 7: Generate Response
            response = self._generate_response(query, relevant_chunks, entities)
            
            # Step 8: Validate Response
            validated_response = self._validate_response(response, query)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = QueryResult(
                answer=validated_response['answer'],
                source_url=validated_response['source_url'],
                last_updated=validated_response['last_updated'],
                confidence_score=validated_response['confidence_score'],
                is_advisory=False,
                context_used=[chunk['content'] for chunk in relevant_chunks[:3]],
                processing_time_ms=processing_time
            )
            
            self.logger.info(f"Query processed successfully in {processing_time:.2f}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return self._create_error_response(query, str(e))
    
    def _analyze_query(self, query: str) -> Dict:
        """Analyze query for intent and type"""
        analysis = {
            'query_type': 'general',
            'intent': 'informational',
            'complexity': 'simple',
            'keywords': []
        }
        
        query_lower = query.lower()
        
        # Classify query type
        if any(word in query_lower for word in ['what', 'how', 'tell me', 'explain']):
            analysis['query_type'] = 'informational'
        elif any(word in query_lower for word in ['nav', 'expense', 'ratio', 'sip', 'minimum']):
            analysis['query_type'] = 'specific_metric'
        elif any(word in query_lower for word in ['performance', 'return', 'growth']):
            analysis['query_type'] = 'performance_related'
        elif any(word in query_lower for word in ['risk', 'safety', 'conservative']):
            analysis['query_type'] = 'risk_related'
        
        # Extract keywords
        words = re.findall(r'\b\w+\b', query_lower)
        analysis['keywords'] = [word for word in words if len(word) > 3]
        
        return analysis
    
    def _detect_advisory_content(self, query: str) -> Dict:
        """Detect if query contains advisory intent"""
        query_lower = query.lower()
        
        for pattern in self.advisory_patterns:
            if re.search(pattern, query_lower):
                return {
                    'is_advisory': True,
                    'reason': f"Query contains advisory pattern: {pattern}"
                }
        
        return {'is_advisory': False, 'reason': None}
    
    def _extract_entities(self, query: str) -> Dict:
        """Extract mutual fund entities from query"""
        entities = {
            'fund_names': [],
            'amc_name': None,
            'metrics': [],
            'time_periods': []
        }
        
        query_lower = query.lower()
        
        # Extract entities using patterns
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, query_lower)
                if matches:
                    if entity_type == 'amc_name':
                        entities[entity_type] = matches[0]
                    else:
                        entities[entity_type].extend(matches)
        
        # Remove duplicates
        for key in entities:
            if isinstance(entities[key], list):
                entities[key] = list(set(entities[key]))
        
        return entities
    
    def _expand_query(self, query: str, entities: Dict) -> str:
        """Expand query with relevant terminology"""
        expanded_terms = []
        
        # Add AMC name if not present
        if not entities['amc_name']:
            expanded_terms.append("Nippon India Mutual Funds")
        
        # Add fund-specific terms
        if entities['fund_names']:
            expanded_terms.extend(entities['fund_names'])
        
        # Add metric-specific terms
        metric_expansions = {
            'nav': 'net asset value',
            'sip': 'systematic investment plan',
            'aum': 'assets under management',
            'returns': 'performance returns'
        }
        
        for metric in entities['metrics']:
            if metric in metric_expansions:
                expanded_terms.append(metric_expansions[metric])
        
        # Combine original query with expansions
        if expanded_terms:
            expanded_query = f"{query} {' '.join(expanded_terms)}"
        else:
            expanded_query = query
        
        return expanded_query
    
    def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for query"""
        try:
            # Preprocess query
            processed_query = self._preprocess_query(query)
            
            # Generate embedding
            embedding = self.embedding_model.encode(processed_query)
            return embedding.tolist()
            
        except Exception as e:
            self.logger.error(f"Failed to generate query embedding: {str(e)}")
            raise
    
    def _preprocess_query(self, query: str) -> str:
        """Preprocess query for better embedding"""
        # Clean and normalize
        query = query.strip()
        query = ' '.join(query.split())  # Remove extra whitespace
        
        # Ensure reasonable length
        if len(query) > 512:
            query = query[:512]
        
        return query
    
    def _retrieve_relevant_chunks(self, query_embedding: List[float], vector_store, entities: Dict) -> List[Dict]:
        """Retrieve relevant chunks from vector store"""
        try:
            # Build filters based on entities
            filters = self._build_search_filters(entities)
            
            # Search vector store
            results = vector_store.search_similar(
                query_vector=query_embedding,
                top_k=10,
                filters=filters
            )
            
            # Filter and rank results
            filtered_results = self._filter_search_results(results, entities)
            
            return filtered_results
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve chunks: {str(e)}")
            return []
    
    def _build_search_filters(self, entities: Dict) -> Dict:
        """Build search filters based on extracted entities"""
        filters = {}
        
        # Filter by fund names if specified
        if entities['fund_names']:
            filters['scheme_name'] = entities['fund_names']
        
        # Filter by document types
        preferred_types = ['sid', 'factsheet', 'performance_page']
        filters['document_type'] = preferred_types
        
        return filters
    
    def _filter_search_results(self, results: List[Dict], entities: Dict) -> List[Dict]:
        """Filter and rank search results"""
        if not results:
            return []
        
        # Score results based on relevance
        scored_results = []
        
        for result in results:
            score = result['score']
            content = result['content'].lower()
            
            # Boost score for entity matches
            for fund_name in entities['fund_names']:
                if fund_name.lower() in content:
                    score += 0.1
            
            for metric in entities['metrics']:
                if metric.lower() in content:
                    score += 0.1
            
            # Boost for high-quality sources
            if result['document_type'] in ['sid', 'factsheet']:
                score += 0.05
            
            scored_results.append({
                **result,
                'relevance_score': score
            })
        
        # Sort by relevance score
        scored_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Return top results
        return scored_results[:5]
    
    def _generate_response(self, query: str, relevant_chunks: List[Dict], entities: Dict) -> Dict:
        """Generate response using LLM"""
        try:
            if self.llm_type == 'openai' and OPENAI_AVAILABLE:
                return self._generate_openai_response(query, relevant_chunks, entities)
            else:
                return self._generate_template_response(query, relevant_chunks, entities)
        prompt = self._create_prompt(query, context, entities)

        response = self.llm_client.chat.completions.create(
            model=self.llm_config.get('model', 'gpt-3.5-turbo'),
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides factual information about mutual funds. Never give investment advice."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.1
        )

        answer = response.choices[0].message.content.strip()
        best_source = self._select_best_source(relevant_chunks)

        return {
            'answer': answer,
            'source_url': best_source['source_url'],
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'confidence_score': self._calculate_confidence_score(relevant_chunks),
            'method': 'openai'
        }

    else:
        # Fallback to template-based response
        self.logger.warning("No LLM client available, using template response")
        return self._generate_template_response(query, relevant_chunks, entities)

def _generate_template_response(self, query: str, relevant_chunks: List[Dict], entities: Dict) -> Dict:
    """Generate response using template-based approach"""
    # Find most relevant chunk
    best_chunk = relevant_chunks[0]

    # Extract relevant information
    answer = self._extract_factual_answer(best_chunk, query, entities)

    return {
        'answer': answer,
        'source_url': best_chunk['source_url'],
        'last_updated': datetime.now().strftime('%Y-%m-%d'),
        'confidence_score': best_chunk['score'],
        'method': 'template'
    }

def _prepare_context(self, relevant_chunks: List[Dict]) -> str:
    """Prepare context from relevant chunks"""
    context_parts = []

    for chunk in relevant_chunks[:3]:  # Use top 3 chunks
        context_parts.append(chunk['content'])

    return "\n\n".join(context_parts)

def _create_prompt(self, query: str, context: str, entities: Dict) -> str:
    """Create prompt for LLM"""
    prompt = f"""
        
        # Extract relevant information
        answer = self._extract_factual_answer(best_chunk, query, entities)
        
        return {
            'answer': answer,
            'source_url': best_chunk['source_url'],
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'confidence_score': best_chunk['score'],
            'method': 'template'
        }
    
    def _prepare_context(self, relevant_chunks: List[Dict]) -> str:
        """Prepare context from relevant chunks"""
        context_parts = []
        
        for chunk in relevant_chunks[:3]:  # Use top 3 chunks
            context_parts.append(chunk['content'])
        
        return "\n\n".join(context_parts)
    
    def _create_prompt(self, query: str, context: str, entities: Dict) -> str:
        """Create prompt for LLM"""
        prompt = ("Based on the following context about Nippon India Mutual Funds, answer the user's question. "
                 "Provide only factual information, no investment advice. Keep your response under 3 sentences.\n\n"
                 f"Context:\n{context}\n\n"
                 f"Question: {query}\n\n"
                 "Answer:")
        return prompt
    
    def _extract_factual_answer(self, chunk: Dict, query: str, entities: Dict) -> str:
        """Extract factual answer from chunk"""
        content = chunk['content']
        
        # Simple extraction based on query type
        query_lower = query.lower()
        
        if 'nav' in query_lower:
            # Look for NAV information
            nav_match = re.search(r'nav[:\s]*₹?([0-9,.-]+)', content, re.IGNORECASE)
            if nav_match:
                return f"The NAV is ₹{nav_match.group(1)} as per the latest update."
        
        elif 'expense ratio' in query_lower:
            # Look for expense ratio
            expense_match = re.search(r'expense\s*ratio[:\s]*([0-9.]+%?)', content, re.IGNORECASE)
            if expense_match:
                return f"The expense ratio is {expense_match.group(1)}."
        
        elif 'sip' in query_lower:
            # Look for SIP information
            sip_match = re.search(r'minimum\s*sip[:\s]*₹?([0-9,]+)', content, re.IGNORECASE)
            if sip_match:
                return f"The minimum SIP amount is ₹{sip_match.group(1)}."
        
        # Fallback: return first relevant sentence
        sentences = content.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and any(word in sentence.lower() for word in query_lower.split() if len(word) > 3):
                return sentence + "."
        
        # Final fallback
        return "Please refer to the official fund documents for detailed information."
    
    def _select_best_source(self, relevant_chunks: List[Dict]) -> Dict:
        """Select the best source from relevant chunks"""
        if not relevant_chunks:
            return {'source_url': '', 'score': 0.0}
        
        # Prioritize by document type and score
        type_priority = {'sid': 3, 'factsheet': 2, 'performance_page': 2, 'amc_page': 1}
        
        best_chunk = relevant_chunks[0]
        best_score = 0
        
        for chunk in relevant_chunks:
            doc_type = chunk.get('document_type', '')
            priority = type_priority.get(doc_type, 0)
            combined_score = chunk['score'] + (priority * 0.1)
            
            if combined_score > best_score:
                best_score = combined_score
                best_chunk = chunk
        
        return best_chunk
    
    def _calculate_confidence_score(self, relevant_chunks: List[Dict]) -> float:
        """Calculate confidence score based on search results"""
        if not relevant_chunks:
            return 0.0
        
        # Use top result's score as base confidence
        base_confidence = relevant_chunks[0]['score']
        
        # Adjust based on number of relevant results
        result_count_factor = min(len(relevant_chunks) / 5, 1.0)
        
        # Adjust based on source quality
        source_quality_factor = 1.0
        if relevant_chunks[0].get('document_type') in ['sid', 'factsheet']:
            source_quality_factor = 1.1
        
        confidence = base_confidence * result_count_factor * source_quality_factor
        return min(confidence, 1.0)
    
    def _validate_response(self, response: Dict, query: str) -> Dict:
        """Validate response for compliance"""
        answer = response['answer']
        
        # Check length
        sentences = answer.split('.')
        if len(sentences) > self.max_sentences:
            answer = '. '.join(sentences[:self.max_sentences]) + '.'
        
        # Check for advisory content
        for pattern in self.advisory_patterns:
            if re.search(pattern, answer.lower()):
                answer = self._remove_advisory_content(answer)
        
        # Ensure factual nature
        if not any(indicator in answer.lower() for indicator in ['nav', 'ratio', '₹', '%', 'date', 'fund']):
            answer = "Please refer to the official fund documents for specific information."
        
        response['answer'] = answer
        return response
    
    def _remove_advisory_content(self, text: str) -> str:
        """Remove advisory content from text"""
        # Replace advisory phrases with factual alternatives
        advisory_replacements = {
            r'\b(should|would|could|might)\s+(invest|buy|sell|hold)\b': 'consider the fund information',
            r'\b(best|better|worst)\s+(fund|scheme|investment)\b': 'fund options available',
            r'\b(good|bad|excellent|poor)\s+(investment|return)\b': 'investment performance data'
        }
        
        for pattern, replacement in advisory_replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text
    
    def _create_advisory_refusal(self, query: str, reason: str) -> QueryResult:
        """Create advisory refusal response"""
        refusal_message = "I can only provide factual information about mutual funds and cannot give investment advice. Please consult a financial advisor for personalized recommendations."
        
        return QueryResult(
            answer=refusal_message,
            source_url="https://www.amfiindia.com/",
            last_updated=datetime.now().strftime('%Y-%m-%d'),
            confidence_score=1.0,
            is_advisory=True,
            refusal_reason=reason
        )
    
    def _create_no_results_response(self, query: str) -> QueryResult:
        """Create response when no results found"""
        no_results_message = "I couldn't find specific information about your query. Please check the official fund documents or contact the fund house for detailed information."
        
        return QueryResult(
            answer=no_results_message,
            source_url="https://www.nipponindiaim.com/",
            last_updated=datetime.now().strftime('%Y-%m-%d'),
            confidence_score=0.1,
            is_advisory=False
        )
    
    def _create_error_response(self, query: str, error: str) -> QueryResult:
        """Create error response"""
        error_message = "I'm experiencing technical difficulties. Please try again later or refer to the official fund documents."
        
        return QueryResult(
            answer=error_message,
            source_url="https://www.nipponindiaim.com/",
            last_updated=datetime.now().strftime('%Y-%m-%d'),
            confidence_score=0.0,
            is_advisory=False
        )
    
    def _generate_fallback_response(self, query: str, relevant_chunks: List[Dict]) -> Dict:
        """Generate fallback response when LLM fails"""
        if relevant_chunks:
            best_chunk = relevant_chunks[0]
            return {
                'answer': "Please refer to the official fund documents for detailed information about your query.",
                'source_url': best_chunk['source_url'],
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'confidence_score': 0.3,
                'method': 'fallback'
            }
        else:
            return {
                'answer': "I couldn't find relevant information. Please check the official fund documents.",
                'source_url': "https://www.nipponindiaim.com/",
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'confidence_score': 0.1,
                'method': 'fallback'
            }
