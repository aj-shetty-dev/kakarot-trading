#!/usr/bin/env python3
"""
Test all 208 NSE FNO symbols using CORRECT ISIN format
This validates that all symbols work with Upstox API when using full ISINs

Previous Issue: Using simple symbol names (e.g., "INFY") returned empty data
Solution: Use full ISIN format (e.g., "NSE_EQ|INE009A01021") for API calls

This script:
1. Loads ISIN mapping for all 208 symbols
2. Tests each symbol by calling Upstox LTP API with correct format
3. Validates that API returns valid LTP data
4. Generates a report of working symbols
"""

import subprocess
import json
import time
from collections import defaultdict
from pathlib import Path
import sys

# Import ISIN mapping
sys.path.insert(0, str(Path(__file__).parent / "backend" / "src" / "data"))
try:
    from isin_mapping_hardcoded import ISIN_MAPPING, get_instrument_key
except ImportError:
    print("❌ ERROR: Could not import isin_mapping_hardcoded")
    print("   Make sure fetch_isins_complete.py has been run first")
    sys.exit(1)


def get_token():
    """Extract access token from .env file"""
    try:
        with open("backend/.env") as f:
            for line in f:
                if "UPSTOX_ACCESS_TOKEN=" in line:
                    token = line.split('=')[1].strip()
                    if token and token != "your_token_here":
                        return token
    except FileNotFoundError:
        pass
    return None


