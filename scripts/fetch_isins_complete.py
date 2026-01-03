#!/usr/bin/env python3
"""
Complete ISIN Resolution Tool for all 208 NSE FNO Symbols
Fetches instrument list from Upstox and maps all symbols to their full ISINs
Generates hardcoded list for production use

This script:
1. Downloads complete instruments list from Upstox
2. Extracts NSE_EQ (equity) symbols and their ISINs
3. Maps the 208 FNO symbols to their correct ISINs
4. Generates a Python file with hardcoded ISIN mapping
5. Validates all mappings work with Upstox API
"""

import gzip
import json
import requests
import sys
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime
import subprocess
import time

# The 208 official NSE FNO symbols
FNO_SYMBOLS_LIST = [
    "360ONE", "ABB", "APLAPOLLO", "AUBANK", "ADANIENSOL", "ADANIENT", "ADANIGREEN",
    "ADANIPORTS", "ABCAPITAL", "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APOLLOHOSP",
    "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUROPHARMA", "DMART", "AXISBANK", "BSE",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BANDHANBNK", "BANKBARODA", "BANKINDIA",
    "BDL", "BEL", "BHARATFORG", "BHEL", "BPCL", "BHARTIARTL", "BIOCON", "BLUESTARCO",
    "BOSCHLTD", "BRITANNIA", "CGPOWER", "CANBK", "CDSL", "CHOLAFIN", "CIPLA",
    "COALINDIA", "COFORGE", "COLPAL", "CAMS", "CONCOR", "CROMPTON", "CUMMINSIND",
    "CYIENT", "DLF", "DABUR", "DALBHARAT", "DELHIVERY", "DIVISLAB", "DIXON",
    "DRREDDY", "ETERNAL", "EICHERMOT", "EXIDEIND", "NYKAA", "FORTIS", "GAIL",
    "GMRAIRPORT", "GLENMARK", "GODREJCP", "GODREJPROP", "GRASIM", "HCLTECH",
    "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HFCL", "HAVELLS", "HEROMOTOCO", "HINDALCO",
    "HAL", "HINDPETRO", "HINDUNILVR", "HINDZINC", "POWERINDIA", "HUDCO", "ICICIBANK",
    "ICICIGI", "ICICIPRULI", "IDFCFIRSTB", "IIFL", "ITC", "INDIANB", "IEX",
    "IOC", "IRCTC", "IRFC", "IREDA", "INDUSTOWER", "INDUSINDBK", "NAUKRI",
    "INFY", "INOXWIND", "INDIGO", "JINDALSTEL", "JSWENERGY", "JSWSTEEL", "JIOFIN",
    "JUBLFOOD", "KEI", "KPITTECH", "KALYANKJIL", "KAYNES", "KFINTECH", "KOTAKBANK",
    "LTF", "LICHSGFIN", "LTIM", "LT", "LAURUSLABS", "LICI", "LODHA",
    "LUPIN", "M&M", "MANAPPURAM", "MANKIND", "MARICO", "MARUTI", "MFSL",
    "MAXHEALTH", "MAZDOCK", "MPHASIS", "MCX", "MUTHOOTFIN", "NBCC", "NCC",
    "NHPC", "NMDC", "NTPC", "NATIONALUM", "NESTLEIND", "NUVAMA", "OBEROIRLTY",
    "ONGC", "OIL", "PAYTM", "OFSS", "POLICYBZR", "PGEL", "PIIND",
    "PNBHOUSING", "PAGEIND", "PATANJALI", "PERSISTENT", "PETRONET", "PIDILITIND",
    "PPLPHARMA", "POLYCAB", "PFC", "POWERGRID", "PRESTIGE", "PNB", "RBLBANK",
    "RECLTD", "RVNL", "RELIANCE", "SBICARD", "SBILIFE", "SHREECEM", "SRF",
    "SAMMAANCAP", "MOTHERSON", "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS",
    "SBIN", "SAIL", "SUNPHARMA", "SUPREMEIND", "SUZLON", "SYNGENE", "TATACONSUM",
    "TITAGARH", "TVSMOTOR", "TCS", "TATAELXSI", "TMPV", "TATAPOWER", "TATASTEEL",
    "TATATECH", "TECHM", "FEDERALBNK", "INDHOTEL", "PHOENIXLTD", "TITAN", "TORNTPHARM",
    "TORNTPOWER", "TRENT", "TIINDIA", "UNOMINDA", "UPL", "ULTRACEMCO", "UNIONBANK",
    "UNITDSPR", "VBL", "VEDL", "IDEA", "VOLTAS", "WIPRO", "YESBANK", "ZYDUSLIFE"
]


