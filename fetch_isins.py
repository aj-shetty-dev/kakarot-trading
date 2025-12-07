#!/usr/bin/env python3
"""
Fetch ISIN codes for all 208 NSE FNO symbols from reliable sources
"""

import requests
import json
import time
from typing import Dict, Optional

# All 208 NSE FNO symbols
FNO_SYMBOLS = [
    "360ONE", "ABB", "APLAPOLLO", "AUBANK", "ADANIENSOL", "ADANIENT",
    "ADANIGREEN", "ADANIPORTS", "ABCAPITAL", "ALKEM", "AMBER", "AMBUJACEM",
    "ANGELONE", "APOLLOHOSP", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUROPHARMA",
    "DMART", "AXISBANK", "BSE", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV",
    "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BDL", "BEL", "BHARATFORG",
    "BHEL", "BPCL", "BHARTIARTL", "BIOCON", "BLUESTARCO", "BOSCHLTD",
    "BRITANNIA", "CGPOWER", "CANBK", "CDSL", "CHOLAFIN", "CIPLA",
    "COALINDIA", "COFORGE", "COLPAL", "CAMS", "CONCOR", "CROMPTON",
    "CUMMINSIND", "CYIENT", "DLF", "DABUR", "DALBHARAT", "DELHIVERY",
    "DIVISLAB", "DIXON", "DRREDDY", "ETERNAL", "EICHERMOT", "EXIDEIND",
    "NYKAA", "FORTIS", "GAIL", "GMRAIRPORT", "GLENMARK", "GODREJCP",
    "GODREJPROP", "GRASIM", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE",
    "HFCL", "HAVELLS", "HEROMOTOCO", "HINDALCO", "HAL", "HINDPETRO",
    "HINDUNILVR", "HINDZINC", "POWERINDIA", "HUDCO", "ICICIBANK", "ICICIGI",
    "ICICIPRULI", "IDFCFIRSTB", "IIFL", "ITC", "INDIANB", "IEX",
    "IOC", "IRCTC", "IRFC", "IREDA", "INDUSTOWER", "INDUSINDBK",
    "NAUKRI", "INFY", "INOXWIND", "INDIGO", "JINDALSTEL", "JSWENERGY",
    "JSWSTEEL", "JIOFIN", "JUBLFOOD", "KEI", "KPITTECH", "KALYANKJIL",
    "KAYNES", "KFINTECH", "KOTAKBANK", "LTF", "LICHSGFIN", "LTIM",
    "LT", "LAURUSLABS", "LICI", "LODHA", "LUPIN", "M&M",
    "MANAPPURAM", "MANKIND", "MARICO", "MARUTI", "MFSL", "MAXHEALTH",
    "MAZDOCK", "MPHASIS", "MCX", "MUTHOOTFIN", "NBCC", "NCC",
    "NHPC", "NMDC", "NTPC", "NATIONALUM", "NESTLEIND", "NUVAMA",
    "OBEROIRLTY", "ONGC", "OIL", "PAYTM", "OFSS", "POLICYBZR",
    "PGEL", "PIIND", "PNBHOUSING", "PAGEIND", "PATANJALI", "PERSISTENT",
    "PETRONET", "PIDILITIND", "PPLPHARMA", "POLYCAB", "PFC", "POWERGRID",
    "PRESTIGE", "PNB", "RBLBANK", "RECLTD", "RVNL", "RELIANCE",
    "SBICARD", "SBILIFE", "SHREECEM", "SRF", "SAMMAANCAP", "MOTHERSON",
    "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS", "SBIN", "SAIL",
    "SUNPHARMA", "SUPREMEIND", "SUZLON", "SYNGENE", "TATACONSUM", "TITAGARH",
    "TVSMOTOR", "TCS", "TATAELXSI", "TMPV", "TATAPOWER", "TATASTEEL",
    "TATATECH", "TECHM", "FEDERALBNK", "INDHOTEL", "PHOENIXLTD", "TITAN",
    "TORNTPHARM", "TORNTPOWER", "TRENT", "TIINDIA", "UNOMINDA", "UPL",
    "ULTRACEMCO", "UNIONBANK", "UNITDSPR", "VBL", "VEDL", "IDEA",
    "VOLTAS", "WIPRO", "YESBANK", "ZYDUSLIFE",
]

