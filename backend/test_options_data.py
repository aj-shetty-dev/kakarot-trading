#!/usr/bin/env python3
"""Check actual option data"""

import gzip
import json
import httpx
import asyncio

async def check_data():
    url = 'https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz'
    
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        data = json.loads(gzip.decompress(r.content))
        
        # Find a CE option
        print("Sample CE option:\n")
        
        for instr in data:
            if instr.get('instrument_type') == 'CE':
                print(json.dumps(instr, indent=2))
                break

if __name__ == "__main__":
    asyncio.run(check_data())