def test_symbol_ltp_with_isin(symbol: str, isin: str, token: str) -> tuple:
    """
    Test a symbol using ISIN format
    
    Returns:
        tuple: (success: bool, ltp: float or None, error_msg: str or None)
    """
    try:
        # CORRECT FORMAT: Use full ISIN
        instrument_key = f"NSE_EQ|{isin}"
        
        cmd = [
            "curl", "-s", "-X", "GET",
            f"https://api.upstox.com/v2/market-quote/ltp?mode=LTP&symbol={instrument_key}",
            "-H", f"Authorization: Bearer {token}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            return False, None, "Request failed"
        
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False, None, "JSON parse error"
        
        # Check status
        if data.get("status") != "success":
            message = data.get("message", "Unknown error")
            return False, None, f"API error: {message}"
        
        if "data" not in data or not data["data"]:
            return False, None, "No data in response"
        
        # Extract LTP from response
        for key, val in data["data"].items():
            if isinstance(val, dict) and "last_price" in val:
                ltp = val["last_price"]
                return True, ltp, None
        
        return False, None, "No LTP field in response"
        
    except subprocess.TimeoutExpired:
        return False, None, "Timeout"
    except Exception as e:
        return False, None, str(e)[:50]


def main():
    """Main test function"""
    print("=" * 110)
    print("🧪 TESTING ALL 208 NSE FNO SYMBOLS - WITH CORRECT ISIN FORMAT")
    print("=" * 110)
    print()
    
    # Get token
    token = get_token()
    if not token:
        print("❌ ERROR: Could not find valid UPSTOX_ACCESS_TOKEN in .env file")
        print()
        print("To run this test:")
        print("  1. Add your Upstox access token to backend/.env")
        print("  2. Ensure token is not expired")
        print()
        return 1
    
    print(f"✅ Access token loaded (length: {len(token)})")
    print(f"✅ ISIN mapping loaded: {len(ISIN_MAPPING)} symbols")
    print()
    
    # Get all symbols
    symbols = sorted(ISIN_MAPPING.keys())
    
    print("=" * 110)
    print("🧪 TESTING SYMBOLS...")
    print("=" * 110)
    print()
    
    successful = 0
    failed = 0
    failed_symbols = []
    ltps = {}
    
    start_time = time.time()
    
    for i, symbol in enumerate(symbols, 1):
        isin = ISIN_MAPPING[symbol]
        success, ltp, error = test_symbol_ltp_with_isin(symbol, isin, token)
        
        if success:
            successful += 1
            ltps[symbol] = ltp
            
            # Print progress (first 15, then every 20th, plus last one)
            if i <= 15 or i % 20 == 0 or i == len(symbols):
                print(f"✅ {i:3}/{len(symbols):3} {symbol:15} (ISIN: {isin:15}) → LTP: ₹{ltp:>8.2f}")
            elif i % 5 == 0:
                print(f"   ({i:3}/{len(symbols):3} symbols tested...)")
        else:
            failed += 1
            failed_symbols.append((symbol, isin, error))
            print(f"❌ {i:3}/{len(symbols):3} {symbol:15} (ISIN: {isin:15}) → ERROR: {error}")
        
        # Small delay to avoid rate limiting
        if i % 10 == 0:
            time.sleep(0.5)
    
    elapsed_time = time.time() - start_time
    
    print()
    print("=" * 110)
    print("📊 TEST RESULTS SUMMARY:")
    print("=" * 110)
    print()
    print(f"   Total Symbols Tested:     {len(symbols)}")
    print(f"   ✅ Successful:             {successful}")
    print(f"   ❌ Failed:                 {failed}")
    print(f"   Success Rate:              {(successful/len(symbols)*100):.1f}%")
    print(f"   Time Taken:                {elapsed_time:.1f} seconds")
    print(f"   Average time/symbol:       {(elapsed_time/len(symbols))*1000:.0f}ms")
    print()
    
    if successful > 0:
        print("=" * 110)
        print("📈 LTP STATISTICS (from successful calls):")
        print("=" * 110)
        print()
        
        ltps_list = list(ltps.values())
        min_ltp = min(ltps_list)
        max_ltp = max(ltps_list)
        avg_ltp = sum(ltps_list) / len(ltps_list)
        
        print(f"   Lowest LTP:                ₹{min_ltp:.2f}")
        print(f"   Highest LTP:               ₹{max_ltp:.2f}")
        print(f"   Average LTP:               ₹{avg_ltp:.2f}")
        print(f"   Symbols with LTP:          {len(ltps_list)}")
        print()
    
    if failed_symbols:
        print("=" * 110)
        print("❌ FAILED SYMBOLS (Details):")
        print("=" * 110)
        print()
        
        error_types = defaultdict(list)
        for symbol, isin, reason in failed_symbols:
            error_types[reason].append((symbol, isin))
        
        for error_reason, syms in sorted(error_types.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"   [{len(syms)} symbols] {error_reason}:")
            for sym, isin in syms[:5]:  # Show first 5
                print(f"      • {sym:15} (ISIN: {isin})")
            if len(syms) > 5:
                print(f"      ... and {len(syms) - 5} more")
        print()
    else:
        print("=" * 110)
        print("✅ ALL 208 SYMBOLS VALIDATED SUCCESSFULLY WITH CORRECT ISIN FORMAT!")
        print("=" * 110)
        print()
    
    # Save results
    output_file = Path("test_results_isin_validation.txt")
    with open(output_file, "w") as f:
        f.write("ISIN VALIDATION TEST RESULTS\n")
        f.write("=" * 110 + "\n\n")
        f.write(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Symbols: {len(symbols)}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Failed: {failed}\n")
        f.write(f"Success Rate: {(successful/len(symbols)*100):.1f}%\n\n")
        
        f.write("SUCCESSFUL SYMBOLS WITH LTP:\n")
        f.write("-" * 110 + "\n")
        f.write("Symbol           ISIN             LTP (₹)\n")
        f.write("-" * 110 + "\n")
        for symbol in sorted(symbols):
            if symbol in ltps:
                isin = ISIN_MAPPING[symbol]
                f.write(f"{symbol:15} {isin:15} ₹{ltps[symbol]:>10.2f}\n")
        
        if failed_symbols:
            f.write("\n\nFAILED SYMBOLS:\n")
            f.write("-" * 110 + "\n")
            f.write("Symbol           ISIN             Error\n")
            f.write("-" * 110 + "\n")
            for symbol, isin, reason in failed_symbols:
                f.write(f"{symbol:15} {isin:15} {reason}\n")
    
    print(f"📄 Results saved to: {output_file}")
    print()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
