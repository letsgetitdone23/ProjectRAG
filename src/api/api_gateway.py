"""
API Gateway for Multi-thread RAG Service
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

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from ..session.session_manager import SessionManager
from ..session.thread_pool import ThreadPoolManager
from ..session.context_manager import ContextManager
from ..session.session_persistence import SessionPersistenceManager
from ..session.load_balancer import LoadBalancer

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
    total_sessions: int = Field(..., description="Total active sessions")

class SessionInfo(BaseModel):
    session_id: str = Field(..., description="Session identifier")
    thread_id: str = Field(..., description="Thread identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    created_at: str = Field(..., description="Session creation time")
    last_activity: str = Field(..., description="Last activity time")
    message_count: int = Field(..., description="Number of messages in session")

@dataclass
class APIConfig:
    """API Gateway configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: List[str] = None
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    request_timeout_seconds: int = 30
    max_request_size_mb: int = 10

class APIGateway:
    """API Gateway for multi-thread RAG service"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # API configuration
        self.api_config = APIConfig(**config.get('api', {}))
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="Multi-thread RAG Service",
            description="RAG service with multi-thread support and session management",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Add CORS middleware
        self._setup_cors()
        
        # Initialize session management components
        self._initialize_session_management()
        
        # Setup API routes
        self._setup_routes()
        
        # Request tracking
        self.active_requests: Dict[str, Dict] = {}
        self.request_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_response_time_ms': 0.0
        }
        
        self.logger.info(f"API Gateway initialized on {self.api_config.host}:{self.api_config.port}")
    
    def _setup_cors(self):
        """Setup CORS middleware"""
        origins = self.api_config.cors_origins or ["*"]
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _initialize_session_management(self):
        """Initialize session management components"""
        session_config = self.config.get('session_management', {})
        
        # Initialize session manager
        self.session_manager = SessionManager(session_config)
        
        # Initialize thread pool manager
        thread_pool_config = session_config.get('thread_pool', {})
        self.thread_pool_manager = ThreadPoolManager(thread_pool_config)
        
        # Initialize context manager
        context_config = session_config.get('context_manager', {})
        self.context_manager = ContextManager(context_config)
        
        # Initialize session persistence
        persistence_config = session_config.get('persistence', {})
        self.persistence_manager = SessionPersistenceManager(persistence_config)
        
        # Initialize load balancer
        self.load_balancer = LoadBalancer(self.thread_pool_manager, session_config)
        
        self.logger.info("Session management components initialized")
    
    def _setup_routes(self):
        """Setup API routes"""
        
        @self.app.post("/api/chat", response_model=ChatResponse)
        async def chat_endpoint(request: ChatRequest, bg_tasks: BackgroundTasks):
            """Main chat endpoint"""
            return await self._handle_chat_request(request, bg_tasks)
        
        @self.app.get("/api/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint"""
            return await self._handle_health_check()
        
        @self.app.get("/api/sessions", response_model=List[SessionInfo])
        async def get_sessions():
            """Get all active sessions"""
            return await self._handle_get_sessions()
        
        @self.app.get("/api/sessions/{session_id}", response_model=SessionInfo)
        async def get_session(session_id: str):
            """Get specific session information"""
            return await self._handle_get_session(session_id)
        
        @self.app.delete("/api/sessions/{session_id}")
        async def delete_session(session_id: str):
            """Delete specific session"""
            return await self._handle_delete_session(session_id)
        
        @self.app.get("/api/stats")
        async def get_stats():
            """Get system statistics"""
            return await self._handle_get_stats()
        
        @self.app.get("/api/threads/{thread_id}/status")
        async def get_thread_status(thread_id: str):
            """Get thread status"""
            return await self._handle_get_thread_status(thread_id)
        
        @self.app.post("/api/threads/{thread_id}/clear")
        async def clear_thread(thread_id: str):
            """Clear all contexts in thread"""
            return await self._handle_clear_thread(thread_id)
        
        # Error handlers
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail, "status_code": exc.status_code}
            )
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            self.logger.error(f"Unhandled exception: {str(exc)}")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "status_code": 500}
            )
    
    async def _handle_chat_request(self, request: ChatRequest, bg_tasks: BackgroundTasks) -> ChatResponse:
        """Handle chat request"""
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        try:
            # Validate request
            if not request.message.strip():
                raise HTTPException(status_code=400, detail="Message cannot be empty")
            
            # Submit query to thread pool
            query_id = self.thread_pool_manager.submit_query(
                query=request.message,
                user_id=request.user_id,
                thread_id=request.thread_id
            )
            
            # Wait for result
            result = self.thread_pool_manager.get_query_result(query_id, timeout=self.api_config.request_timeout_seconds)
            
            # Update statistics
            processing_time = (time.time() - start_time) * 1000
            self._update_request_stats(processing_time, success=True)
            
            # Create response
            response = ChatResponse(
                response=result.get('response', 'I apologize, but I could not process your request.'),
                source_url=result.get('source_url', ''),
                confidence=result.get('confidence', 0.0),
                thread_id=result.get('thread_id', ''),
                session_id=request.session_id or query_id,
                processing_time_ms=processing_time,
                context_length=result.get('context_length', 0)
            )
            
            # Add background task for logging
            bg_tasks.add_task(self._log_request, request_id, request, response, processing_time)
            
            return response
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self._update_request_stats(processing_time, success=False)
            
            self.logger.error(f"Chat request failed: {str(e)}")
            
            if "timeout" in str(e).lower():
                raise HTTPException(status_code=408, detail="Request timeout")
            elif "busy" in str(e).lower():
                raise HTTPException(status_code=503, detail="Service is busy, please try again later")
            else:
                raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _handle_health_check(self) -> HealthResponse:
        """Handle health check"""
        try:
            # Get system status
            pool_status = self.thread_pool_manager.get_pool_status()
            session_stats = self.session_manager.get_thread_stats()
            
            return HealthResponse(
                status="healthy" if pool_status['active_threads'] > 0 else "unhealthy",
                timestamp=datetime.now().isoformat(),
                active_threads=pool_status['active_threads'],
                pending_queries=pool_status['pending_queries'],
                total_sessions=session_stats['total_conversations']
            )
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return HealthResponse(
                status="unhealthy",
                timestamp=datetime.now().isoformat(),
                active_threads=0,
                pending_queries=0,
                total_sessions=0
            )
    
    async def _handle_get_sessions(self) -> List[SessionInfo]:
        """Handle get sessions request"""
        try:
            sessions = []
            
            # Get active sessions from all threads
            with self.session_manager.thread_lock:
                for thread_id, thread_session in self.session_manager.active_threads.items():
                    for conv_id, conversation in thread_session.active_conversations.items():
                        session_info = SessionInfo(
                            session_id=f"{thread_id}_{conv_id}",
                            thread_id=thread_id,
                            user_id=conversation.user_id,
                            created_at=conversation.created_at.isoformat(),
                            last_activity=conversation.last_activity.isoformat(),
                            message_count=len(conversation.conversation_history)
                        )
                        sessions.append(session_info)
            
            return sessions
            
        except Exception as e:
            self.logger.error(f"Error getting sessions: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve sessions")
    
    async def _handle_get_session(self, session_id: str) -> SessionInfo:
        """Handle get specific session request"""
        try:
            # Parse session_id to get thread_id and conversation_id
            parts = session_id.split('_', 1)
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid session ID format")
            
            thread_id, conv_id = parts
            
            with self.session_manager.thread_lock:
                if (thread_id not in self.session_manager.active_threads or
                    conv_id not in self.session_manager.active_threads[thread_id].active_conversations):
                    raise HTTPException(status_code=404, detail="Session not found")
                
                conversation = self.session_manager.active_threads[thread_id].active_conversations[conv_id]
                
                return SessionInfo(
                    session_id=session_id,
                    thread_id=thread_id,
                    user_id=conversation.user_id,
                    created_at=conversation.created_at.isoformat(),
                    last_activity=conversation.last_activity.isoformat(),
                    message_count=len(conversation.conversation_history)
                )
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error getting session {session_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve session")
    
    async def _handle_delete_session(self, session_id: str) -> Dict:
        """Handle delete session request"""
        try:
            # Parse session_id
            parts = session_id.split('_', 1)
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid session ID format")
            
            thread_id, conv_id = parts
            
            # Clear context
            success = self.context_manager.clear_context(thread_id, conv_id)
            
            if success:
                return {"message": "Session deleted successfully", "session_id": session_id}
            else:
                raise HTTPException(status_code=500, detail="Failed to delete session")
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error deleting session {session_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete session")
    
    async def _handle_get_stats(self) -> Dict:
        """Handle get statistics request"""
        try:
            # Get statistics from all components
            pool_stats = self.thread_pool_manager.get_pool_status()
            load_balancer_stats = self.load_balancer.get_load_balancing_stats()
            context_stats = self.context_manager.get_global_metrics()
            persistence_stats = self.persistence_manager.get_storage_stats()
            
            return {
                "api_stats": self.request_stats,
                "thread_pool": pool_stats,
                "load_balancer": load_balancer_stats,
                "context_manager": context_stats,
                "persistence": persistence_stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting stats: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
    
    async def _handle_get_thread_status(self, thread_id: str) -> Dict:
        """Handle get thread status request"""
        try:
            thread_details = self.load_balancer.get_thread_details()
            
            if thread_id not in thread_details:
                raise HTTPException(status_code=404, detail="Thread not found")
            
            return thread_details[thread_id]
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error getting thread status {thread_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve thread status")
    
    async def _handle_clear_thread(self, thread_id: str) -> Dict:
        """Handle clear thread request"""
        try:
            cleared_count = self.context_manager.clear_thread_contexts(thread_id)
            
            return {
                "message": f"Cleared {cleared_count} contexts in thread {thread_id}",
                "thread_id": thread_id,
                "cleared_contexts": cleared_count
            }
            
        except Exception as e:
            self.logger.error(f"Error clearing thread {thread_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to clear thread")
    
    def _update_request_stats(self, response_time_ms: float, success: bool):
        """Update request statistics"""
        self.request_stats['total_requests'] += 1
        
        if success:
            self.request_stats['successful_requests'] += 1
        else:
            self.request_stats['failed_requests'] += 1
        
        # Update average response time
        if self.request_stats['total_requests'] == 1:
            self.request_stats['average_response_time_ms'] = response_time_ms
        else:
            alpha = 0.1  # Exponential moving average
            self.request_stats['average_response_time_ms'] = (
                alpha * response_time_ms +
                (1 - alpha) * self.request_stats['average_response_time_ms']
            )
    
    async def _log_request(self, request_id: str, request: ChatRequest, 
                          response: ChatResponse, processing_time_ms: float):
        """Log request details asynchronously"""
        try:
            log_entry = {
                'request_id': request_id,
                'timestamp': datetime.now().isoformat(),
                'request': {
                    'user_id': request.user_id,
                    'thread_id': request.thread_id,
                    'message_length': len(request.message),
                    'has_context': request.context is not None
                },
                'response': {
                    'response_length': len(response.response),
                    'confidence': response.confidence,
                    'thread_id': response.thread_id,
                    'context_length': response.context_length
                },
                'performance': {
                    'processing_time_ms': processing_time_ms
                }
            }
            
            self.logger.info(f"Request completed: {json.dumps(log_entry)}")
            
        except Exception as e:
            self.logger.error(f"Error logging request {request_id}: {str(e)}")
    
    def run(self):
        """Run the API gateway"""
        self.logger.info(f"Starting API Gateway on {self.api_config.host}:{self.api_config.port}")
        
        uvicorn.run(
            self.app,
            host=self.api_config.host,
            port=self.api_config.port,
            debug=self.api_config.debug,
            log_level="info"
        )
    
    def shutdown(self):
        """Gracefully shutdown API gateway"""
        self.logger.info("Shutting down API Gateway")
        
        # Shutdown all components
        self.thread_pool_manager.shutdown()
        self.session_manager.shutdown()
        self.context_manager.shutdown()
        self.persistence_manager.shutdown()
        self.load_balancer.shutdown()
        
        self.logger.info("API Gateway shutdown complete")

# Factory function
def create_api_gateway(config: Dict) -> APIGateway:
    """Create API Gateway instance"""
    return APIGateway(config)

# CLI entry point
def main():
    """Main entry point for API Gateway"""
    import argparse
    import yaml
    
    parser = argparse.ArgumentParser(description="Multi-thread RAG API Gateway")
    parser.add_argument("--config", default="config/api_config.yaml", help="Configuration file path")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = {}
    
    # Override with CLI arguments
    if 'api' not in config:
        config['api'] = {}
    
    config['api'].update({
        'host': args.host,
        'port': args.port,
        'debug': args.debug
    })
    
    # Create and run API gateway
    api_gateway = create_api_gateway(config)
    
    try:
        api_gateway.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        api_gateway.shutdown()

if __name__ == "__main__":
    main()
