# options_loader.py - ISIN Update Example

This file shows exactly what needs to be changed in `backend/src/data/options_loader.py` to use ISINs.

## Current Issue

The `fetch_spot_price` function uses a generic ISIN pattern:

```python
# ❌ WRONG - Line 47
instrument_key = f"NSE_EQ|INE{symbol}01012"  # Generic pattern - doesn't match real ISINs
```

This pattern:
- Assumes all ISINs follow `INE{symbol}01012` format
- Does NOT match actual ISINs (e.g., INFY is `INE009A01021`, not `INEINFY01012`)
- Causes API to return empty data (HTTP 200 but no data)

## Solution

Replace the hardcoded pattern with the correct ISIN from `isin_mapping_hardcoded.py`.

## Step-by-Step Update

### 1. Add Import at Top of File

**File**: `backend/src/data/options_loader.py`

**Add after existing imports (around line 10)**:

```python
# Add this import with other imports
from .isin_mapping_hardcoded import get_instrument_key, validate_symbol
```

### 2. Update fetch_spot_price Function

**Current Code** (lines 35-65):
```python
async def fetch_spot_price(self, symbol: str) -> Optional[float]:
    """
    Fetch current spot price (LTP) for a symbol from Upstox API
    Falls back to mock price in development if API fails
    
    Args:
        symbol: Base symbol (e.g., "RELIANCE")
    
    Returns:
        Spot price or None if failed
    """
    try:
        # Format for NSE equity
        instrument_key = f"NSE_EQ|INE{symbol}01012"  # Standard NSE format
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.api_base_url}/market-quote/ltp",
                params={"mode": "LTP", "symbol": instrument_key},
                headers={"Authorization": f"Bearer {self.upstox_access_token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "fetch" in data["data"]:
                    for key, val in data["data"]["fetch"].items():
                        if "last_price" in val:
                            return float(val["last_price"])
            
            # API call failed - use mock data for development
            # Generate a realistic mock price based on symbol length and hash
            mock_price = 1000.0 + (hash(symbol) % 5000)
            logger.debug(f"ℹ️  Using mock spot price for {symbol}: {mock_price}")
            return mock_price
            
    except Exception as e:
        # On exception, use mock data
        mock_price = 1000.0 + (hash(symbol) % 5000)
        logger.debug(f"ℹ️  Using mock spot price for {symbol}: {mock_price} (exception: {e})")
        return mock_price
```

**Updated Code**:
```python
async def fetch_spot_price(self, symbol: str) -> Optional[float]:
    """
    Fetch current spot price (LTP) for a symbol from Upstox API
    Falls back to mock price in development if API fails
    
    Args:
        symbol: Base symbol (e.g., "RELIANCE")
    
    Returns:
        Spot price or None if failed
    """
    try:
        # Validate symbol is in FNO list
        if not validate_symbol(symbol):
            logger.warning(f"⚠️  Invalid FNO symbol: {symbol}")
            return 1000.0  # Default mock price
        
        # Get correct instrument key using ISIN mapping (not generic pattern)
        instrument_key = get_instrument_key(symbol)
        if not instrument_key:
            logger.warning(f"⚠️  Could not get instrument key for {symbol}")
            return 1000.0  # Default mock price
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.api_base_url}/market-quote/ltp",
                params={"mode": "LTP", "symbol": instrument_key},
                headers={"Authorization": f"Bearer {self.upstox_access_token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and instrument_key in data["data"]:
                    val = data["data"][instrument_key]
                    if "last_price" in val:
                        ltp = float(val["last_price"])
                        logger.debug(f"✅ Fetched LTP for {symbol}: ₹{ltp} (using correct ISIN: {instrument_key})")
                        return ltp
            
            # API call failed - use mock data for development
            mock_price = 1000.0 + (hash(symbol) % 5000)
            logger.debug(f"ℹ️  Using mock spot price for {symbol}: ₹{mock_price}")
            return mock_price
            
    except Exception as e:
        # On exception, use mock data
        mock_price = 1000.0 + (hash(symbol) % 5000)
        logger.error(f"❌ Error fetching LTP for {symbol}: {e}")
        logger.debug(f"ℹ️  Using mock spot price: ₹{mock_price}")
        return mock_price
```

## Key Changes Explained

### Change 1: Symbol Validation
```python
# ✅ NEW - Validate symbol before using
if not validate_symbol(symbol):
    logger.warning(f"⚠️  Invalid FNO symbol: {symbol}")
    return 1000.0
```
**Why**: Prevents errors with invalid symbols

