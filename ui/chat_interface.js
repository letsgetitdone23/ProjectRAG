/**
 * Chat Interface JavaScript
 * Handles real-time conversation with API integration
 */

class ChatInterface {
    constructor() {
        this.apiBase = 'http://localhost:8000/api';
        this.currentSessionId = null;
        this.currentThreadId = null;
        this.messageHistory = [];
        this.isConnected = false;
        
        this.initializeEventListeners();
        this.checkAPIConnection();
    }
    
    initializeEventListeners() {
        // Send button
        const sendButton = document.getElementById('sendButton');
        if (sendButton) {
            sendButton.addEventListener('click', () => this.sendMessage());
        }
        
        // Enter key
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    this.sendMessage();
                }
            });
        }
        
        // Example question clicks
        document.querySelectorAll('.example-question').forEach(element => {
            element.addEventListener('click', () => {
                const question = element.querySelector('.question-text').textContent;
                this.setChatInput(question);
            });
        });
    }
    
    async checkAPIConnection() {
        try {
            const response = await fetch(`${this.apiBase}/health`);
            const data = await response.json();
            
            this.updateConnectionStatus(data.status === 'healthy');
        } catch (error) {
            this.updateConnectionStatus(false);
        }
        
        // Check every 30 seconds
        setInterval(() => this.checkAPIConnection(), 30000);
    }
    
    updateConnectionStatus(isConnected) {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-indicator span');
        
        if (statusDot && statusText) {
            if (isConnected) {
                statusDot.className = 'status-dot online';
                statusText.textContent = 'API Connected';
            } else {
                statusDot.className = 'status-dot';
                statusText.textContent = 'API Disconnected';
            }
        }
        
        this.isConnected = isConnected;
    }
    
    setChatInput(text) {
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            chatInput.value = text;
            chatInput.focus();
        }
    }
    
    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();
        
        if (!message) return;
        
        const sendButton = document.getElementById('sendButton');
        const chatMessages = document.getElementById('chatMessages');
        
        // Disable send button and show loading
        sendButton.disabled = true;
        sendButton.textContent = 'Sending...';
        this.addMessage('user', message);
        
        try {
            const response = await fetch(`${this.apiBase}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.currentSessionId,
                    thread_id: this.currentThreadId
                })
            });
            
            const data = await response.json();
            
            // Add assistant response
            this.addMessage('assistant', data.response, data.source_url, data.confidence);
            
            // Clear input
            chatInput.value = '';
            
        } catch (error) {
            this.addMessage('assistant', `❌ Error: ${error.message}. Please try again.`, '', 0);
        } finally {
            // Re-enable send button
            sendButton.disabled = false;
            sendButton.textContent = 'Send';
        }
    }
    
    addMessage(type, content, sourceUrl = '', confidence = 0) {
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
                    </div>
                ` : ''}
            </div>
        `;
        
        messageDiv.innerHTML = messageContent;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Store in history
        this.messageHistory.push({
            type,
            content,
            sourceUrl,
            confidence,
            timestamp: new Date().toISOString()
        });
    }
    
    // Initialize chat interface
    document.addEventListener('DOMContentLoaded', () => {
        new ChatInterface();
    });
}

// Export for use in HTML
window.ChatInterface = ChatInterface;
