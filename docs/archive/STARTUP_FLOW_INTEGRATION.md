# Application Startup Flow - ISIN Integration

## Overview

This document explains how the application will use ISIN mappings at startup to correctly fetch LTP and options data from Upstox API.

## The Problem

Upstox API requires **instrument keys** in `NSE_EQ|ISIN` format, not simple symbol names:

```
❌ WRONG: "RELIANCE"
✅ RIGHT: "NSE_EQ|INE002A01018"
```

Without this mapping, all API calls return empty data or errors.

## Solution Architecture

### 1. ISIN Mapping (Already Complete ✅)

**File**: `backend/src/data/isin_mapping_hardcoded.py`

Contains:
- `ISIN_MAPPING`: Dict of 208 symbols → ISINs
- `get_instrument_key(symbol)`: Returns `NSE_EQ|{ISIN}` format
- `get_all_symbols()`: Returns list of all 208 symbols
- `validate_symbol(symbol)`: Checks if symbol is in FNO list

```python
from isin_mapping_hardcoded import get_instrument_key

# Usage
instrument_key = get_instrument_key("RELIANCE")
# Returns: "NSE_EQ|INE002A01018"
```

### 2. Startup Flow (Proposed)

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION STARTUP                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Load ISIN Mapping                                        │
│   - Import isin_mapping_hardcoded.py                            │
│   - 208 symbols → ISINs loaded in memory                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Fetch LTP for All Symbols                               │
│   - For each symbol in ISIN_MAPPING:                            │
│     - Get instrument_key = NSE_EQ|{ISIN}                        │
│     - Call Upstox v3 LTP API                                    │
│     - Store LTP in memory/database                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Fetch Options Chains                                     │
│   - For each symbol with valid LTP:                             │
│     - Calculate ATM strike from LTP                             │
│     - Fetch options chain using symbol instrument key           │
│     - Filter to ATM ± 1 strikes                                 │
│     - Store options in database                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Subscribe to WebSocket                                   │
│   - Build subscription list using instrument keys               │
│   - Subscribe to LTP updates for:                               │
│     - Underlying symbols (208 stocks)                           │
│     - Selected options (ATM ± 1 CE/PE)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Ready for Trading                                        │
│   - All LTP data loaded                                         │
│   - Options chains loaded                                       │
│   - WebSocket streaming live data                               │
│   - Signal detection active                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Key Code Changes Required

#### A. options_loader.py - fetch_spot_price()

**Before**:
```python
async def fetch_spot_price(self, symbol: str) -> Optional[float]:
    # ❌ WRONG - Generic ISIN pattern
    instrument_key = f"NSE_EQ|INE{symbol}01012"
    ...
```

**After**:
```python
from .isin_mapping_hardcoded import get_instrument_key, validate_symbol

async def fetch_spot_price(self, symbol: str) -> Optional[float]:
    # ✅ CORRECT - Use actual ISIN from mapping
    if not validate_symbol(symbol):
        logger.warning(f"Invalid FNO symbol: {symbol}")
        return None
    
    instrument_key = get_instrument_key(symbol)
    ...
```

#### B. WebSocket Handlers

**Before**:
```python
def subscribe_to_symbol(symbol: str):
    # ❌ WRONG - Using symbol name directly
    self.ws.send(json.dumps({
        "guid": "someguid",
        "method": "sub",
        "data": {"mode": "ltpc", "instrumentKeys": [f"NSE_EQ|{symbol}"]}
    }))
```

**After**:
```python
from backend.src.data.isin_mapping_hardcoded import get_instrument_key

def subscribe_to_symbol(symbol: str):
    # ✅ CORRECT - Use instrument key with ISIN
    instrument_key = get_instrument_key(symbol)
    self.ws.send(json.dumps({
        "guid": "someguid",
        "method": "sub",
        "data": {"mode": "ltpc", "instrumentKeys": [instrument_key]}
    }))
```

### 4. Validation Flow

Before going live, run the validation script:

