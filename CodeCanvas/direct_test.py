#!/usr/bin/env python3
"""
Simple WHOIS API Test
"""

import asyncio
import aiohttp
import json

async def test_direct():
    """Test WHOIS API directly with the exact key"""
    api_key = "653b90312dmsh9219d00db599bf4p1e3706jsn8f0ba5f7b11b"
    
    url = "https://whois-api6.p.rapidapi.com/whois/api/v1/getData"
    
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'whois-api6.p.rapidapi.com',
        'Content-Type': 'application/json'
    }
    
    payload = json.dumps({"query": "google.com"})
    
    print(f"Testing WHOIS API directly...")
    print(f"URL: {url}")
    print(f"API Key: {api_key}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=payload) as response:
                print(f"Status: {response.status}")
                text = await response.text()
                print(f"Response: {text[:500]}...")
                
                if response.status == 200:
                    data = await response.json()
                    print("✅ Success!")
                    if 'result' in data and 'creation_date' in data['result']:
                        print(f"Creation dates: {data['result']['creation_date']}")
                else:
                    print(f"❌ Failed: {response.status}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_direct())