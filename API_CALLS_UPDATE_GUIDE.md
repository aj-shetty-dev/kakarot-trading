# API Call Updates - Complete Codebase Review

## 🎯 Files Requiring API Call Updates

This document identifies all locations in the codebase that need to be updated to use the correct ISIN format for Upstox API calls.

---

## 1. options_loader.py - PRIMARY LOCATION ⚠️

**Current Issue**: Most likely using incorrect symbol format for LTP calls

```bash
# Search for API calls
grep -n "market-quote\|ltp\|LTP" backend/src/data/options_loader.py
```

**Expected Pattern** (BEFORE):
```python
# ❌ WRONG - Uses simple symbol or generic ISIN pattern
symbol_key = f"NSE_EQ|INE{symbol}01012"  # Generic pattern
# or
symbol_key = symbol  # Just symbol name
```

**Updated Pattern** (AFTER):
```python
# ✅ CORRECT - Uses actual ISIN from mapping
from .isin_mapping_hardcoded import get_instrument_key

symbol_key = get_instrument_key(symbol)  # Returns "NSE_EQ|INE009A01021"
```

---

## 2. options_service.py / options_service_v2.py / options_service_v3.py

**Files to Check**:
- `backend/src/data/options_service.py`
- `backend/src/data/options_service_v2.py`
- `backend/src/data/options_service_v3.py`

**Search Pattern**:
```bash
grep -n "market-quote\|exchange_token\|instrument_key" backend/src/data/options_service*.py
```

**Sections to Update**:
1. LTP fetch calls
2. Option chain queries
3. Greeks calculations
4. Any API requests using symbols

---

## 3. websocket/handlers.py - WebSocket Subscriptions ⚠️

**Current Issue**: WebSocket subscriptions likely use wrong symbol format

```bash
grep -n "subscribe\|symbol\|ISIN" backend/src/websocket/handlers.py
```

**Update Pattern**:
```python
# ❌ BEFORE
def subscribe_to_ltp(symbol: str, mode: str = "LTP"):
    instrument_key = f"NSE_EQ|INE{symbol}01012"
    
# ✅ AFTER
from backend.src.data.isin_mapping_hardcoded import get_instrument_key

def subscribe_to_ltp(symbol: str, mode: str = "LTP"):
    instrument_key = get_instrument_key(symbol)
```

---

## 4. Risk Management Modules

**Files to Check**:
- `backend/src/risk/` - Any risk calculations using symbols
- `backend/src/signals/` - Signal generation using symbols

```bash
find backend/src/risk backend/src/signals -name "*.py" -exec grep -l "market-quote\|LTP\|ltp" {} \;
```

---

## 5. Trading Module

**File**: `backend/src/trading/`

```bash
grep -rn "market-quote\|instrument\|symbol" backend/src/trading/
```

**Look for**:
- Order placement (symbol format)
- Position tracking (symbol format)
- P&L calculations (symbol format)

---

## 6. API Routes

**Files to Check**:
- `backend/src/api/routes/` - All route handlers

```bash
find backend/src/api/routes -name "*.py" -exec grep -l "market-quote\|ltp" {} \;
```

**Sections**:
1. LTP endpoints
2. Option data endpoints
3. Symbol search endpoints

---

## 🔍 Complete Search Commands

### Find All Market Quote Calls
```bash
cd /Users/shetta20/Projects/upstox
grep -rn "market-quote" backend/src/
```

### Find All LTP References
```bash
grep -rn "LTP\|ltp" backend/src/ | grep -v "__pycache__"
```

### Find All Symbol/Instrument References
```bash
grep -rn "f\"NSE_EQ" backend/src/ | grep -v "__pycache__"
grep -rn "instrument_key\|exchange_token" backend/src/ | grep -v "__pycache__"
```

### Find All API Calls
```bash
grep -rn "api.upstox.com\|requests.get\|requests.post" backend/src/ | grep -v "__pycache__"
```

---

## 📋 Standardized Update Template

For each file found, apply this template:

### Step 1: Add Import
```python
# At the top of the file
from ..data.isin_mapping_hardcoded import (
    get_instrument_key, 
    ISIN_MAPPING, 
    validate_symbol
)
```

### Step 2: Update Symbol Usage
```python
# ❌ BEFORE
def fetch_ltp(symbol: str) -> float:
    instrument_key = f"NSE_EQ|INE{symbol}01012"
    response = requests.get(
        f"https://api.upstox.com/v2/market-quote/ltp?mode=LTP&symbol={instrument_key}"
    )

# ✅ AFTER
def fetch_ltp(symbol: str) -> float:
    instrument_key = get_instrument_key(symbol)
    if not instrument_key:
        raise ValueError(f"Invalid symbol: {symbol}")
    response = requests.get(
        f"https://api.upstox.com/v2/market-quote/ltp?mode=LTP&symbol={instrument_key}"
    )
```

