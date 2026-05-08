"""
API Gateway for Multi-thread RAG Service - Fixed Version
Provides REST API interface with session management and load balancing
"""

import logging
import json
import uuid
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import asyncio
from functools import wraps
import sys

# Import enhanced query processor
sys.path.append(str(Path(__file__).parent.parent))
from retrieval.enhanced_query_processor import create_enhanced_query_processor

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Import session management components
from session.session_manager import SessionManager
from session.thread_pool import ThreadPoolManager
from session.context_manager import ContextManager
from session.session_persistence import SessionPersistenceManager
from session.load_balancer import LoadBalancer

# Pydantic models for API
class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    user_id: Optional[str] = Field(None, description="User identifier")
    thread_id: Optional[str] = Field(None, description="Thread identifier for session continuity")
    context: Optional[List[Dict]] = Field(None, description="Previous conversation context")
    session_id: Optional[str] = Field(None, description="Session identifier")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Assistant response")
    source_url: str = Field(..., description="Source URL for citation")
    confidence: float = Field(..., description="Confidence score")
    thread_id: str = Field(..., description="Thread identifier")
    session_id: str = Field(..., description="Session identifier")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    context_length: int = Field(..., description="Context window size")

class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status")
    timestamp: str = Field(..., description="Health check timestamp")
    active_threads: int = Field(..., description="Number of active threads")
    pending_queries: int = Field(..., description="Number of pending queries")

