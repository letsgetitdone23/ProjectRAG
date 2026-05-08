'use client';

import { useState } from 'react';
import ChatPopup from '@/components/ChatPopup';

export default function LandingPage() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [prefillQuestion, setPrefillQuestion] = useState('');

  const openChatWithQuestion = (question: string) => {
    setPrefillQuestion(question);
    setIsChatOpen(true);
  };

  const openChat = () => {
    setPrefillQuestion('');
    setIsChatOpen(true);
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Navbar */}
      <nav className="w-full bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <h1 className="text-xl font-bold text-gray-900">Nippon India</h1>
              </div>
            </div>
            <div className="hidden md:block">
              <div className="ml-10 flex items-baseline space-x-4">
                <a href="#" className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">Home</a>
                <a href="#" className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">Schemes</a>
                <a href="#" className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">About</a>
                <a href="#" className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">Contact</a>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-gray-50 to-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-4xl md:text-6xl font-bold text-gray-900 mb-6">
              Nippon India Mutual Fund
              <br />
              <span className="text-blue-600">FAQ Assistant</span>
            </h1>
            <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
              Get instant answers to your questions about Nippon India mutual funds. 
              Our AI-powered assistant provides factual information with real-time data.
            </p>
            <button
              onClick={openChat}
              className="bg-blue-600 text-white px-8 py-4 rounded-lg text-lg font-semibold hover:bg-blue-700 transition-colors"
            >
              Ask a Question →
            </button>
          </div>
        </div>
      </section>

      {/* Scheme Cards */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            Popular Schemes
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow">
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                Nippon India Large Cap Fund
              </h3>
              <p className="text-gray-600 mb-4">
                Invest in India's largest and most stable companies
              </p>
              <button
                onClick={() => openChatWithQuestion("What is the expense ratio of Nippon India Large Cap Fund Direct Growth?")}
                className="text-blue-600 hover:text-blue-700 font-medium"
              >
                Ask about this fund →
              </button>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow">
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                Nippon India Flexi Cap Fund
              </h3>
              <p className="text-gray-600 mb-4">
                Dynamic allocation across market capitalizations
              </p>
              <button
                onClick={() => openChatWithQuestion("What is the minimum SIP amount for Nippon India Flexi Cap Fund Direct Growth?")}
                className="text-blue-600 hover:text-blue-700 font-medium"
              >
                Ask about this fund →
              </button>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow">
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                Nippon India Multi Asset Allocation Fund
              </h3>
              <p className="text-gray-600 mb-4">
                Diversified across equity, debt, and gold
              </p>
              <button
                onClick={() => openChatWithQuestion("What is the benchmark index of Nippon India Multi Asset Allocation Fund Direct Growth?")}
                className="text-blue-600 hover:text-blue-700 font-medium"
              >
                Ask about this fund →
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Question Pills Grid */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            Popular Questions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              "What is the expense ratio of Nippon India Large Cap Fund Direct Growth?",
              "What is the minimum SIP amount for Nippon India Flexi Cap Fund Direct Growth?",
              "What is the benchmark index of Nippon India Multi Asset Allocation Fund Direct Growth?",
              "What is the current NAV of Nippon India Large Cap Fund Direct Growth?",
              "What is the exit load for Nippon India Flexi Cap Fund Direct Growth?",
              "What is the riskometer classification of Nippon India Multi Asset Allocation Fund Direct Growth?"
            ].map((question, index) => (
              <button
                key={index}
                onClick={() => openChatWithQuestion(question)}
                className="bg-white border border-gray-200 rounded-full px-6 py-3 text-left hover:bg-gray-50 hover:border-blue-300 transition-colors"
              >
                <span className="text-sm text-gray-700">{question}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            How It Works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-blue-600 font-bold">1</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Ask Your Question</h3>
              <p className="text-gray-600">Type your question about Nippon India mutual funds</p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-blue-600 font-bold">2</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">AI Processing</h3>
              <p className="text-gray-600">Our AI analyzes your query and retrieves relevant information</p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-blue-600 font-bold">3</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Get Answer</h3>
              <p className="text-gray-600">Receive factual information with official sources</p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-blue-600 font-bold">4</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Verify Sources</h3>
              <p className="text-gray-600">Check official Nippon India sources for more details</p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <h3 className="text-lg font-semibold mb-4">Nippon India</h3>
              <p className="text-gray-400">
                Leading mutual fund company in India with a wide range of investment solutions.
              </p>
            </div>
            
            <div>
              <h3 className="text-lg font-semibold mb-4">Products</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="#" className="hover:text-white">Equity Funds</a></li>
                <li><a href="#" className="hover:text-white">Debt Funds</a></li>
                <li><a href="#" className="hover:text-white">Hybrid Funds</a></li>
                <li><a href="#" className="hover:text-white">Solution Oriented</a></li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-lg font-semibold mb-4">Resources</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="#" className="hover:text-white">Calculators</a></li>
                <li><a href="#" className="hover:text-white">KYC</a></li>
                <li><a href="#" className="hover:text-white">FAQs</a></li>
                <li><a href="#" className="hover:text-white">Blog</a></li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-lg font-semibold mb-4">Contact</h3>
              <ul className="space-y-2 text-gray-400">
                <li>1800-200-6626</li>
                <li>customercare@nipponindiamf.com</li>
                <li>Mon-Fri: 9 AM to 6 PM</li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2024 Nippon India Mutual Fund. All rights reserved.</p>
          </div>
        </div>
      </footer>

      {/* Floating Chat Button */}
      <button
        onClick={openChat}
        className="fixed bottom-6 right-6 w-14 h-14 bg-red-600 text-white rounded-full shadow-lg hover:bg-red-700 transition-colors flex items-center justify-center z-40"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      </button>

      {/* Chat Popup */}
      <ChatPopup
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        prefillQuestion={prefillQuestion}
      />
    </div>
  );
}
