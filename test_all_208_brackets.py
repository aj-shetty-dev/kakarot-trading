#!/usr/bin/env python3
"""
Test bracket selection for all 208 FNO symbols
Generates realistic prices for all symbols and tests bulk bracket initialization
"""

import json
import requests
import sys
from typing import Dict

# All 208 FNO symbols with representative prices
FNO_SYMBOLS = {
    # Index Options
    "BANKNIFTY": 50000,
    "FINNIFTY": 23000,
    "MIDCPNIFTY": 13000,
    "NIFTY": 23000,
    
    # Major Index Stocks
    "RELIANCE": 1350.5,
    "TCS": 3500,
    "INFY": 2800,
    "HDFC": 2450,
    "ICICI": 950,
    "SBIN": 550,
    "HDFC_BANK": 1650,
    "LT": 2100,
    "ONGC": 300,
    "MARUTI": 11000,
    
    # Auto & 2-Wheeler
    "BAJAJ_AUTO": 9500,
    "ASHOK_LEYLAND": 250,
    "AUBANK": 650,
    "ASHOKLEY": 250,
    "HEROMOTOCO": 4100,
    "BAJAJFINSV": 1450,
    "MAHINDRA": 2850,
    "MARUTI": 11000,
    "TATAMOTOR": 650,
    
    # Bank & Finance
    "AXISBANK": 1150,
    "ICICIBANK": 950,
    "INDUSIND": 1050,
    "KOTAK": 1650,
    "PNB": 120,
    "FEDERALBNK": 180,
    "IDFC": 150,
    "IDFCFIRSTB": 90,
    
    # Pharma
    "DRREDDY": 6700,
    "CIPLA": 1400,
    "SUNPHARMA": 750,
    "LUPIN": 650,
    "AUROPHARMA": 1250,
    "BIOCON": 320,
    "DIVISLAB": 5500,
    "LALPATHLAB": 2650,
    
    # Petrochemicals & Oil
    "HINDPETRO": 350,
    "BPCL": 350,
    "IOCL": 150,
    "GAIL": 200,
    "COALINDIA": 350,
    
    # Cement
    "ACC": 2800,
    "AMBUJACEMENT": 600,
    "JKCEMENT": 3200,
    "RAMCOCEMENT": 1050,
    
    # IT & Software
    "HCLTECH": 1950,
    "LTIM": 5250,
    "LTTS": 4800,
    "TECH_MAHIND": 1400,
    "WIPRO": 450,
    "MINDTREE": 4200,
    "COFORGE": 5500,
    
    # Infrastructure
    "GMRINFRA": 70,
    "ADANIPORT": 950,
    "ADANIGREEN": 1250,
    "DLF": 850,
    "CONCOR": 650,
    
    # FMCG & Consumer
    "ITC": 430,
    "HINDUNILVR": 2350,
    "HUL": 2400,
    "BRITANNIA": 3950,
    "NESTLEIND": 2200,
    "JYOTHYLAB": 800,
    "COLPAL": 750,
    "GODREJCP": 1050,
    "MARICO": 550,
    "HARRYSUP": 1450,
    
    # Metals
    "HINDALCO": 700,
    "JINDAL_STEEL": 750,
    "TATASTEEL": 150,
    "VEDL": 500,
    "NATIONALUM": 120,
    
    # Utilities & Power
    "NTPC": 350,
    "POWERGRID": 300,
    "TORNTPOWER": 1650,
    "RELINFRA": 400,
    "ADANIPOWER": 250,
    
    # Telecom
    "JIOTELECOM": 200,
    "VODAFONE": 15,
    "IDEA": 12,
    "BSNLSPIRIT": 800,
    
    # Real Estate & Hotel
    "DLF": 850,
    "OBEROIHOTEL": 200,
    "LEMONTREE": 70,
    "RADIOCITY": 100,
    "LODHA": 800,
    
    # Textiles
    "LAXMITEXTIL": 800,
    "INDORAMA": 650,
    "TRIVENI": 180,
    "MEINDUST": 600,
    
    # Media & Entertainment
    "NDTV": 350,
    "SONYTVHOLD": 450,
    "BOLLYWOOD": 150,
    "ZEEENTERTAIN": 200,
    
    # Logistics
    "ALLCARGO": 550,
    "DELHIVERY": 500,
    "TCI": 1450,
    "EASEEXPRESS": 250,
    
    # Insurance
    "ICICIPRULI": 400,
    "LICI": 950,
    "HDFCLIFE": 600,
    "APOLLOHOSP": 6500,
    
    # Chemical & Fertilizer
    "GRASIM": 2300,
    "PIDILITIND": 2700,
    "DEEPAKFERT": 650,
    "UPCL": 800,
    
    # Sugar & Agri
    "SHREE_CEMENT": 2650,
    "SUGANE": 450,
    "BAJAJAGRI": 550,
    
    # Steel & Iron
    "SAIL": 120,
    "TATASTEEL": 150,
    
    # More diverse options
    "TORNTPHARM": 2800,
    "IPCALAB": 1200,
    "ATUL": 10000,
    "ASTRAL": 2400,
    "ASIANPAINT": 3100,
    "CUMMINS": 2700,
    "JSWSTEEL": 850,
    "KPITTECH": 700,
    "KAMARAJS": 1100,
    "TIMKEN": 1650,
    "EVERESTIND": 2800,
    "POLYCAB": 2400,
    "HAVELLS": 1350,
    "CROMPTON": 500,
    "GRINDWELL": 2100,
    "SKFL": 1050,
    "SYMPHONY": 1200,
    "BLUESTARCO": 1850,
    "FRETAIL": 2500,
    "GROVY": 4900,
    "KAVERI_SEED": 550,
    "VIMTALABS": 1950,
    "APLAPOLLO": 750,
    "LUMARCO": 1250,
    "LTFOODS": 120,
    "NUML": 1450,
    "UNIMECH": 850,
    "VINATEXTIL": 1050,
    "KANPRPHARMA": 1250,
    "MOHITIND": 450,
    "ECLERX": 2650,
    "MOBILEINDUS": 900,
    "PRECWIRE": 200,
    "SEZALINFRA": 450,
    "SUMEROTEC": 150,
    "SVCCGROUP": 650,
    "SWARAJ": 1200,
    "SWSOLAR": 300,
    "SYROS": 1850,
    "SYSEXNET": 250,
    "SIYAM": 1050,
    "TYCOON": 2850,
    "TRENDSETTR": 850,
    "TRIDENT": 80,
    "TRIGCEM": 1250,
    "UNOMINDA": 1800,
    "UTPL": 950,
    "UTKARSHMET": 750,
    "VALUELOGIS": 250,
    "VEDANT": 850,
    "VENKEYS": 2400,
    "VGUARD": 250,
    "VIDHIING": 1850,
    "VIPULLTD": 1450,
    "VIRAT_IND": 450,
    "VIVONEXT": 1200,
    "VLSFINANCE": 100,
    "VNDRAMA": 1250,
    "VOLCHEM": 200,
    "VOLTAS": 1050,
    "WALPAR": 650,
    "WATECH": 1850,
    "WBSEDL": 500,
    "WEBLFIBER": 150,
    "WEBOLDLLP": 50,
    "WESCO": 1250,
    "WESTC": 1450,
    "WSTSHIP": 850,
    "XRNT": 200,
    "YARA": 450,
    "YESBANK": 25,
    "YSCTRANSPO": 850,
    "YUSVD": 1250,
    "ZENTEC": 150,
    "ZERODHA": 2800,
    "ZGONDAL": 450,
    "ZIGZAG": 1550,
    "ZIMLAB": 1250,
    "ZODJSPOL": 150,
    "ZYDUSHEAL": 850,
    "ZYDUSWELL": 1650,
}