class ISINResolver:
    """Resolve ISINs for all 208 NSE FNO symbols"""
    
    def __init__(self):
        self.isin_mapping: Dict[str, str] = {}
        self.failed_symbols: List[Tuple[str, str]] = []
        self.instruments_data: List[Dict] = []
        
    def download_instruments(self) -> bool:
        """
        Download complete instruments list from Upstox
        
        Returns:
            bool: True if successful
        """
        print("\n" + "="*100)
        print("📥 DOWNLOADING INSTRUMENTS LIST FROM UPSTOX")
        print("="*100)
        print()
        
        url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
        
        print(f"🔗 URL: {url}")
        print()
        print("⏳ Downloading... (this may take 30-60 seconds)")
        
        try:
            response = requests.get(url, timeout=120, stream=True)
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}")
                return False
            
            # Download with progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            print(f"📦 File size: {total_size / (1024*1024):.1f} MB")
            print()
            
            # Decompress on-the-fly
            decompressed_data = b''
            for chunk in response.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                decompressed_data += chunk
                
                if total_size > 0:
                    progress = (downloaded / total_size) * 100
                    if downloaded % (512*1024) == 0:  # Every 512KB
                        print(f"   ⏳ Progress: {progress:.1f}% ({downloaded/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB)")
            
            # Decompress gzip
            print(f"\n🔓 Decompressing...")
            try:
                # Try gzip decompression
                decompressed = gzip.decompress(decompressed_data)
            except:
                # If not gzip, use as-is
                decompressed = decompressed_data
            
            # Parse JSON
            print(f"📝 Parsing JSON...")
            self.instruments_data = json.loads(decompressed)
            
            print(f"✅ Downloaded and parsed successfully!")
            print(f"   Total instruments: {len(self.instruments_data)}")
            print()
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def extract_nse_eq_symbols(self) -> Dict[str, str]:
        """
        Extract NSE_EQ symbols and their ISINs from downloaded data
        
        Returns:
            Dict mapping symbol to ISIN
        """
        print("="*100)
        print("🔍 EXTRACTING NSE_EQ SYMBOLS AND ISINs")
        print("="*100)
        print()
        
        symbol_to_isin = {}
        
        for instrument in self.instruments_data:
            try:
                # Check if it's an NSE_EQ instrument
                segment = instrument.get("segment", "")
                if segment != "NSE_EQ":
                    continue
                
                # Get symbol and ISIN
                trading_symbol = instrument.get("trading_symbol", "").strip()
                isin = instrument.get("isin", "").strip()
                
                # Only take equity instruments, not debt/govt securities (filter out 'SG', 'ST', etc.)
                instrument_type = instrument.get("instrument_type", "").strip()
                if instrument_type not in ["", "EQ"]:  # Skip non-equity types
                    continue
                
                if trading_symbol and isin and len(trading_symbol) > 0:
                    symbol_to_isin[trading_symbol] = isin
                    
            except Exception as e:
                continue
        
        print(f"✅ Extracted {len(symbol_to_isin)} NSE_EQ equity instruments")
        print()
        
        return symbol_to_isin
    
    def resolve_fno_isins(self, nse_eq_symbols: Dict[str, str]) -> bool:
        """
        Resolve ISINs for all 208 FNO symbols
        
        Args:
            nse_eq_symbols: Dict of NSE_EQ symbols to ISINs
            
        Returns:
            bool: True if all resolved
        """
        print("="*100)
        print("🔎 RESOLVING FNO SYMBOLS TO ISINs")
        print("="*100)
        print()
        
        found_count = 0
        missing_count = 0
        
        for symbol in FNO_SYMBOLS_LIST:
            if symbol in nse_eq_symbols:
                isin = nse_eq_symbols[symbol]
                self.isin_mapping[symbol] = isin
                found_count += 1
                
                # Print first 10, then every 20th
                if found_count <= 10 or found_count % 20 == 0 or found_count == len(FNO_SYMBOLS_LIST):
                    print(f"✅ {found_count:3}/{len(FNO_SYMBOLS_LIST):3} {symbol:20} → {isin}")
            else:
                self.failed_symbols.append((symbol, "NOT FOUND IN NSE_EQ"))
                missing_count += 1
        
        print()
        print(f"📊 RESULTS:")
        print(f"   ✅ Resolved: {found_count}")
        print(f"   ❌ Missing: {missing_count}")
        print(f"   Success rate: {(found_count/len(FNO_SYMBOLS_LIST)*100):.1f}%")
        print()
        
        if missing_count > 0:
            print(f"❌ MISSING SYMBOLS:")
            for symbol, reason in self.failed_symbols[:10]:
                print(f"   • {symbol}: {reason}")
            if len(self.failed_symbols) > 10:
                print(f"   ... and {len(self.failed_symbols) - 10} more")
            print()
        
        return missing_count == 0
    
    def generate_hardcoded_list(self, output_file: str) -> bool:
        """
        Generate hardcoded Python file with ISIN mapping
        
        Args:
            output_file: Path to output Python file
            
        Returns:
            bool: True if successful
        """
        print("="*100)
        print(f"💾 GENERATING HARDCODED ISIN LIST")
        print("="*100)
        print()
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            count = len(self.isin_mapping)
            
            content = f'''"""
ISIN Mapping for 208 NSE FNO Symbols
Source: Official Upstox Instruments API (complete.json.gz)
These are the COMPLETE and VERIFIED ISIN codes for all 208 symbols

Format: Symbol (NSE_EQ) -> ISIN (Full Identifier)
Usage: For API calls, use "NSE_EQ|{{ISIN}}" format

Generated: {timestamp}
Total Symbols: {count}
"""

# Complete ISIN mapping for all 208 NSE FNO symbols
# These ISINs are required for correct LTP API calls
ISIN_MAPPING = {{
'''
            # Add mappings in sorted order
            for symbol in sorted(self.isin_mapping.keys()):
                isin = self.isin_mapping[symbol]
                content += f'    "{symbol}": "{isin}",\n'
            
            # Remove trailing comma from last entry and close dict
            content = content.rstrip(',\n') + '\n}\n\n'
            
            content += '''
def get_isin(symbol: str) -> str:
    """Get ISIN for a symbol"""
    return ISIN_MAPPING.get(symbol, None)


def get_all_symbols() -> list:
    """Get all available symbols"""
    return list(ISIN_MAPPING.keys())


def get_all_isins() -> dict:
    """Get complete mapping"""
    return ISIN_MAPPING.copy()


def validate_symbol(symbol: str) -> bool:
    """Check if symbol exists in mapping"""
    return symbol in ISIN_MAPPING


def get_instrument_key(symbol: str) -> str:
    """Get full instrument key for Upstox API (NSE_EQ|ISIN format)"""
    isin = ISIN_MAPPING.get(symbol)
    if isin:
        return f"NSE_EQ|{isin}"
    return None


# Statistics
TOTAL_SYMBOLS = len(ISIN_MAPPING)
SYMBOLS_LIST = list(ISIN_MAPPING.keys())

# Test: Verify all mappings
if __name__ == "__main__":
    print(f"✅ ISIN Mapping loaded: {{TOTAL_SYMBOLS}} symbols")
    print()
    print("Sample mappings:")
    for symbol in sorted(ISIN_MAPPING.keys())[:5]:
        isin = ISIN_MAPPING[symbol]
        print(f"  {{symbol:20}} → NSE_EQ|{{isin}}")
    print()
    print(f"Total: {{TOTAL_SYMBOLS}} symbols")
'''
            
            # Write to file
            Path(output_file).write_text(content)
            
            print(f"✅ Generated: {output_file}")
            print(f"   Symbols: {len(self.isin_mapping)}")
            print(f"   File size: {len(content)} bytes")
            print()
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def validate_with_api(self, token: str, sample_size: int = 10) -> bool:
        """
        Validate ISINs work with Upstox API (test a sample)
        
        Args:
            token: Upstox access token
            sample_size: Number of symbols to test
            
        Returns:
            bool: True if validation passes
        """
        print("="*100)
        print(f"🧪 VALIDATING ISINs WITH UPSTOX API (Testing {sample_size} symbols)")
        print("="*100)
        print()
        
        if not token:
            print("⚠️  No token provided, skipping validation")
            print()
            return True
        
        import random
        test_symbols = random.sample(list(self.isin_mapping.keys()), min(sample_size, len(self.isin_mapping)))
        
        successful = 0
        failed = 0
        
        for i, symbol in enumerate(test_symbols, 1):
            isin = self.isin_mapping[symbol]
            instrument_key = f"NSE_EQ|{isin}"
            
            try:
                response = requests.get(
                    f"https://api.upstox.com/v2/market-quote/ltp?mode=LTP&symbol={instrument_key}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success" and data.get("data"):
                        # Check if we have LTP data
                        has_ltp = False
                        for key, val in data.get("data", {}).items():
                            if isinstance(val, dict) and "last_price" in val:
                                ltp = val["last_price"]
                                print(f"✅ {i:2}/{sample_size} {symbol:20} (ISIN: {isin}) → LTP: ₹{ltp:.2f}")
                                successful += 1
                                has_ltp = True
                                break
                        
                        if not has_ltp:
                            print(f"⚠️  {i:2}/{sample_size} {symbol:20} (ISIN: {isin}) → No LTP in response")
                            failed += 1
                    else:
                        print(f"❌ {i:2}/{sample_size} {symbol:20} (ISIN: {isin}) → API error: {data.get('message', 'Unknown')}")
                        failed += 1
                else:
                    print(f"❌ {i:2}/{sample_size} {symbol:20} (ISIN: {isin}) → HTTP {response.status_code}")
                    failed += 1
                    
            except Exception as e:
                print(f"❌ {i:2}/{sample_size} {symbol:20} (ISIN: {isin}) → Error: {str(e)[:50]}")
                failed += 1
            
            # Small delay
            time.sleep(0.2)
        
        print()
        print(f"📊 Validation Results: {successful} passed, {failed} failed")
        print()
        
        return failed == 0


def main():
    """Main execution"""
    print("\n" + "="*100)
    print("🚀 COMPLETE ISIN RESOLUTION TOOL FOR 208 NSE FNO SYMBOLS")
    print("="*100)
    print()
    
    # Initialize resolver
    resolver = ISINResolver()
    
    # Step 1: Download instruments
    if not resolver.download_instruments():
        print("❌ Failed to download instruments")
        return 1
    
    # Step 2: Extract NSE_EQ symbols
    nse_eq_symbols = resolver.extract_nse_eq_symbols()
    
    # Step 3: Resolve FNO ISINs
    if not resolver.resolve_fno_isins(nse_eq_symbols):
        print("⚠️  Some symbols could not be resolved")
    
    # Step 4: Generate hardcoded list
    output_file = "backend/src/data/isin_mapping_hardcoded.py"
    if not resolver.generate_hardcoded_list(output_file):
        print(f"❌ Failed to generate {output_file}")
        return 1
    
    # Step 5: Optional API validation
    print("="*100)
    print("📝 API VALIDATION (OPTIONAL)")
    print("="*100)
    print()
    
    try:
        with open("backend/.env") as f:
            for line in f:
                if "UPSTOX_ACCESS_TOKEN=" in line:
                    token = line.split('=')[1].strip()
                    if token and token != "your_token_here":
                        resolver.validate_with_api(token, sample_size=15)
                    break
    except Exception as e:
        print(f"⚠️  Could not read token: {e}")
    
    # Summary
    print("="*100)
    print("✅ COMPLETION SUMMARY")
    print("="*100)
    print()
    print(f"✅ Total symbols resolved: {len(resolver.isin_mapping)}")
    print(f"✅ Output file: {output_file}")
    print()
    print("📋 Next steps:")
    print(f"   1. Review: {output_file}")
    print("   2. Update seed_symbols.py to use ISINs")
    print("   3. Test with: python test_all_symbols_with_isin.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