```bash
# 1. Update token in backend/.env
UPSTOX_ACCESS_TOKEN=your_fresh_token_here

# 2. Run validation
python3 validate_all_isins.py

# Expected output:
# ✅ 208/208 symbols validated
# All ISINs correct and returning LTP data
```

### 5. Files Modified/Created

| File | Status | Description |
|------|--------|-------------|
| `backend/src/data/isin_mapping_hardcoded.py` | ✅ Created | 208 symbol→ISIN mappings |
| `backend/src/data/models.py` | ✅ Updated | Added `isin`, `instrument_token` fields |
| `backend/src/data/seed_symbols.py` | ✅ Updated | Uses ISIN mapping for seeding |
| `validate_all_isins.py` | ✅ Created | Validates all 208 ISINs against API |
| `backend/src/data/options_loader.py` | ⏳ Pending | Needs ISIN integration |
| `backend/src/websocket/handlers.py` | ⏳ Pending | Needs ISIN integration |

### 6. API Endpoints Used

| Purpose | Endpoint | Format |
|---------|----------|--------|
| LTP (single) | `GET /v3/market-quote/ltp?instrument_key={key}` | `NSE_EQ|{ISIN}` |
| LTP (batch) | `GET /v3/market-quote/ltp?instrument_key={key1},{key2},...` | Comma-separated |
| Options Chain | `GET /v2/option/chain?instrument_key={key}&expiry_date={date}` | `NSE_EQ|{ISIN}` |
| WebSocket | Subscribe with `instrumentKeys` array | `["NSE_EQ|{ISIN1}", ...]` |

### 7. Error Handling

```python
def get_ltp_for_symbol(symbol: str) -> Optional[float]:
    """
    Get LTP with proper error handling
    """
    # Validate symbol first
    if not validate_symbol(symbol):
        logger.error(f"Symbol {symbol} not in FNO list")
        return None
    
    # Get instrument key
    instrument_key = get_instrument_key(symbol)
    if not instrument_key:
        logger.error(f"No ISIN mapping for {symbol}")
        return None
    
    # Make API call
    try:
        response = fetch_ltp(instrument_key)
        return response.get('last_price')
    except HTTPError as e:
        if e.code == 403:
            logger.error("Token expired or invalid")
        elif e.code == 429:
            logger.warning("Rate limited - waiting...")
            time.sleep(1)
        return None
```

### 8. Testing Checklist

- [ ] Fresh Upstox access token obtained
- [ ] Token added to `backend/.env`
- [ ] Run `validate_all_isins.py` - expect 208/208 success
- [ ] Update `options_loader.py` with ISIN integration
- [ ] Test single symbol LTP fetch
- [ ] Test batch LTP fetch (5 symbols)
- [ ] Test options chain fetch
- [ ] Test WebSocket subscription
- [ ] Full integration test with all 208 symbols

### 9. Next Steps

1. **Get fresh Upstox token** with market data permissions
2. **Run validation script** to confirm all 208 ISINs work
3. **Update options_loader.py** to use ISIN mapping
4. **Update WebSocket handlers** to use ISIN mapping
5. **Test full startup flow** with real API calls
6. **Deploy and monitor** for any issues

---

## Quick Reference

### Get Instrument Key for Any Symbol
```python
from backend.src.data.isin_mapping_hardcoded import get_instrument_key

key = get_instrument_key("RELIANCE")  # "NSE_EQ|INE002A01018"
key = get_instrument_key("INFY")      # "NSE_EQ|INE009A01021"
key = get_instrument_key("TCS")       # "NSE_EQ|INE467B01029"
```

### Validate Symbol is in FNO List
```python
from backend.src.data.isin_mapping_hardcoded import validate_symbol

validate_symbol("RELIANCE")  # True
validate_symbol("INVALID")   # False
```

### Get All 208 Symbols
```python
from backend.src.data.isin_mapping_hardcoded import get_all_symbols

symbols = get_all_symbols()  # ['360ONE', 'ABB', 'APLAPOLLO', ...]
```
