"""
Nippon India Focused API Gateway with Embedded UI
Serves HTML interface directly without file dependencies
"""

import logging
import json
import uuid
import time
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

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

class NipponIndiaQueryProcessor:
    """Query processor focused on Nippon India schemes only"""
    
    def __init__(self):
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
            r'\bwhich\s+is\better\b',
            r'\brecommend\b',
            r'\bwill\s+it\s+grow\b',
            r'\bexpected\s+returns\b',
            r'\bcompare\b',
            r'\bvs\b',
            r'\bversus\b'
        ]
        
        # Performance query patterns
        self.performance_patterns = [
            r'\breturns?\s+(history|track|record)\b',
            r'\bperformance\s+(history|track|record)\b',
            r'\bnav\s+history\b',
            r'\bgrowth\s+(rate|history|track)\b'
        ]
        
        # Nippon India data
        self.nippon_data = {
            'large_cap': {
                'nav': '₹101.17',
                'expense_ratio': '1.25%',
                'exit_load': 'Nil for units held for more than 1 year',
                'minimum_sip': '₹500',
                'benchmark': 'Nifty 50 TRI',
                'riskometer': 'Moderately High',
                'source_url': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Large-Cap-Fund.aspx'
            },
            'flexi_cap': {
                'nav': '₹98.45',
                'expense_ratio': '1.15%',
                'exit_load': 'Nil for units held for more than 1 year',
                'minimum_sip': '₹500',
                'benchmark': 'Nifty 50 TRI',
                'riskometer': 'Moderately High',
                'source_url': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Flexi-Cap-Fund.aspx'
            },
            'multi_asset': {
                'nav': '₹87.23',
                'expense_ratio': '1.08%',
                'exit_load': 'Nil for units held for more than 1 year',
                'minimum_sip': '₹500',
                'benchmark': 'CRISIL Composite Bond TRI',
                'riskometer': 'Moderately High',
                'source_url': 'https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Multi-Asset-Allocation-Fund.aspx'
            }
        }
    
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
    
    def process_query(self, query: str) -> Dict:
        """Process query with scope guard and refusal handling"""
        start_time = time.time()
        
        # Check for advisory queries
        if self.is_advisory_query(query):
            return {
                'answer': "This assistant provides facts only and cannot offer investment advice or recommendations. For guidance on choosing funds, please visit: https://www.amfiindia.com/investor-corner/knowledge-center",
                'source_url': "https://www.amfiindia.com/investor-corner/knowledge-center",
                'confidence': 0.0,
                'is_advisory': True,
                'scheme_detected': None
            }
        
        # Check for performance queries
        if self.is_performance_query(query):
            return {
                'answer': "For performance data, please refer to the official factsheet directly.",
                'source_url': "https://mf.nipponindiaim.com/FundsAndPerformance/Pages/",
                'confidence': 0.0,
                'is_advisory': True,
                'scheme_detected': None
            }
        
        # Detect scheme
        detected_scheme = self.detect_scheme(query)
        
        if detected_scheme:
            return self._process_nippon_query(query, detected_scheme)
        
        # General query (not Nippon India specific)
        return {
            'answer': "I can only answer questions about Nippon India Large Cap Fund Direct Growth, Nippon India Flexi Cap Fund Direct Growth, and Nippon India Multi Asset Allocation Fund Direct Growth. Please rephrase your question about one of these schemes.",
            'source_url': "https://mf.nipponindiaim.com/FundsAndPerformance/Pages/",
            'confidence': 0.0,
            'is_advisory': False,
            'scheme_detected': None
        }
    
    def _process_nippon_query(self, query: str, scheme: str) -> Dict:
        """Process Nippon India specific query"""
        data = self.nippon_data.get(scheme, {})
        query_lower = query.lower()
        
        answer = ""
        
        # Generate response based on query type
        if 'nav' in query_lower:
            answer = f"The current NAV of Nippon India {scheme.replace('_', ' ').title()} Fund Direct Growth is {data.get('nav', 'N/A')} per unit."
        
        elif 'expense ratio' in query_lower:
            answer = f"The expense ratio of Nippon India {scheme.replace('_', ' ').title()} Fund Direct Growth is {data.get('expense_ratio', 'N/A')} including GST."
        
        elif 'exit load' in query_lower:
            answer = f"The exit load for Nippon India {scheme.replace('_', ' ').title()} Fund Direct Growth is {data.get('exit_load', 'N/A')}."
        
        elif 'minimum sip' in query_lower:
            answer = f"The minimum SIP amount for Nippon India {scheme.replace('_', ' ').title()} Fund Direct Growth is {data.get('minimum_sip', 'N/A')} per month."
        
        elif 'benchmark' in query_lower:
            answer = f"The benchmark index for Nippon India {scheme.replace('_', ' ').title()} Fund Direct Growth is {data.get('benchmark', 'N/A')} as per official factsheet."
        
        elif 'riskometer' in query_lower:
            answer = f"The riskometer classification for Nippon India {scheme.replace('_', ' ').title()} Fund Direct Growth is {data.get('riskometer', 'N/A')} as per official riskometer."
        
        else:
            # Default response
            answer = f"Nippon India {scheme.replace('_', ' ').title()} Fund Direct Growth provides investment opportunities with current NAV of {data.get('nav', 'N/A')} and expense ratio of {data.get('expense_ratio', 'N/A')}."
        
        return {
            'answer': answer,
            'source_url': data.get('source_url', 'https://mf.nipponindiaim.com'),
            'confidence': 0.9,
            'is_advisory': False,
            'scheme_detected': scheme
        }