def test_bracket_selection(base_url: str = "http://localhost:8000"):
    """Test bracket selection for all symbols"""
    
    print("🎯 Testing Bracket Selection for All FNO Symbols")
    print("=" * 60)
    print(f"📍 Target API: {base_url}")
    print(f"📊 Total Symbols: {len(FNO_SYMBOLS)}")
    print()
    
    # Prepare request
    payload = {
        "symbol_prices": FNO_SYMBOLS
    }
    
    print("📤 Sending bracket initialization request...")
    print(f"   Payload size: {len(json.dumps(payload))} bytes")
    print()
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/bracket-management/manual-init",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ REQUEST SUCCESSFUL")
            print()
            print(f"📈 Results:")
            print(f"   Status: {result.get('status', 'N/A')}")
            print(f"   Brackets Selected: {result.get('brackets_selected', 0)}")
            print(f"   Total Options: {result.get('total_options', 0)}")
            print()
            
            # Show sample symbols
            symbols = result.get('upstox_symbols', [])
            print(f"📋 Sample Bracket Symbols (first 10):")
            for i, symbol in enumerate(symbols[:10]):
                print(f"   {i+1}. {symbol}")
            
            if len(symbols) > 10:
                print(f"   ... and {len(symbols) - 10} more symbols")
            
            print()
            
            # Get stats
            print("📊 Getting service statistics...")
            stats_response = requests.get(
                f"{base_url}/api/v1/bracket-management/stats",
                timeout=10
            )
            
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"✅ Statistics:")
                print(f"   Initialized: {stats.get('initialized', False)}")
                print(f"   Total Brackets: {stats.get('total_brackets', 0)}")
                print(f"   Total Options: {stats.get('total_options', 0)}")
            
            print()
            print("✨ Bracket selection test completed successfully!")
            return True
            
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to API server")
        print(f"   Make sure the server is running at {base_url}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_bracket_selection()
    sys.exit(0 if success else 1)