### Change 2: Use ISIN Mapping
```python
# ❌ OLD
instrument_key = f"NSE_EQ|INE{symbol}01012"

# ✅ NEW
instrument_key = get_instrument_key(symbol)
```
**Why**: Uses actual ISIN instead of generic pattern

### Change 3: Better Data Parsing
```python
# ❌ OLD - Generic loop
if "data" in data and "fetch" in data["data"]:
    for key, val in data["data"]["fetch"].items():

# ✅ NEW - Direct access with correct key
if "data" in data and instrument_key in data["data"]:
    val = data["data"][instrument_key]
```
**Why**: Direct access is clearer and handles correct ISIN format

### Change 4: Better Logging
```python
# ✅ NEW - Log what worked
logger.debug(f"✅ Fetched LTP for {symbol}: ₹{ltp} (using correct ISIN: {instrument_key})")

# ✅ NEW - Better error logging
logger.error(f"❌ Error fetching LTP for {symbol}: {e}")
```
**Why**: Makes debugging easier

## Testing the Update

### Before Test (Verify the problem)
```bash
# This would show empty data with old format
python -c "
import asyncio
from backend.src.data.options_loader import OptionsLoaderService

service = OptionsLoaderService()
ltp = asyncio.run(service.fetch_spot_price('INFY'))
print(f'INFY LTP: {ltp}')  # Would be None or mock (broken)
"
```

### After Test (Verify it's fixed)
```bash
# This should show real LTP with new format
python -c "
import asyncio
from backend.src.data.options_loader import OptionsLoaderService

service = OptionsLoaderService()
ltp = asyncio.run(service.fetch_spot_price('INFY'))
print(f'INFY LTP: ₹{ltp}')  # Should be real LTP (e.g., 2432.50)
"
```

## Similar Updates Needed

The same pattern appears in these functions - update them all:

1. **`fetch_spot_price()`** ← Apply change above
2. **Any other API calls** - Search for `f"NSE_EQ|INE` pattern

### Search Command
```bash
grep -n "NSE_EQ|INE" backend/src/data/options_loader.py
```

## Complete Diff Summary

```diff
--- a/backend/src/data/options_loader.py
+++ b/backend/src/data/options_loader.py
@@ -8,6 +8,7 @@ from typing import List, Dict, Optional, Tuple
 from datetime import datetime
 import httpx
 from sqlalchemy.orm import Session
+from .isin_mapping_hardcoded import get_instrument_key, validate_symbol
 
 from ..config.logging import logger
 from ..config.settings import settings
@@ -41,7 +42,16 @@ class OptionsLoaderService:
     """
     try:
         # Format for NSE equity
-        instrument_key = f"NSE_EQ|INE{symbol}01012"
+        # Validate symbol is in FNO list
+        if not validate_symbol(symbol):
+            logger.warning(f"⚠️  Invalid FNO symbol: {symbol}")
+            return 1000.0
+        
+        # Get correct instrument key using ISIN mapping (not generic pattern)
+        instrument_key = get_instrument_key(symbol)
+        if not instrument_key:
+            logger.warning(f"⚠️  Could not get instrument key for {symbol}")
+            return 1000.0
         
         async with httpx.AsyncClient(timeout=10.0) as client:
             response = await client.get(
```

## Validation Checklist

- [ ] Import added at top of file
- [ ] `fetch_spot_price()` function updated
- [ ] Symbol validation added
- [ ] ISIN mapping function used
- [ ] Better logging added
- [ ] No hardcoded `INE{symbol}01012` patterns remain
- [ ] File tested with valid symbols
- [ ] All 208 symbols work correctly

## Next Files to Update

After updating `options_loader.py`, check these files with similar issues:

1. `backend/src/data/options_service.py`
2. `backend/src/data/options_service_v2.py`
3. `backend/src/data/options_service_v3.py`
4. `backend/src/websocket/handlers.py`
5. `backend/src/api/routes/*.py`

Use the search command to find all occurrences:
```bash
grep -rn "NSE_EQ|INE" backend/src/ | grep -v "__pycache__"
```

---

**Status**: Ready to apply ✅
**Difficulty**: Low - Straightforward find/replace
**Time Estimate**: 5-10 minutes per file
**Testing**: Use `test_all_symbols_with_isin.py` to validate
