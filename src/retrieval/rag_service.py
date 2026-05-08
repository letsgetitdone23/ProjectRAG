"""
RAG Service - Main service for Retrieval-Augmented Generation
Integrates query processing, vector search, and response generation
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from .query_processor import QueryProcessor, QueryResult
from storage.vector_store import VectorStoreManager

@dataclass
class RAGConfig:
    """Configuration for RAG service"""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_sentences: int = 3
    require_source: bool = True
    facts_only: bool = True
    confidence_threshold: float = 0.3
    
    # LLM configuration
    llm_type: str = "openai"
    llm_model: str = "gpt-3.5-turbo"
    max_tokens: int = 200
    temperature: float = 0.1

class RAGService:
    """Main RAG service for mutual fund FAQ assistant"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.query_processor = QueryProcessor(config.get('query_processor', {}))
        
        # Vector store configuration
        vector_store_config = config.get('vector_store', {})
        self.vector_store = VectorStoreManager(vector_store_config)
        
        # Service metadata
        self.service_start_time = datetime.now()
        self.query_count = 0
        self.advisory_query_count = 0
        
        self.logger.info("RAG Service initialized successfully")
    
    def process_query(self, query: str, user_id: Optional[str] = None) -> QueryResult:
        """Process user query and return response"""
        self.query_count += 1
        
        try:
            self.logger.info(f"Processing query #{self.query_count}: {query[:100]}...")
            
            # Process query through the pipeline
            result = self.query_processor.process_query(query, self.vector_store)
            
            # Track advisory queries
            if result.is_advisory:
                self.advisory_query_count += 1
                self.logger.info(f"Advisory query detected and refused: {result.refusal_reason}")
            
            # Log successful processing
            self.logger.info(f"Query processed successfully. Confidence: {result.confidence_score:.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return self._create_error_response(query, str(e))
    
    def get_service_stats(self) -> Dict:
        """Get service statistics"""
        uptime = datetime.now() - self.service_start_time
        
        try:
            vector_store_stats = self.vector_store.get_store_stats()
        except Exception as e:
            self.logger.error(f"Failed to get vector store stats: {str(e)}")
            vector_store_stats = {}
        
        stats = {
            'service_info': {
                'uptime_seconds': uptime.total_seconds(),
                'queries_processed': self.query_count,
                'advisory_queries_refused': self.advisory_query_count,
                'advisory_refusal_rate': self.advisory_query_count / max(self.query_count, 1),
                'start_time': self.service_start_time.isoformat()
            },
            'vector_store': vector_store_stats,
            'configuration': {
                'embedding_model': self.query_processor.embedding_model_name,
                'max_sentences': self.query_processor.max_sentences,
                'facts_only': self.query_processor.facts_only,
                'llm_type': self.query_processor.llm_type
            }
        }
        
        return stats
    
    def health_check(self) -> Dict:
        """Perform health check"""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'components': {}
        }
        
        try:
            # Check query processor
            test_query = "What is NAV?"
            test_result = self.query_processor._generate_query_embedding(test_query)
            health_status['components']['query_processor'] = {
                'status': 'healthy' if test_result else 'unhealthy',
                'embedding_dimension': len(test_result) if test_result else 0
            }
        except Exception as e:
            health_status['components']['query_processor'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        try:
            # Check vector store
            vector_stats = self.vector_store.get_store_stats()
            health_status['components']['vector_store'] = {
                'status': 'healthy',
                'total_vectors': vector_stats.get('total_vectors', 0)
            }
        except Exception as e:
            health_status['components']['vector_store'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # Overall status
        component_statuses = [comp['status'] for comp in health_status['components'].values()]
        if any(status == 'unhealthy' for status in component_statuses):
            health_status['status'] = 'degraded'
        
        return health_status
    
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

class MultiThreadRAGService:
    """RAG Service with multi-thread support"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Create thread-specific RAG services
        self.thread_services = {}
        self.default_service = RAGService(config)
        
        self.logger.info("Multi-thread RAG Service initialized")
    
    def get_service_for_thread(self, thread_id: str) -> RAGService:
        """Get or create RAG service for specific thread"""
        if thread_id not in self.thread_services:
            # Create service for this thread
            thread_config = self.config.copy()
            thread_config['thread_id'] = thread_id
            
            self.thread_services[thread_id] = RAGService(thread_config)
            self.logger.info(f"Created RAG service for thread: {thread_id}")
        
        return self.thread_services[thread_id]
    
    def process_query(self, query: str, thread_id: Optional[str] = None, user_id: Optional[str] = None) -> QueryResult:
        """Process query with thread support"""
        if thread_id:
            service = self.get_service_for_thread(thread_id)
        else:
            service = self.default_service
        
        return service.process_query(query, user_id)
    
    def get_thread_stats(self, thread_id: Optional[str] = None) -> Dict:
        """Get statistics for specific thread or all threads"""
        if thread_id:
            if thread_id in self.thread_services:
                return self.thread_services[thread_id].get_service_stats()
            else:
                return {'error': f'Thread {thread_id} not found'}
        else:
            # Aggregate stats from all threads
            all_stats = {
                'threads': {},
                'total_queries': 0,
                'total_advisory_queries': 0,
                'active_threads': len(self.thread_services)
            }
            
            for tid, service in self.thread_services.items():
                stats = service.get_service_stats()
                all_stats['threads'][tid] = stats
                all_stats['total_queries'] += stats['service_info']['queries_processed']
                all_stats['total_advisory_queries'] += stats['service_info']['advisory_queries_refused']
            
            # Add default service stats
            default_stats = self.default_service.get_service_stats()
            all_stats['total_queries'] += default_stats['service_info']['queries_processed']
            all_stats['total_advisory_queries'] += default_stats['service_info']['advisory_queries_refused']
            
            return all_stats
    
    def cleanup_thread(self, thread_id: str) -> bool:
        """Clean up thread-specific service"""
        if thread_id in self.thread_services:
            del self.thread_services[thread_id]
            self.logger.info(f"Cleaned up thread: {thread_id}")
            return True
        return False
    
    def health_check(self) -> Dict:
        """Health check for multi-thread service"""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'components': {
                'default_service': self.default_service.health_check(),
                'thread_services': {
                    'active_threads': len(self.thread_services),
                    'thread_ids': list(self.thread_services.keys())
                }
            }
        }
        
        # Check individual thread services
        thread_health = {}
        for thread_id, service in self.thread_services.items():
            try:
                thread_health[thread_id] = service.health_check()
            except Exception as e:
                thread_health[thread_id] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
        
        health_status['components']['thread_services']['thread_details'] = thread_health
        
        # Overall status
        if health_status['components']['default_service']['status'] != 'healthy':
            health_status['status'] = 'degraded'
        
        return health_status

# Factory function
def create_rag_service(config: Dict, multi_thread: bool = False) -> RAGService:
    """Create RAG service instance"""
    if multi_thread:
        return MultiThreadRAGService(config)
    else:
        return RAGService(config)
