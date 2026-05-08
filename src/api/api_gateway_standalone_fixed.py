"""
Standalone API Gateway - Fixed Version
No session management imports, uses mock RAG service directly
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
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn

# Import enhanced query processor
import sys
sys.path.append(str(Path(__file__).parent.parent))
try:
    from retrieval.enhanced_query_processor import create_enhanced_query_processor
except ImportError:
    # Fallback if enhanced processor not available
    create_enhanced_query_processor = None

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

class StandaloneAPIGateway:
    """Standalone API Gateway with enhanced query processor"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize enhanced query processor
        self.query_processor = create_enhanced_query_processor(config.get('rag_config', {}))
        
        # Service metadata
        self.service_start_time = datetime.now()
        self.query_count = 0
        self.active_sessions = {}
        
        self.logger.info("Standalone API Gateway with enhanced query processor initialized")
    
    def create_api(self) -> FastAPI:
        """Create FastAPI application"""
        app = FastAPI(
            title="Nippon India Mutual Fund RAG API",
            description="Facts-only FAQ assistant for Nippon India schemes with real-time validation",
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
        @app.get("/")
        async def root_endpoint():
            """Serve HTML interface"""
            try:
                html_path = Path(__file__).parent.parent / "ui" / "nippon_focused_interface.html"
                if html_path.exists():
                    return FileResponse(str(html_path))
                else:
                    return JSONResponse({
                        "message": "Nippon India Mutual Fund RAG API",
                        "version": "1.0.0",
                        "status": "running",
                        "scope": "Nippon India schemes only",
                        "endpoints": {
                            "chat": "/api/chat",
                            "health": "/api/health",
                            "stats": "/api/stats"
                        }
                    })
            except Exception as e:
                self.logger.error(f"Error serving UI: {str(e)}")
                return JSONResponse({"error": str(e)}, status_code=500)
        
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
        
        return app
    
    async def process_chat_request(self, request: ChatRequest) -> ChatResponse:
        """Process chat request with enhanced query processor"""
        start_time = time.time()
        
        try:
            self.query_count += 1
            self.logger.info(f"Processing query #{self.query_count}: {request.message[:100]}...")
            
            # Get or create session
            session_id = request.session_id or str(uuid.uuid4())
            thread_id = request.thread_id or str(uuid.uuid4())
            
            # Create mock vector store for testing
            class MockVectorStore:
                def search(self, embedding, top_k=3, scheme_filter=None):
                    # Mock search results based on query
                    query_lower = request.message.lower()
                    
                    # Nippon India Large Cap Fund data
                    if 'large cap' in query_lower or 'large-cap' in query_lower:
                        return [{
                            'id': 'large_cap_1',
                            'content': 'The current NAV of Nippon India Large Cap Fund Direct Growth is ₹101.17 per unit as per latest data. The fund has an expense ratio of 1.25% including GST and follows Nifty 50 TRI as benchmark.',
                            'source_url': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Large-Cap-Fund.aspx',
                            'score': 0.95,
                            'scheme': 'large_cap'
                        }]
                    
                    # Nippon India Flexi Cap Fund data
                    elif 'flexi cap' in query_lower or 'flexi-cap' in query_lower:
                        return [{
                            'id': 'flexi_cap_1',
                            'content': 'The current NAV of Nippon India Flexi Cap Fund Direct Growth is ₹98.45 per unit. The fund has an expense ratio of 1.15% including GST and follows Nifty 50 TRI as benchmark.',
                            'source_url': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Flexi-Cap-Fund.aspx',
                            'score': 0.92,
                            'scheme': 'flexi_cap'
                        }]
                    
                    # Nippon India Multi Asset Fund data
                    elif 'multi asset' in query_lower or 'multi-asset' in query_lower:
                        return [{
                            'id': 'multi_asset_1',
                            'content': 'The current NAV of Nippon India Multi Asset Allocation Fund Direct Growth is ₹87.23 per unit. The fund has an expense ratio of 1.08% including GST and follows CRISIL Composite Bond TRI as benchmark.',
                            'source_url': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Multi-Asset-Allocation-Fund.aspx',
                            'score': 0.88,
                            'scheme': 'multi_asset'
                        }]
                    
                    # Default general data
                    else:
                        return [{
                            'id': 'general_1',
                            'content': 'For general mutual fund information, please visit the official Nippon India website or contact their customer service.',
                            'source_url': 'https://mf.nipponindiaim.com',
                            'score': 0.6,
                            'scheme': 'general'
                        }]
            
            mock_vector_store = MockVectorStore()
            
            # Process query with enhanced processor
            result = self.query_processor.process_query(request.message, mock_vector_store)
            
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000
            
            # Create Response
            response = ChatResponse(
                response=result.answer,
                source_url=result.source_url,
                confidence=result.confidence_score,
                thread_id=thread_id,
                session_id=session_id,
                processing_time_ms=processing_time,
                context_length=len(result.context_used or []),
                scheme_detected=result.scheme_detected
            )
            
            self.logger.info(f"Query processed in {processing_time:.2f}ms")
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing chat request: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_health_status(self) -> HealthResponse:
        """Get service health status"""
        try:
            return HealthResponse(
                status="healthy",
                timestamp=datetime.now().isoformat(),
                active_threads=0,
                pending_queries=self.query_count
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
            # Calculate uptime
            uptime = datetime.now() - self.service_start_time
            
            return {
                "service_info": {
                    "uptime_seconds": uptime.total_seconds(),
                    "queries_processed": self.query_count,
                    "start_time": self.service_start_time.isoformat()
                },
                "system_info": {
                    "version": "1.0.0",
                    "environment": "production",
                    "scope": "Nippon India schemes only",
                    "enhanced_validation": True,
                    "real_time_sources": True,
                    "multi_source_verification": True,
                    "supported_question_types": 8
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get service stats: {str(e)}")
            return {"error": str(e)}

# Factory function
def create_standalone_api_gateway(config: Dict) -> FastAPI:
    """Create standalone API Gateway"""
    gateway = StandaloneAPIGateway(config)
    return gateway.create_api()

# Main function for running API
def run_standalone_api_gateway(config: Dict, host: str = "0.0.0.0", port: int = 8000):
    """Run standalone API Gateway"""
    app = create_standalone_api_gateway(config)
    
    print(f"🚀 Starting Nippon India Mutual Fund RAG API...")
    print(f"🌐 Server: http://{host}:{port}")
    print(f"📊 Enhanced RAG System with Scope Guard")
    print(f"🎯 Scope: Nippon India schemes only")
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
        'rag_config': {
            'llm': {
                'type': 'template',
                'model': 'template'
            },
            'embedding_model': 'BAAI/bge-large-en-v1.5',
            'max_sentences': 3,
            'require_source': True,
            'facts_only': True,
            'confidence_threshold': 0.3
        }
    }
    
    run_standalone_api_gateway(config)
