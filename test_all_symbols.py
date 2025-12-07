#!/usr/bin/env python3
"""
Test all 208 symbols by calling Upstox API to validate they exist
This verifies that our symbol list matches Upstox's available symbols
"""

import subprocess
import json
import time
from collections import defaultdict

def get_token():
    """Extract access token from .env file"""
    with open("backend/.env") as f:
        for line in f:
            if "UPSTOX_ACCESS_TOKEN=" in line:
                return line.split('=')[1].strip()
    return None

def get_symbols_from_db():
    """Get all unique base symbols from database"""
    result = subprocess.run([
        "docker", "compose", "exec", "-T", "postgres", "psql", 
        "-U", "upstox_user", "-d", "upstox_trading", 
        "-c", "SELECT DISTINCT symbol FROM subscribed_options ORDER BY symbol;"
    ], capture_output=True, text=True, cwd="/Users/shetta20/Projects/upstox")
    
    lines = result.stdout.strip().split('\n')
    
    symbols = []
    for line in lines:
        line = line.strip()
        if line and 'symbol' not in line.lower() and '---' not in line and '(' not in line and len(line) > 0:
            symbols.append(line)
    
    return symbols

def test_symbol_ltp(symbol, token):
    """
    Test a single symbol by calling Upstox LTP API
    
    Returns:
        tuple: (success: bool, ltp: float or None, error_msg: str or None)
    """
    try:
        # Construct NSE EQ instrument key
        instrument_key = f"NSE_EQ|INE{symbol}01012"
        
        cmd = [
            "curl", "-s", "-X", "GET",
            f"https://api.upstox.com/v2/market-quote/ltp?mode=LTP&symbol={instrument_key}",
            "-H", f"Authorization: Bearer {token}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            return False, None, "Request failed"
        
        data = json.loads(result.stdout)
        
        if data.get("status") != "success":
            return False, None, f"API error: {data.get('message', 'Unknown')}"
        
        if "data" not in data or not data["data"]:
            return False, None, "No data in response"
        
        # Extract LTP from response
        # Response key format: "NSE_EQ:SYMBOL" (with colon, not pipe)
        for key, val in data["data"].items():
            if isinstance(val, dict) and "last_price" in val:
                ltp = val["last_price"]
                return True, ltp, None
        
        return False, None, "No LTP in response"
        
    except json.JSONDecodeError:
        return False, None, "JSON parse error"
    except subprocess.TimeoutExpired:
        return False, None, "Timeout"
    except Exception as e:
        return False, None, str(e)[:50]

def main():
    """Main test function"""
    print("=" * 100)
    print("🔍 TESTING ALL 208 BASE SYMBOLS - LTP API VALIDATION")
    print("=" * 100)
    print()
    
    # Get token
    token = get_token()
    if not token:
        print("❌ ERROR: Could not find UPSTOX_ACCESS_TOKEN in .env file")
        return
    
    print(f"✅ Access token loaded (length: {len(token)})")
    print()
    
    # Get symbols
    symbols = get_symbols_from_db()
    print(f"✅ Loaded {len(symbols)} symbols from database")
    print()
    
    if not symbols:
        print("❌ ERROR: No symbols found in database")
        return
    
    # Test all symbols
    print("=" * 100)
    print("🧪 TESTING SYMBOLS...")
    print("=" * 100)
    print()
    
    successful = 0
    failed = 0
    failed_symbols = []
    ltps = {}
    
    start_time = time.time()
    
    for i, symbol in enumerate(symbols, 1):
        success, ltp, error = test_symbol_ltp(symbol, token)
        
        if success:
            successful += 1
            ltps[symbol] = ltp
            
            # Print progress (first 15, then every 20th, plus last one)
            if i <= 15 or i % 20 == 0 or i == len(symbols):
                print(f"✅ {i:3}/{len(symbols):3} {symbol:15} → LTP: ₹{ltp:>8.2f}")
            elif i % 5 == 0:
                print(f"   ({i:3}/{len(symbols):3} symbols processed...)")
        else:
            failed += 1
            failed_symbols.append((symbol, error))
            print(f"❌ {i:3}/{len(symbols):3} {symbol:15} → ERROR: {error}")
        
        # Small delay to avoid rate limiting
        if i % 10 == 0:
            time.sleep(0.5)
    
    elapsed_time = time.time() - start_time
    
    print()
    print("=" * 100)
    print("📊 TEST RESULTS SUMMARY:")
    print("=" * 100)
    print()
    print(f"   Total Symbols Tested:     {len(symbols)}")
    print(f"   ✅ Successful:             {successful}")
    print(f"   ❌ Failed:                 {failed}")
    print(f"   Success Rate:              {(successful/len(symbols)*100):.1f}%")
    print(f"   Time Taken:                {elapsed_time:.1f} seconds")
    print()
    
    if successful > 0:
        print("=" * 100)
        print("📈 LTP STATISTICS:")
        print("=" * 100)
        print()
        
        ltps_list = list(ltps.values())
        min_ltp = min(ltps_list)
        max_ltp = max(ltps_list)
        avg_ltp = sum(ltps_list) / len(ltps_list)
        
        print(f"   Lowest LTP:                ₹{min_ltp:.2f}")
        print(f"   Highest LTP:               ₹{max_ltp:.2f}")
        print(f"   Average LTP:               ₹{avg_ltp:.2f}")
        print()
    
    if failed_symbols:
        print("=" * 100)
        print("❌ FAILED SYMBOLS (Details):")
        print("=" * 100)
        print()
        
        error_types = defaultdict(list)
        for symbol, reason in failed_symbols:
            error_types[reason].append(symbol)
        
        for error_reason, syms in sorted(error_types.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"   [{len(syms)} symbols] {error_reason}:")
            for sym in syms[:5]:  # Show first 5
                print(f"      • {sym}")
            if len(syms) > 5:
                print(f"      ... and {len(syms) - 5} more")
        print()
    else:
        print("=" * 100)
        print("✅ ALL SYMBOLS VALIDATED SUCCESSFULLY!")
        print("=" * 100)
        print()
    
    # Save results to file
    output_file = "/tmp/symbol_validation_results.txt"
    with open(output_file, "w") as f:
        f.write("SYMBOL VALIDATION RESULTS\n")
        f.write("=" * 100 + "\n\n")
        f.write(f"Total Symbols: {len(symbols)}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Failed: {failed}\n")
        f.write(f"Success Rate: {(successful/len(symbols)*100):.1f}%\n\n")
        
        f.write("SUCCESSFUL SYMBOLS WITH LTP:\n")
        f.write("-" * 100 + "\n")
        for symbol in sorted(symbols):
            if symbol in ltps:
                f.write(f"{symbol:20} → ₹{ltps[symbol]:10.2f}\n")
        
        if failed_symbols:
            f.write("\n\nFAILED SYMBOLS:\n")
            f.write("-" * 100 + "\n")
            for symbol, reason in failed_symbols:
                f.write(f"{symbol:20} → {reason}\n")
    
    print(f"📄 Results saved to: {output_file}")
    print()

if __name__ == "__main__":
    main()
