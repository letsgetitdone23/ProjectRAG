'use client';

import { useState, useEffect, useRef } from 'react';

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
  sourceUrl?: string;
  lastUpdated?: string;
}

interface ChatThread {
  id: string;
  name: string;
  messages: Message[];
  sessionId: string;
}

interface ChatPopupProps {
  isOpen: boolean;
  onClose: () => void;
  prefillQuestion?: string;
}

export default function ChatPopup({ isOpen, onClose, prefillQuestion = '' }: ChatPopupProps) {
  const [threads, setThreads] = useState<ChatThread[]>([
    {
      id: '1',
      name: 'Chat 1',
      messages: [],
      sessionId: ''
    }
  ]);
  const [activeThreadId, setActiveThreadId] = useState('1');
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeThread = threads.find(t => t.id === activeThreadId);

  useEffect(() => {
    if (prefillQuestion && isOpen) {
      setInputMessage(prefillQuestion);
      setTimeout(() => {
        sendMessage(prefillQuestion);
      }, 100);
    }
  }, [prefillQuestion, isOpen]);

  useEffect(() => {
    scrollToBottom();
  }, [activeThread?.messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const createNewThread = () => {
    if (threads.length >= 3) return;
    
    const newThreadId = (threads.length + 1).toString();
    const newThread: ChatThread = {
      id: newThreadId,
      name: `Chat ${newThreadId}`,
      messages: [],
      sessionId: ''
    };
    setThreads([...threads, newThread]);
    setActiveThreadId(newThreadId);
  };

  const sendMessage = async (messageText?: string) => {
    const messageToSend = messageText || inputMessage;
    if (!messageToSend.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: messageToSend,
      isUser: true,
      timestamp: new Date().toISOString()
    };

    setThreads(threads.map(thread => 
      thread.id === activeThreadId 
        ? { ...thread, messages: [...thread.messages, userMessage] }
        : thread
    ));

    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: messageToSend,
          thread_id: activeThreadId,
          session_id: activeThread?.sessionId || ''
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: data.response,
        isUser: false,
        timestamp: new Date().toISOString(),
        sourceUrl: data.source_url,
        lastUpdated: data.last_updated || '2024-01-01'
      };

      setThreads(prevThreads => prevThreads.map(thread => 
        thread.id === activeThreadId 
          ? { 
              ...thread, 
              messages: [...thread.messages, botMessage],
              sessionId: data.session_id || thread.sessionId
            }
          : thread
      ));

    } catch (error) {
      console.error('Error sending message:', error);
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: 'Sorry, I encountered an error. Please try again.',
        isUser: false,
        timestamp: new Date().toISOString()
      };

      setThreads(prevThreads => prevThreads.map(thread => 
        thread.id === activeThreadId 
          ? { ...thread, messages: [...thread.messages, errorMessage] }
          : thread
      ));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div 
        className="fixed inset-0 z-40"
        style={{ backgroundColor: 'rgba(26, 26, 46, 0.65)', backdropFilter: 'blur(4px)' }}
        onClick={onClose}
      />
      
      {/* Chat Popup */}
      <div className="fixed bottom-6 right-6 w-96 h-[600px] bg-white rounded-lg shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="bg-red-600 text-white px-4 py-3 rounded-t-lg flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
              <span className="text-red-600 font-bold text-sm">N</span>
            </div>
            <div>
              <h3 className="font-semibold">Nippon India Assistant</h3>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                <span className="text-xs">LIVE</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="w-6 h-6 flex items-center justify-center hover:bg-red-700 rounded">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              </svg>
            </button>
            <button 
              onClick={onClose}
              className="w-6 h-6 flex items-center justify-center hover:bg-red-700 rounded"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-gray-50 border-b border-gray-200 px-2 py-2">
          <div className="flex items-center gap-2">
            {threads.map(thread => (
              <button
                key={thread.id}
                onClick={() => setActiveThreadId(thread.id)}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  activeThreadId === thread.id
                    ? 'bg-white text-gray-900 border border-gray-300'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {thread.name}
              </button>
            ))}
            {threads.length < 3 && (
              <button
                onClick={createNewThread}
                className="px-3 py-1 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700"
              >
                New
              </button>
            )}
          </div>
        </div>

        {/* Disclaimer Banner */}
        <div className="bg-yellow-50 border border-yellow-200 px-3 py-2">
          <p className="text-xs text-yellow-800">
            <strong>Disclaimer:</strong> This is an AI assistant providing factual information. 
            Not investment advice. Please consult financial advisors.
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {activeThread?.messages.map(message => (
            <div
              key={message.id}
              className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 ${
                  message.isUser
                    ? 'bg-red-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}
              >
                <p className="text-sm">{message.content}</p>
                {!message.isUser && message.sourceUrl && (
                  <div className="mt-2 pt-2 border-t border-gray-200">
                    <p className="text-xs text-gray-600">
                      <a href={message.sourceUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        Source
                      </a>
                    </p>
                    <p className="text-xs text-gray-500">
                      Last updated: {message.lastUpdated}
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 text-gray-900 rounded-lg px-3 py-2">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your question..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading}
            />
            <button
              onClick={() => sendMessage()}
              disabled={!inputMessage.trim() || isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-4 py-2 border-t border-gray-200">
          <p className="text-xs text-gray-500 text-center">
            Powered by Nippon India Mutual Fund Assistant
          </p>
        </div>
      </div>
    </>
  );
}
