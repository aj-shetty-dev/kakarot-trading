#!/usr/bin/env python3
"""
ISIN Validation Script for Upstox Trading Bot
==============================================

This script validates that ALL 208 FNO symbol ISINs are correct by:
1. Loading the ISIN mapping from isin_mapping_hardcoded.py
2. Calling Upstox LTP API (v3) for each symbol using NSE_EQ|ISIN format
3. Verifying we get valid LTP data back
4. Generating a comprehensive report

Usage:
    1. Ensure you have a FRESH Upstox access token in backend/.env
    2. Run: python3 validate_all_isins.py
    3. Check the results - all 208 symbols should return LTP data

If this script succeeds (208/208 working), our ISIN mapping is correct
and the app can use these ISINs for all LTP and options fetching.
"""

import json
import urllib.request
import urllib.parse
import time
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Setup paths
ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / 'backend' / 'src' / 'data'
sys.path.insert(0, str(DATA_PATH))

# Import ISIN mapping
try:
    from isin_mapping_hardcoded import ISIN_MAPPING, get_instrument_key, get_all_symbols
    print(f"✅ Loaded ISIN mapping with {len(ISIN_MAPPING)} symbols")
except ImportError as e:
    print(f"❌ Could not import ISIN mapping: {e}")
    print("   Run fetch_isins_complete.py first to generate the mapping")
    sys.exit(1)


def load_access_token() -> str:
    """Load access token from .env file"""
    env_path = ROOT / 'backend' / '.env'
    if not env_path.exists():
        print("❌ backend/.env file not found")
        sys.exit(1)
    
    for line in env_path.read_text().splitlines():
        if line.startswith('UPSTOX_ACCESS_TOKEN='):
            token = line.split('=', 1)[1].strip()
            if token and token != 'your_token_here':
                return token
    
    print("❌ No valid UPSTOX_ACCESS_TOKEN found in backend/.env")
    sys.exit(1)


