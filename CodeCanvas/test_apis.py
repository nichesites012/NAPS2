#!/usr/bin/env python3
"""
API Test Script - Test SERP and WHOIS APIs
"""

import asyncio
import aiohttp
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

async def test_serp_api():
    """Test SERP API connectivity"""
    api_key = os.getenv('SERP_API_KEY', '63cc73fca4mshf55eb3b0811d360p14620ajsn92730fc828bc')
    
    url = "https://google-search116.p.rapidapi.com/?query=Nike"
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'google-search116.p.rapidapi.com'
    }
    
    print("Testing SERP API...")
    print(f"URL: {url}")
    print(f"API Key: {api_key[:20]}...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                print(f"Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print("✅ SERP API working!")
                    print(f"Results found: {len(data.get('results', []))}")
                    return True
                else:
                    text = await response.text()
                    print(f"❌ SERP API failed: {response.status}")
                    print(f"Response: {text[:200]}...")
                    return False
    except Exception as e:
        print(f"❌ SERP API error: {e}")
        return False

async def test_whois_api():
    """Test WHOIS API connectivity"""
    api_key = os.getenv('WHOIS_API_KEY', '653b90312dmsh9219d00db599bf4p1e3706jsn8f0ba5f7b11b')
    
    # Test the working endpoint
    url = "https://whois-api6.p.rapidapi.com/whois/api/v1/getData"
    
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'whois-api6.p.rapidapi.com',
        'Content-Type': 'application/json'
    }
    
    payload = json.dumps({"query": "google.com"})
    
    print(f"\nTesting WHOIS API...")
    print(f"URL: {url}")
    print(f"API Key: {api_key[:20]}...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=payload) as response:
                print(f"Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print("✅ WHOIS API working!")
                    print(f"Response keys: {list(data.keys())}")
                    
                    # Check if we have the required fields
                    if 'result' in data and 'creation_date' in data['result']:
                        creation_dates = data['result']['creation_date']
                        print(f"Creation dates found: {creation_dates}")
                        return True
                    else:
                        print("⚠️  Missing creation_date in response")
                        return False
                else:
                    text = await response.text()
                    print(f"❌ WHOIS API failed: {response.status}")
                    print(f"Response: {text[:200]}...")
                    return False
                        
    except Exception as e:
        print(f"❌ WHOIS API error: {e}")
        return False

async def main():
    """Main test function"""
    print("🔍 Testing API Connectivity...")
    print("=" * 50)
    
    serp_ok = await test_serp_api()
    whois_ok = await test_whois_api()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"SERP API: {'✅ Working' if serp_ok else '❌ Failed'}")
    print(f"WHOIS API: {'✅ Working' if whois_ok else '❌ Failed'}")
    
    if serp_ok and whois_ok:
        print("\n🎉 All APIs are working! The application should work correctly.")
    else:
        print("\n⚠️  Some APIs failed. Check your API keys and subscription status.")

if __name__ == "__main__":
    asyncio.run(main())