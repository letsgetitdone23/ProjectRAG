"""
Test script to verify all Nippon India fixes are working correctly
Tests the 3 required test queries from the requirements
"""

import requests
import json
import time

def test_query(query, expected_scheme=None, should_be_advisory=False):
    """Test a single query against the API"""
    url = "http://localhost:8003/api/chat"
    payload = {"message": query}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n🔍 Query: {query}")
            print(f"✅ Response: {data['response']}")
            print(f"📄 Source: {data['source_url']}")
            print(f"🎯 Confidence: {data['confidence']}")
            print(f"⏱️ Processing Time: {data['processing_time_ms']:.2f}ms")
            
            # Check if advisory refusal
            if should_be_advisory:
                if "facts only" in data['response'].lower() or "cannot offer investment advice" in data['response'].lower():
                    print("✅ Advisory refusal working correctly")
                else:
                    print("❌ Advisory refusal NOT working")
            
            # Check if Nippon India specific
            if expected_scheme:
                if "nippon india" in data['response'].lower():
                    print("✅ Nippon India scheme detected correctly")
                else:
                    print("❌ Nippon India scheme NOT detected")
                
                if expected_scheme.lower() in data['response'].lower():
                    print(f"✅ {expected_scheme} scheme detected correctly")
                else:
                    print(f"❌ {expected_scheme} scheme NOT detected")
            
            # Check source URL
            if "nipponindiaim.com" in data['source_url']:
                print("✅ Source URL is Nippon India official")
            else:
                print("❌ Source URL is NOT Nippon India official")
            
            return True
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🧪 Testing Nippon India RAG System Fixes")
    print("=" * 60)
    
    # Test 1: Nippon India Large Cap Fund expense ratio
    print("\n📋 TEST 1: Nippon India Large Cap Fund Expense Ratio")
    test_query("What is the expense ratio of Nippon India Large Cap Fund Direct Growth?", expected_scheme="large cap")
    
    # Test 2: Nippon India Flexi Cap Fund minimum SIP
    print("\n📋 TEST 2: Nippon India Flexi Cap Fund Minimum SIP")
    test_query("What is the minimum SIP amount for Nippon India Flexi Cap Fund Direct Growth?", expected_scheme="flexi cap")
    
    # Test 3: Advisory query refusal
    print("\n📋 TEST 3: Advisory Query Refusal")
    test_query("Should I invest in Nippon India Large Cap Fund?", should_be_advisory=True)
    
    # Additional tests
    print("\n📋 TEST 4: Non-Nippon India Query (Should be refused)")
    test_query("What is the NAV of HDFC Mid-Cap Fund?")
    
    print("\n📋 TEST 5: Performance Query (Should be refused)")
    test_query("What are the returns of Nippon India Large Cap Fund?", should_be_advisory=True)
    
    print("\n📋 TEST 6: Nippon India Multi Asset Fund")
    test_query("What is the benchmark index of Nippon India Multi Asset Allocation Fund Direct Growth?", expected_scheme="multi asset")
    
    print("\n📋 TEST 7: General Nippon India Query")
    test_query("How do I download my capital gains statement from Nippon India Mutual Fund?")
    
    print("\n🎯 All tests completed!")

if __name__ == "__main__":
    main()
