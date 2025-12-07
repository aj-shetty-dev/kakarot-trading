#!/usr/bin/env python3
"""
Test symbols with detailed logging - DEBUG VERSION
Start with 5 symbols to identify issues
"""

import subprocess
import json
import time

def get_token():
    """Extract access token from .env file"""
    with open("backend/.env") as f:
        for line in f:
            if "UPSTOX_ACCESS_TOKEN=" in line:
                return line.split('=')[1].strip()
    return None

def get_symbols_from_db(limit=5):
    """Get symbols from database with limit for testing"""
    result = subprocess.run([
        "docker", "compose", "exec", "-T", "postgres", "psql", 
        "-U", "upstox_user", "-d", "upstox_trading", 
        "-c", "SELECT DISTINCT symbol FROM subscribed_options ORDER BY symbol LIMIT {};".format(limit)
    ], capture_output=True, text=True, cwd="/Users/shetta20/Projects/upstox")
    
    lines = result.stdout.strip().split('\n')
    
    symbols = []
    for line in lines:
        line = line.strip()
        if line and 'symbol' not in line.lower() and '---' not in line and '(' not in line and len(line) > 0:
            symbols.append(line)
    
    return symbols

def test_symbol_ltp_verbose(symbol, token, test_num):
    """
    Test a single symbol with verbose logging
    """
    print()
    print("=" * 80)
    print(f"TEST #{test_num}: {symbol}")
    print("=" * 80)
    
    try:
        # Try different instrument key formats
        formats = [
            ("Format 1: NSE_EQ|INE{SYMBOL}01012", f"NSE_EQ|INE{symbol}01012"),
            ("Format 2: NSE_EQ|{SYMBOL}", f"NSE_EQ|{symbol}"),
        ]
        
        for format_name, instrument_key in formats:
            print()
            print(f"📌 Trying {format_name}")
            print(f"   Instrument Key: {instrument_key}")
            print(f"   URL Encoded: {instrument_key.replace('|', '%7C')}")
            
            cmd = [
                "curl", "-s", "-X", "GET",
                f"https://api.upstox.com/v2/market-quote/ltp?mode=LTP&symbol={instrument_key.replace('|', '%7C')}",
                "-H", f"Authorization: Bearer {token[:20]}..."
            ]
            
            print(f"   Command: curl -s -X GET [URL] -H Authorization...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            print(f"   Return Code: {result.returncode}")
            
            if result.returncode != 0:
                print(f"   ❌ Request failed")
                continue
            
            print(f"   Raw Response Length: {len(result.stdout)} bytes")
            print(f"   Raw Response (first 200 chars): {result.stdout[:200]}")
            
            try:
                data = json.loads(result.stdout)
                print(f"   ✅ JSON parsed successfully")
                print(f"   Status: {data.get('status')}")
                print(f"   Data keys: {list(data.get('data', {}).keys())}")
                
                if data.get("status") == "success":
                    data_obj = data.get("data", {})
                    
                    if not data_obj:
                        print(f"   ⚠️  Data object is empty")
                    else:
                        for key, val in data_obj.items():
                            print(f"      Key: '{key}'")
                            print(f"      Value type: {type(val)}")
                            if isinstance(val, dict):
                                print(f"      Value keys: {list(val.keys())}")
                                if "last_price" in val:
                                    ltp = val["last_price"]
                                    print(f"      ✅ FOUND LTP: ₹{ltp}")
                                    return True, ltp, None
                                else:
                                    print(f"      ❌ No 'last_price' key")
                            else:
                                print(f"      Value: {val}")
                else:
                    print(f"   ❌ Status is not 'success': {data.get('status')}")
                    print(f"   Message: {data.get('message', 'N/A')}")
                    
            except json.JSONDecodeError as e:
                print(f"   ❌ JSON parse error: {e}")
        
        print()
        print(f"❌ FAILED: Could not get LTP for {symbol}")
        return False, None, "No valid format worked"
        
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout")
        return False, None, "Timeout"
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False, None, str(e)[:50]

def main():
    """Main test function"""
    print("=" * 80)
    print("🔍 SYMBOL VALIDATION - DEBUG MODE (5 SYMBOLS)")
    print("=" * 80)
    print()
    
    # Get token
    token = get_token()
    if not token:
        print("❌ ERROR: Could not find UPSTOX_ACCESS_TOKEN in .env file")
        return
    
    print(f"✅ Access token loaded (length: {len(token)})")
    print()
    
    # Get symbols (limit to 5 for debugging)
    symbols = get_symbols_from_db(limit=5)
    print(f"✅ Loaded {len(symbols)} symbols from database")
    print(f"   Symbols: {symbols}")
    print()
    
    if not symbols:
        print("❌ ERROR: No symbols found in database")
        return
    
    # Test all symbols with verbose logging
    successful = 0
    failed = 0
    
    for i, symbol in enumerate(symbols, 1):
        success, ltp, error = test_symbol_ltp_verbose(symbol, token, i)
        
        if success:
            successful += 1
        else:
            failed += 1
        
        time.sleep(1)  # Delay between requests
    
    print()
    print("=" * 80)
    print("📊 SUMMARY:")
    print("=" * 80)
    print(f"   Successful: {successful}/{len(symbols)}")
    print(f"   Failed: {failed}/{len(symbols)}")
    print()

if __name__ == "__main__":
    main()