class APIGateway:
    """Main API Gateway for RAG service"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.session_manager = SessionManager(config.get('session', {}))
        self.thread_pool = ThreadPoolManager(config.get('thread_pool', {}))
        self.context_manager = ContextManager(config.get('context', {}))
        self.persistence_manager = SessionPersistenceManager(config.get('persistence', {}))
        self.load_balancer = LoadBalancer(config.get('load_balancer', {}))
        
        # Initialize RAG service
        from retrieval.rag_service import RAGService
        self.rag_service = RAGService(config.get('rag_config', {}))
        
        # Service metadata
        self.service_start_time = datetime.now()
        self.query_count = 0
        self.active_sessions = {}
        
        self.logger.info("API Gateway initialized successfully")
    
    def create_api(self) -> FastAPI:
        """Create FastAPI application"""
        app = FastAPI(
            title="Mutual Fund RAG API",
            description="Facts-only mutual fund FAQ assistant with real-time validation",
            version="1.0.0"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Define endpoints
        @app.post("/api/chat", response_model=ChatResponse)
        async def chat_endpoint(request: ChatRequest):
            """Process chat message"""
            return await self.process_chat_request(request)
        
        @app.get("/api/health", response_model=HealthResponse)
        async def health_endpoint():
            """Health check endpoint"""
            return await self.get_health_status()
        
        @app.get("/api/stats")
        async def stats_endpoint():
            """Get service statistics"""
            return await self.get_service_stats()
        
        @app.get("/")
        async def root_endpoint():
            """Root endpoint"""
            return {
                "message": "Mutual Fund RAG API",
                "version": "1.0.0",
                "status": "running",
                "endpoints": {
                    "chat": "/api/chat",
                    "health": "/api/health",
                    "stats": "/api/stats"
                }
            }
        
        return app
    
    async def process_chat_request(self, request: ChatRequest) -> ChatResponse:
        """Process chat request with RAG service"""
        start_time = time.time()
        
        try:
            self.query_count += 1
            self.logger.info(f"Processing query #{self.query_count}: {request.message[:100]}...")
            
            # Get or create session
            session_id = request.session_id or str(uuid.uuid4())
            thread_id = request.thread_id or str(uuid.uuid4())
            
            # Get or create thread
            thread = await self.get_or_create_thread(thread_id, request.user_id)
            
            # Get context
            context = request.context or []
            
            # Process query with RAG service
            rag_result = self.rag_service.process_query(request.message)
            
            # Update context
            await self.context_manager.update_context(thread_id, rag_result.context_used or [])
            
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000
            
            # Create response
            response = ChatResponse(
                response=rag_result.answer,
                source_url=rag_result.source_url,
                confidence=rag_result.confidence_score,
                thread_id=thread_id,
                session_id=session_id,
                processing_time_ms=processing_time,
                context_length=len(rag_result.context_used or [])
            )
            
            self.logger.info(f"Query processed in {processing_time:.2f}ms")
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing chat request: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_or_create_thread(self, thread_id: str, user_id: Optional[str]):
        """Get or create thread"""
        if thread_id in self.active_sessions:
            return self.active_sessions[thread_id]
        
        # Create new thread
        thread = await self.thread_pool.create_thread(thread_id, user_id)
        self.active_sessions[thread_id] = thread
        return thread
    
    async def get_health_status(self) -> HealthResponse:
        """Get service health status"""
        try:
            # Get component health
            rag_stats = self.rag_service.get_service_stats()
            thread_stats = self.thread_pool.get_stats()
            session_stats = self.session_manager.get_stats()
            
            return HealthResponse(
                status="healthy",
                timestamp=datetime.now().isoformat(),
                active_threads=thread_stats.get('active_threads', 0),
                pending_queries=rag_stats.get('service_info', {}).get('queries_processed', 0)
            )
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return HealthResponse(
                status="unhealthy",
                timestamp=datetime.now().isoformat(),
                active_threads=0,
                pending_queries=0
            )
    
    async def get_service_stats(self) -> Dict:
        """Get comprehensive service statistics"""
        try:
            # Get component stats
            rag_stats = self.rag_service.get_service_stats()
            thread_stats = self.thread_pool.get_stats()
            session_stats = self.session_manager.get_stats()
            
            # Calculate uptime
            uptime = datetime.now() - self.service_start_time
            
            return {
                "service_info": {
                    "uptime_seconds": uptime.total_seconds(),
                    "queries_processed": self.query_count,
                    "start_time": self.service_start_time.isoformat()
                },
                "rag_service": rag_stats,
                "thread_pool": thread_stats,
                "session_manager": session_stats,
                "load_balancer": self.load_balancer.get_stats(),
                "system_info": {
                    "version": "1.0.0",
                    "environment": "production",
                    "enhanced_validation": True,
                    "real_time_sources": True,
                    "multi_source_verification": True
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get service stats: {str(e)}")
            return {"error": str(e)}

# Factory function
def create_api_gateway(config: Dict) -> FastAPI:
    """Create API Gateway instance"""
    gateway = APIGateway(config)
    return gateway.create_api()

# Main function for running the API
def run_api_gateway(config: Dict, host: str = "0.0.0.0", port: int = 8000):
    """Run the API Gateway"""
    app = create_api_gateway(config)
    
    print(f"🚀 Starting Mutual Fund RAG API Gateway...")
    print(f"🌐 Server: http://{host}:{port}")
    print(f"📊 Enhanced RAG System with Real-time Validation")
    print(f"🔗 API Documentation: http://{host}:{port}/docs")
    
    uvicorn.run(
        app=app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    # Load configuration
    config = {
        'session': {
            'max_sessions': 100,
            'session_timeout_hours': 24,
            'cleanup_interval_hours': 1
        },
        'thread_pool': {
            'max_threads': 5,
            'max_concurrent_conversations': 10,
            'resource_limits': {
                'max_memory_mb': 512,
                'max_cpu_percent': 80
            }
        },
        'context': {
            'max_context_length': 10,
            'context_window_size': 5,
            'memory_limit_mb': 256
        },
        'persistence': {
            'storage_type': 'sqlite',
            'database_path': './data/sessions.db',
            'auto_save_interval': 300
        },
        'load_balancer': {
            'strategy': 'least_connections',
            'health_check_interval': 30,
            'max_failures': 3
        },
        'rag_config': {
            'llm': {
                'type': 'template',  # Start with template-based
                'model': 'template'
            },
            'embedding_model': 'BAAI/bge-large-en-v1.5',
            'max_sentences': 3,
            'require_source': True,
            'facts_only': True,
            'confidence_threshold': 0.3
        }
    }
    
    run_api_gateway(config)