def check_token_validity(token: str) -> bool:
    """Check if token is valid and not expired"""
    import base64
    try:
        _, payload, _ = token.split('.')
        payload += '=' * (4 - len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        
        exp_time = data.get('exp', 0)
        current_time = int(time.time())
        
        if exp_time < current_time:
            expired_ago = current_time - exp_time
            hours = expired_ago // 3600
            minutes = (expired_ago % 3600) // 60
            print(f"❌ TOKEN EXPIRED! Expired {hours}h {minutes}m ago")
            print(f"   Please generate a fresh token from Upstox Developer Portal")
            return False
        
        valid_for = exp_time - current_time
        hours = valid_for // 3600
        minutes = (valid_for % 3600) // 60
        print(f"✅ Token valid for {hours}h {minutes}m")
        return True
        
    except Exception as e:
        print(f"⚠️  Could not validate token expiry: {e}")
        return True  # Proceed anyway


def fetch_ltp_batch(symbols: list, token: str) -> dict:
    """
    Fetch LTP for multiple symbols in one API call (up to 500)
    
    Uses Upstox v3 API which supports comma-separated instrument keys
    """
    # Build comma-separated instrument keys
    instrument_keys = []
    for sym in symbols:
        key = get_instrument_key(sym)
        if key:
            instrument_keys.append(key)
    
    if not instrument_keys:
        return {}
    
    # URL encode the comma-separated keys
    keys_param = ','.join(instrument_keys)
    url = f"https://api.upstox.com/v3/market-quote/ltp?instrument_key={urllib.parse.quote(keys_param)}"
    
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            if data.get('status') == 'success':
                return data.get('data', {})
    except Exception as e:
        print(f"⚠️  Batch request failed: {e}")
    
    return {}


def fetch_ltp_single(symbol: str, token: str) -> tuple:
    """
    Fetch LTP for a single symbol
    
    Returns: (ltp, volume, error_msg)
    """
    instrument_key = get_instrument_key(symbol)
    if not instrument_key:
        return None, None, "No ISIN mapping"
    
    url = f"https://api.upstox.com/v3/market-quote/ltp?instrument_key={urllib.parse.quote(instrument_key)}"
    
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            
            if data.get('status') != 'success':
                return None, None, f"API error: {data.get('message', 'Unknown')}"
            
            payload = data.get('data', {})
            
            # Try to find our instrument key in response
            if instrument_key in payload:
                entry = payload[instrument_key]
            else:
                # Try first entry
                entry = next(iter(payload.values()), {})
            
            ltp = entry.get('last_price')
            volume = entry.get('volume')
            
            if ltp is not None:
                return ltp, volume, None
            else:
                return None, None, "No last_price in response"
                
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()
            error_data = json.loads(error_body)
            return None, None, f"HTTP {e.code}: {error_data.get('message', e.reason)}"
        except:
            return None, None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, None, str(e)[:50]


def validate_all_symbols(token: str, batch_size: int = 50) -> dict:
    """
    Validate all 208 symbols by fetching LTP
    
    Returns dict with results
    """
    all_symbols = get_all_symbols()
    total = len(all_symbols)
    
    print(f"\n{'='*80}")
    print(f"🧪 VALIDATING {total} SYMBOLS AGAINST UPSTOX LTP API")
    print(f"{'='*80}\n")
    
    results = {
        'success': [],
        'failed': [],
        'errors': defaultdict(list)
    }
    
    start_time = time.time()
    
    # Process symbols one by one for detailed error tracking
    for i, symbol in enumerate(all_symbols, 1):
        isin = ISIN_MAPPING.get(symbol)
        ltp, volume, error = fetch_ltp_single(symbol, token)
        
        if error:
            results['failed'].append(symbol)
            results['errors'][error].append(symbol)
            status = f"❌ ERROR: {error}"
        else:
            results['success'].append((symbol, ltp, volume))
            status = f"✅ LTP: ₹{ltp:,.2f}"
        
        # Progress output
        if i <= 10 or i % 20 == 0 or i == total:
            print(f"[{i:3}/{total}] {symbol:15} (ISIN: {isin}) → {status}")
        
        # Rate limiting - small delay between requests
        if i % 5 == 0:
            time.sleep(0.2)
    
    elapsed = time.time() - start_time
    
    return {
        'success': results['success'],
        'failed': results['failed'],
        'errors': dict(results['errors']),
        'total': total,
        'elapsed': elapsed
    }


def generate_report(results: dict) -> str:
    """Generate validation report"""
    success_count = len(results['success'])
    failed_count = len(results['failed'])
    total = results['total']
    elapsed = results['elapsed']
    
    report = []
    report.append("\n" + "="*80)
    report.append("📊 ISIN VALIDATION REPORT")
    report.append("="*80)
    report.append(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Symbols: {total}")
    report.append(f"✅ Successful: {success_count} ({success_count/total*100:.1f}%)")
    report.append(f"❌ Failed: {failed_count} ({failed_count/total*100:.1f}%)")
    report.append(f"Time Elapsed: {elapsed:.1f} seconds")
    report.append(f"Avg per symbol: {elapsed/total*1000:.0f}ms")
    
    if results['success']:
        report.append("\n" + "-"*80)
        report.append("📈 LTP STATISTICS (Successful Symbols)")
        report.append("-"*80)
        
        ltps = [ltp for _, ltp, _ in results['success'] if ltp]
        if ltps:
            report.append(f"Min LTP: ₹{min(ltps):,.2f}")
            report.append(f"Max LTP: ₹{max(ltps):,.2f}")
            report.append(f"Avg LTP: ₹{sum(ltps)/len(ltps):,.2f}")
    
    if results['errors']:
        report.append("\n" + "-"*80)
        report.append("❌ ERRORS BY TYPE")
        report.append("-"*80)
        
        for error_type, symbols in sorted(results['errors'].items(), key=lambda x: -len(x[1])):
            report.append(f"\n[{len(symbols)} symbols] {error_type}:")
            for sym in symbols[:5]:
                report.append(f"   • {sym}")
            if len(symbols) > 5:
                report.append(f"   ... and {len(symbols)-5} more")
    
    if success_count == total:
        report.append("\n" + "="*80)
        report.append("🎉 ALL 208 SYMBOLS VALIDATED SUCCESSFULLY!")
        report.append("   The ISIN mapping is correct and ready for production use.")
        report.append("="*80)
    elif success_count > 0:
        report.append("\n" + "="*80)
        report.append(f"⚠️  PARTIAL SUCCESS: {success_count}/{total} symbols working")
        report.append("   Check the failed symbols above for issues.")
        report.append("="*80)
    else:
        report.append("\n" + "="*80)
        report.append("❌ ALL SYMBOLS FAILED")
        report.append("   This is likely a token issue. Please check:")
        report.append("   1. Token is not expired")
        report.append("   2. Token has market data permissions")
        report.append("   3. Markets are open (for live data)")
        report.append("="*80)
    
    return "\n".join(report)


def save_results(results: dict, report: str):
    """Save results to files"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save detailed JSON results
    json_file = ROOT / f'isin_validation_results_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'total': results['total'],
            'success_count': len(results['success']),
            'failed_count': len(results['failed']),
            'success': [(s, ltp, vol) for s, ltp, vol in results['success']],
            'failed': results['failed'],
            'errors': results['errors']
        }, f, indent=2)
    print(f"\n📄 JSON results saved to: {json_file}")
    
    # Save text report
    report_file = ROOT / f'isin_validation_report_{timestamp}.txt'
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"📄 Report saved to: {report_file}")
    
    # Also save a summary file for quick reference
    summary_file = ROOT / 'ISIN_VALIDATION_SUMMARY.md'
    with open(summary_file, 'w') as f:
        f.write(f"# ISIN Validation Summary\n\n")
        f.write(f"**Last Run**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Results\n")
        f.write(f"- **Total Symbols**: {results['total']}\n")
        f.write(f"- **Successful**: {len(results['success'])}\n")
        f.write(f"- **Failed**: {len(results['failed'])}\n")
        f.write(f"- **Success Rate**: {len(results['success'])/results['total']*100:.1f}%\n\n")
        
        if len(results['success']) == results['total']:
            f.write("## ✅ Status: ALL SYMBOLS VALIDATED\n\n")
            f.write("The ISIN mapping is correct. The application can use these ISINs for:\n")
            f.write("1. Fetching LTP at startup\n")
            f.write("2. Getting options chains\n")
            f.write("3. WebSocket subscriptions\n")
        else:
            f.write("## ⚠️ Status: PARTIAL SUCCESS\n\n")
            f.write("Some symbols failed. Check the detailed report for issues.\n")
        
        f.write(f"\n## Sample Successful LTPs\n\n")
        f.write("| Symbol | LTP (₹) | Volume |\n")
        f.write("|--------|---------|--------|\n")
        for sym, ltp, vol in results['success'][:10]:
            vol_str = f"{vol:,}" if vol else "N/A"
            f.write(f"| {sym} | {ltp:,.2f} | {vol_str} |\n")
    
    print(f"📄 Summary saved to: {summary_file}")


def main():
    print("="*80)
    print("🔍 UPSTOX ISIN VALIDATION TOOL")
    print("   Validates all 208 FNO symbols against Upstox LTP API")
    print("="*80)
    
    # Load and validate token
    print("\n📌 Step 1: Loading access token...")
    token = load_access_token()
    print(f"   Token loaded (length: {len(token)})")
    
    print("\n📌 Step 2: Checking token validity...")
    if not check_token_validity(token):
        print("\n⚠️  Please update the token in backend/.env and run again")
        return 1
    
    print("\n📌 Step 3: Validating symbols...")
    results = validate_all_symbols(token)
    
    print("\n📌 Step 4: Generating report...")
    report = generate_report(results)
    print(report)
    
    print("\n📌 Step 5: Saving results...")
    save_results(results, report)
    
    # Return exit code based on success
    if len(results['success']) == results['total']:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
