"""
Groq LLM Client
Fast inference with Groq Cloud API
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import os
import json

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logging.warning("Groq library not installed. Install with: pip install groq")

@dataclass
class GroqConfig:
    """Configuration for Groq LLM"""
    api_key: str
    model: str = "llama-3-8b-instruct"
    temperature: float = 0.1
    max_tokens: int = 200
    timeout: int = 30
    rate_limit: int = 30  # requests per minute
    
class GroqClient:
    """Groq LLM client for ultra-fast inference"""
    
    def __init__(self, config: GroqConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        if not GROQ_AVAILABLE:
            raise ImportError("Groq library not installed. Install with: pip install groq")
        
        # Initialize Groq client
        self.client = Groq(api_key=config.api_key)
        
        # Rate limiting
        self.last_request_time = 0
        self.request_times = []
        
        self.logger.info(f"Groq client initialized with model: {config.model}")
    
    def generate_response(self, prompt: str, context: Optional[str] = None) -> Dict:
        """Generate response using Groq LLM"""
        try:
            # Check rate limiting
            self._check_rate_limit()
            
            # Prepare full prompt
            if context:
                full_prompt = f"""Context: {context}

Question: {prompt}

Provide a factual answer based on the context above. Keep your response under 3 sentences and cite the source if available."""
            else:
                full_prompt = prompt
            
            start_time = time.time()
            
            # Generate response
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that provides factual information about mutual funds. Never give investment advice. Keep responses under 3 sentences."
                    },
                    {
                        "role": "user", 
                        "content": full_prompt
                    }
                ],
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            # Extract response
            response_text = chat_completion.choices[0].message.content
            
            result = {
                'success': True,
                'response': response_text.strip(),
                'model': self.config.model,
                'response_time_ms': response_time,
                'tokens_used': chat_completion.usage.total_tokens if chat_completion.usage else 0,
                'finish_reason': chat_completion.choices[0].finish_reason
            }
            
            self.logger.info(f"Groq response generated in {response_time:.2f}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"Groq API error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': 'I apologize, but I encountered an error generating a response.'
            }
    
    def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        current_time = time.time()
        
        # Remove old requests (older than 1 minute)
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        # Check if we're at the rate limit
        if len(self.request_times) >= self.config.rate_limit:
            # Calculate wait time
            oldest_request = min(self.request_times)
            wait_time = 60 - (current_time - oldest_request)
            
            if wait_time > 0:
                self.logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
        
        # Record this request
        self.request_times.append(current_time)
    
    def get_model_info(self) -> Dict:
        """Get information about the current model"""
        return {
            'model': self.config.model,
            'temperature': self.config.temperature,
            'max_tokens': self.config.max_tokens,
            'rate_limit': self.config.rate_limit,
            'available_models': [
                'llama-3-8b-instruct',
                'llama-3-70b-instruct',
                'mixtral-8x7b-instruct',
                'gemma-7b-instruct'
            ]
        }
    
    def test_connection(self) -> bool:
        """Test connection to Groq API"""
        try:
            response = self.generate_response("Hello, this is a test.")
            return response.get('success', False)
        except Exception as e:
            self.logger.error(f"Groq connection test failed: {str(e)}")
            return False

# Factory function
def create_groq_client(config: Dict) -> GroqClient:
    """Create Groq client from configuration"""
    api_key = config.get('api_key') or os.environ.get('GROQ_API_KEY')
    
    if not api_key:
        raise ValueError("Groq API key is required. Set GROQ_API_KEY environment variable or provide in config")
    
    groq_config = GroqConfig(
        api_key=api_key,
        model=config.get('model', 'llama-3-8b-instruct'),
        temperature=config.get('temperature', 0.1),
        max_tokens=config.get('max_tokens', 200),
        timeout=config.get('timeout', 30),
        rate_limit=config.get('rate_limit', 30)
    )
    
    return GroqClient(groq_config)