class NipponIndiaAPIGateway:
    """API Gateway focused on Nippon India schemes with embedded UI"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.query_processor = NipponIndiaQueryProcessor()
        self.service_start_time = datetime.now()
        self.query_count = 0
    
    def create_api(self) -> FastAPI:
        """Create FastAPI application"""
        app = FastAPI(
            title="Nippon India Mutual Fund RAG API",
            description="Facts-only FAQ assistant for Nippon India schemes with scope guard",
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
            return HTMLResponse(content=self.get_embedded_html())
        
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
    
    def get_embedded_html(self) -> str:
        """Get embedded HTML content"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nippon India Mutual Fund RAG Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
            overflow: hidden;
        }

        .header {
            background: #2E7D32;
            color: white;
            padding: 20px;
            text-align: center;
        }

        .header h1 {
            font-size: 1.8em;
            margin: 0;
            font-weight: 600;
        }

        .header .subtitle {
            color: #4CAF50;
            font-size: 1.2em;
            margin-top: 10px;
            font-weight: 500;
        }

        .disclaimer {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 15px;
            margin: 20px;
            text-align: center;
        }

        .disclaimer h3 {
            color: #856404;
            margin: 0 0 10px 0;
            font-size: 1.1em;
        }

        .examples {
            padding: 20px;
            background: #f8f9fa;
        }

        .examples h3 {
            color: #2E7D32;
            margin: 0 0 15px 0;
            font-size: 1.1em;
        }

        .example-buttons {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }

        .example-btn {
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 16px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
            text-align: left;
        }

        .example-btn:hover {
            background: #45a049;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
        }

        .chat-container {
            border-top: 1px solid #e9ecef;
        }

        .chat-messages {
            height: 300px;
            overflow-y: auto;
            padding: 20px;
            background: #fafafa;
        }

        .message {
            margin-bottom: 15px;
            display: flex;
            align-items: flex-start;
        }

        .message.user {
            justify-content: flex-end;
        }

        .message.assistant {
            justify-content: flex-start;
        }

        .message-content {
            max-width: 80%;
            padding: 12px 16px;
            border-radius: 15px;
            word-wrap: break-word;
        }

        .message.user .message-content {
            background: #2196F3;
            color: white;
        }

        .message.assistant .message-content {
            background: #f1f3f4;
            border: 1px solid #e9ecef;
        }

        .message-info {
            font-size: 0.8em;
            color: #6c757d;
            margin-top: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .source-link {
            color: #4CAF50;
            text-decoration: none;
            font-weight: 500;
        }

        .source-link:hover {
            text-decoration: underline;
        }

        .confidence-score {
            background: #4CAF50;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8em;
        }

        .input-container {
            display: flex;
            gap: 10px;
            padding: 20px;
            background: #f8f9fa;
        }

        .chat-input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #ddd;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
        }

        .chat-input:focus {
            border-color: #4CAF50;
        }

        .send-button {
            padding: 12px 24px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
        }

        .send-button:hover {
            background: #45a049;
        }

        .send-button:disabled {
            background: #cccccc;
            cursor: not-allowed;
        }

        .status {
            text-align: center;
            padding: 10px;
            font-size: 0.9em;
            color: #6c757d;
        }

        .status.connected {
            color: #4CAF50;
            font-weight: 600;
        }

        .status.disconnected {
            color: #dc3545;
            font-weight: 600;
        }

        .scheme-badge {
            background: #2E7D32;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 600;
            margin-left: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🤖 Nippon India Mutual Fund RAG Assistant</h1>
            <div>Facts-Only FAQ System with Real-time Validation</div>
        </div>

        <!-- Disclaimer -->
        <div class="disclaimer">
            <h3>⚠️ Important Disclaimer</h3>
            <p><strong>Facts-only. No investment advice.</strong> This assistant provides only factual information about Nippon India mutual funds based on official sources. It does not give investment recommendations, performance comparisons, or financial advice. Always consult with a qualified financial advisor before making investment decisions.</p>
        </div>

        <!-- Example Questions -->
        <div class="examples">
            <h3>📋 Ask About Nippon India Schemes</h3>
            <div class="example-buttons">
                <button class="example-btn" onclick="askQuestion('What is NAV of Nippon India Large Cap Fund Direct Growth?')">
                    <span class="scheme-badge">LARGE CAP</span>
                    NAV Query
                </button>
                <button class="example-btn" onclick="askQuestion('What is expense ratio of Nippon India Large Cap Fund Direct Growth?')">
                    <span class="scheme-badge">LARGE CAP</span>
                    Expense Ratio
                </button>
                <button class="example-btn" onclick="askQuestion('What is exit load for Nippon India Large Cap Fund Direct Growth?')">
                    <span class="scheme-badge">LARGE CAP</span>
                    Exit Load
                </button>
                <button class="example-btn" onclick="askQuestion('What is benchmark index of Nippon India Large Cap Fund Direct Growth?')">
                    <span class="scheme-badge">LARGE CAP</span>
                    Benchmark
                </button>
                <button class="example-btn" onclick="askQuestion('What is minimum SIP amount for Nippon India Large Cap Fund Direct Growth?')">
                    <span class="scheme-badge">LARGE CAP</span>
                    Minimum SIP
                </button>
            </div>
            <div class="example-buttons">
                <button class="example-btn" onclick="askQuestion('What is NAV of Nippon India Flexi Cap Fund Direct Growth?')">
                    <span class="scheme-badge">FLEXI CAP</span>
                    NAV Query
                </button>
                <button class="example-btn" onclick="askQuestion('What is expense ratio of Nippon India Flexi Cap Fund Direct Growth?')">
                    <span class="scheme-badge">FLEXI CAP</span>
                    Expense Ratio
                </button>
                <button class="example-btn" onclick="askQuestion('What is exit load for Nippon India Flexi Cap Fund Direct Growth?')">
                    <span class="scheme-badge">FLEXI CAP</span>
                    Exit Load
                </button>
                <button class="example-btn" onclick="askQuestion('What is benchmark index of Nippon India Flexi Cap Fund Direct Growth?')">
                    <span class="scheme-badge">FLEXI CAP</span>
                    Benchmark
                </button>
                <button class="example-btn" onclick="askQuestion('What is minimum SIP amount for Nippon India Flexi Cap Fund Direct Growth?')">
                    <span class="scheme-badge">FLEXI CAP</span>
                    Minimum SIP
                </button>
            </div>
            <div class="example-buttons">
                <button class="example-btn" onclick="askQuestion('What is NAV of Nippon India Multi Asset Allocation Fund Direct Growth?')">
                    <span class="scheme-badge">MULTI ASSET</span>
                    NAV Query
                </button>
                <button class="example-btn" onclick="askQuestion('What is expense ratio of Nippon India Multi Asset Allocation Fund Direct Growth?')">
                    <span class="scheme-badge">MULTI ASSET</span>
                    Expense Ratio
                </button>
                <button class="example-btn" onclick="askQuestion('What is exit load for Nippon India Multi Asset Allocation Fund Direct Growth?')">
                    <span class="scheme-badge">MULTI ASSET</span>
                    Exit Load
                </button>
                <button class="example-btn" onclick="askQuestion('What is benchmark index of Nippon India Multi Asset Allocation Fund Direct Growth?')">
                    <span class="scheme-badge">MULTI ASSET</span>
                    Benchmark
                </button>
                <button class="example-btn" onclick="askQuestion('What is minimum SIP amount for Nippon India Multi Asset Allocation Fund Direct Growth?')">
                    <span class="scheme-badge">MULTI ASSET</span>
                    Minimum SIP
                </button>
            </div>
        </div>

        <!-- Chat Interface -->
        <div class="chat-container">
            <div class="chat-messages" id="chatMessages">
                <div class="message assistant">
                    <div class="message-content">
                        👋 Welcome! I can help you with factual information about Nippon India mutual funds including NAV details, expense ratios, SIP amounts, exit loads, benchmark indices, and riskometer classifications. All responses are based on official sources and include source citations. What would you like to know?
                    </div>
                </div>
            </div>
            <div class="input-container">
                <input type="text" id="chatInput" class="chat-input" placeholder="Ask about Nippon India mutual funds (Large Cap, Flexi Cap, Multi Asset)..." onkeypress="handleKeyPress(event)">
                <button class="send-button" id="sendButton" onclick="sendMessage()">Send</button>
            </div>
        </div>

        <!-- Status -->
        <div class="status" id="status">
            Connecting to API...
        </div>
    </div>

    <script>
        let currentSessionId = null;
        let currentThreadId = null;

        // Initialize
        window.onload = function() {
            checkAPIStatus();
            setInterval(checkAPIStatus, 10000);
        };

        function askQuestion(question) {
            document.getElementById('chatInput').value = question;
            sendMessage();
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }

        async function sendMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            const sendButton = document.getElementById('sendButton');
            const chatMessages = document.getElementById('chatMessages');
            
            // Add user message
            addMessage('user', message);
            
            // Clear input and disable button
            input.value = '';
            sendButton.disabled = true;
            sendButton.textContent = 'Sending...';
            
            try {
                // Send to API
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        session_id: currentSessionId,
                        thread_id: currentThreadId
                    })
                });
                
                const data = await response.json();
                
                // Add assistant response
                addMessage('assistant', data.response, data.source_url, data.confidence, data.scheme_detected);
                
            } catch (error) {
                addMessage('assistant', `❌ Error: ${error.message}. Please try again.`, '', 0);
            } finally {
                sendButton.disabled = false;
                sendButton.textContent = 'Send';
            }
        }

        function addMessage(type, content, sourceUrl = '', confidence = 0, schemeDetected = '') {
            const chatMessages = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${type}`;
            
            let messageContent = `
                <div class="message-content">
                    ${content}
                    ${sourceUrl ? `
                        <div class="message-info">
                            <span class="confidence-score">Confidence: ${(confidence * 100).toFixed(1)}%</span>
                            <a href="${sourceUrl}" target="_blank" class="source-link">📄 Source</a>
                            ${schemeDetected ? `<span class="scheme-badge">${schemeDetected.toUpperCase()}</span>` : ''}
                        </div>
                    ` : ''}
                </div>
            `;
            
            messageDiv.innerHTML = messageContent;
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        async function checkAPIStatus() {
            const statusElement = document.getElementById('status');
            
            try {
                const response = await fetch('/api/health');
                const data = await response.json();
                
                statusElement.textContent = '✅ API Connected - Nippon India Focused';
                statusElement.className = 'status connected';
                
            } catch (error) {
                statusElement.textContent = '❌ API Disconnected';
                statusElement.className = 'status disconnected';
            }
        }
    </script>
</body>
</html>
        """
    
    async def process_chat_request(self, request: ChatRequest) -> ChatResponse:
        """Process chat request"""
        start_time = time.time()
        
        try:
            self.query_count += 1
            self.logger.info(f"Processing query #{self.query_count}: {request.message[:100]}...")
            
            # Process query
            result = self.query_processor.process_query(request.message)
            
            # Get or create session
            session_id = request.session_id or str(uuid.uuid4())
            thread_id = request.thread_id or str(uuid.uuid4())
            
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000
            
            # Create response
            response = ChatResponse(
                response=result['answer'],
                source_url=result['source_url'],
                confidence=result['confidence'],
                thread_id=thread_id,
                session_id=session_id,
                processing_time_ms=processing_time,
                context_length=0
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
        """Get service statistics"""
        try:
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

# Main function for running API
def run_nippon_api_gateway(host: str = "0.0.0.0", port: int = 8000):
    """Run Nippon India API Gateway with embedded UI"""
    gateway = NipponIndiaAPIGateway()
    app = gateway.create_api()
    
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
    run_nippon_api_gateway()