# Known ISIN mappings (from Upstox API responses we've tested)
KNOWN_ISINS = {
    "RELIANCE": "INE002A01018",
}

def fetch_from_upstox(symbol: str, token: str) -> Optional[str]:
    """
    Try to extract ISIN from Upstox LTP API by testing with generic format
    and checking if we get a valid response with the actual key
    """
    try:
        # Try the generic format
        instrument_key = f"NSE_EQ|INE{symbol}01012"
        
        response = requests.get(
            "https://api.upstox.com/v2/market-quote/ltp",
            params={"mode": "LTP", "symbol": instrument_key},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            # If we got data back, the ISIN was correct
            if data.get("data") and len(data["data"]) > 0:
                # Extract the actual key from response
                for key in data["data"].keys():
                    # Return the ISIN part (after NSE_EQ:)
                    if "|" in str(data["data"][key].get("instrument_token", "")):
                        isin = data["data"][key]["instrument_token"].split("|")[1]
                        print(f"✅ {symbol}: {isin}")
                        return isin
        
        return None
    except Exception as e:
        print(f"❌ {symbol}: Error - {e}")
        return None

def fetch_from_moneycontrol(symbol: str) -> Optional[str]:
    """
    Try to fetch ISIN from MoneyControl
    """
    try:
        # MoneyControl URL pattern
        url = f"https://www.moneycontrol.com/india/stockpricequote/{symbol.lower()}/stock-price"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        # Look for ISIN in the HTML
        if "ISIN" in response.text:
            # Simple extraction - this is basic, might need refinement
            lines = response.text.split('\n')
            for i, line in enumerate(lines):
                if 'ISIN' in line and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if next_line.startswith('INE'):
                        return next_line.strip()
        
        return None
    except Exception as e:
        # Silently fail for web scraping
        return None

def main():
    print("=" * 60)
    print("Fetching ISIN codes for 208 NSE FNO symbols")
    print("=" * 60)
    
    # Token from earlier session (may be expired)
    token = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI0OUNMQlEiLCJqdGkiOiI2OTJhN2YxM2JhYzQ4MDMwYmFiODJiODYiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzY0MzkyNzIzLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NjY0NTM2MDB9.3JrhmmxFkKS9BRPdIW21ShgMrdhnV_f6PlQcb7-gKog"
    
    isins_found = {}
    isins_missing = []
    
    print("\n1️⃣  Testing with Upstox API (generic format)...")
    for i, symbol in enumerate(FNO_SYMBOLS, 1):
        if symbol in KNOWN_ISINS:
            print(f"✅ {symbol}: {KNOWN_ISINS[symbol]} (known)")
            isins_found[symbol] = KNOWN_ISINS[symbol]
            continue
        
        isin = fetch_from_upstox(symbol, token)
        if isin:
            isins_found[symbol] = isin
        else:
            isins_missing.append(symbol)
        
        # Rate limiting
        if i % 10 == 0:
            print(f"   Progress: {i}/{len(FNO_SYMBOLS)}")
            time.sleep(1)
    
    print(f"\n📊 Results Summary:")
    print(f"   Found: {len(isins_found)}/208")
    print(f"   Missing: {len(isins_missing)}/208")
    
    # Export results
    results = {
        "found": isins_found,
        "missing": isins_missing,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open("isin_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results exported to isin_results.json")
    
    if isins_missing:
        print(f"\n❓ Missing ISINs for {len(isins_missing)} symbols:")
        print(", ".join(isins_missing[:20]))
        if len(isins_missing) > 20:
            print(f"... and {len(isins_missing) - 20} more")

if __name__ == "__main__":
    main()