### Step 3: Add Validation
```python
# Before using any symbol
if not validate_symbol(symbol):
    raise ValueError(f"Symbol {symbol} not in FNO list")
```

---

## 🎯 Priority Order for Updates

### HIGH PRIORITY (API-Critical)
1. `options_loader.py` - Main LTP fetcher
2. `websocket/handlers.py` - Live data subscriptions
3. `options_service_v3.py` - Latest options service

### MEDIUM PRIORITY (Data-Related)
4. `api/routes/` - All API endpoints
5. `signals/` - Signal generation
6. `trading/` - Trading logic

### LOW PRIORITY (Utility)
7. `risk/` - Risk calculations
8. Test files - Test data

---

## ✅ Checklist for Complete Update

- [ ] `options_loader.py` - Updated
- [ ] `options_service.py` - Updated
- [ ] `options_service_v2.py` - Updated
- [ ] `options_service_v3.py` - Updated
- [ ] `websocket/handlers.py` - Updated
- [ ] `api/routes/*.py` - All routes updated
- [ ] `signals/*.py` - All signal modules updated
- [ ] `trading/*.py` - All trading modules updated
- [ ] `risk/*.py` - All risk modules updated
- [ ] Test files - Updated with ISIN format
- [ ] Database migration - Run
- [ ] Symbols seeded - With ISINs
- [ ] Live test - All 208 symbols working

---

## 🧪 Validation After Updates

### Test Individual Module
```python
from backend.src.data.options_loader import fetch_ltp

ltp = fetch_ltp("INFY")
print(f"INFY LTP: {ltp}")
```

### Test All 208 Symbols
```bash
python test_all_symbols_with_isin.py
```

### Check Database
```python
from backend.src.data.database import SessionLocal
from backend.src.data.models import Symbol

db = SessionLocal()
symbols = db.query(Symbol).all()
for sym in symbols[:5]:
    print(f"{sym.symbol}: ISIN={sym.isin}, Token={sym.instrument_token}")
```

---

## 💡 Key Points

1. **Always Use ISIN**: Never use simple symbol names for API calls
2. **Use Helper Function**: Always call `get_instrument_key()` instead of hardcoding format
3. **Validate Symbols**: Check with `validate_symbol()` before API calls
4. **Import Once**: Import at module level, not in functions
5. **Error Handling**: Handle invalid symbols gracefully

---

## 🚀 Example Implementation

### Complete Working Example
```python
"""
Complete example of updating an API call to use ISIN format
"""
from typing import Optional
from ..data.isin_mapping_hardcoded import (
    get_instrument_key, 
    validate_symbol
)
import requests
from datetime import datetime

class LTPFetcher:
    """Fetches Last Traded Price using correct ISIN format"""
    
    def __init__(self, base_url: str = "https://api.upstox.com"):
        self.base_url = base_url
    
    def fetch_ltp(self, symbol: str, auth_token: str) -> Optional[dict]:
        """
        Fetch LTP for a symbol using correct ISIN format
        
        Args:
            symbol: Symbol name (e.g., "INFY")
            auth_token: Upstox authentication token
        
        Returns:
            dict with LTP data or None if error
        """
        # Validate symbol
        if not validate_symbol(symbol):
            raise ValueError(f"Invalid FNO symbol: {symbol}")
        
        # Get correct instrument key (NSE_EQ|ISIN)
        instrument_key = get_instrument_key(symbol)
        
        try:
            # API call with correct format
            response = requests.get(
                f"{self.base_url}/v2/market-quote/ltp",
                params={"mode": "LTP", "symbol": instrument_key},
                headers={"Authorization": f"Bearer {auth_token}"},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return {
                        "symbol": symbol,
                        "instrument_key": instrument_key,
                        "ltp": data["data"][instrument_key]["last_price"],
                        "timestamp": datetime.now()
                    }
            
            return None
            
        except Exception as e:
            print(f"Error fetching LTP for {symbol}: {e}")
            return None

# Usage
fetcher = LTPFetcher()
result = fetcher.fetch_ltp("INFY", "your_auth_token")
if result:
    print(f"✅ {result['symbol']}: ₹{result['ltp']}")
```

---

**Last Updated**: Auto-generated by ISIN Integration Tool
**Status**: Ready for Implementation ✅
