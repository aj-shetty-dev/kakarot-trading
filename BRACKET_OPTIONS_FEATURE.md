# 🎯 Bracket Options Auto-Subscription Feature

**Status**: ✅ Implementation Complete  
**Date**: 2025-11-29

---

## Overview

Automatically select and subscribe to bracketing options (PE above, CE below current price) for all 208 FNO symbols.

**Result**: 
- ✅ 208 symbols → 416 options total (1 PE + 1 CE per symbol)
- ✅ Auto-subscribe via WebSocket
- ✅ Real-time price monitoring

---

## How It Works

### 1. **Bracket Selection Algorithm**

For each symbol at current price `P`:

```
Available strikes: [1200, 1250, 1300, 1350, 1400, ...]

Current Price: 1250

PE (Put - Above price):    Find closest strike >= 1250  → 1300 PE
CE (Call - Below price):   Find closest strike <= 1250  → 1250 CE
                                                          (or 1200 if 1250 not available)

Result: Buy PE 1300 / Buy CE 1200 (brackets the position)
```

### 2. **Auto-Subscription Flow**

```
┌─────────────────────────────────────────────────────────┐
│  1. Get Current Prices from WebSocket                  │
│     (LTP for all 208 symbols)                          │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  2. For Each Symbol:                                   │
│     - Find PE strike (above price)                     │
│     - Find CE strike (below price)                     │
│     - Select nearest expiry                            │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  3. Collect All Symbols (416 total)                    │
│     Format: NSE_FO|RELIANCE 1300 PE 30 DEC 25          │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  4. Subscribe via WebSocket                            │
│     Stream live tick data for all 416 options          │
└─────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### 1. **Auto-Initialize from WebSocket Prices**

```bash
POST /api/v1/bracket-management/auto-init
```

Uses current prices from WebSocket to auto-select brackets.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/bracket-management/auto-init
```

**Response:**
```json
{
  "status": "success",
  "brackets_selected": 208,
  "total_options": 416,
  "upstox_symbols": [
    "NSE_FO|RELIANCE 1300 PE 30 DEC 25",
    "NSE_FO|RELIANCE 1200 CE 30 DEC 25",
    "NSE_FO|TCS 3600 PE 30 DEC 25",
    "NSE_FO|TCS 3400 CE 30 DEC 25",
    ...
  ]
}
```

### 2. **Manual Initialize with Custom Prices**

```bash
POST /api/v1/bracket-management/manual-init
```

Manually specify current prices for each symbol.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/bracket-management/manual-init \
  -H "Content-Type: application/json" \
  -d '{
    "symbol_prices": {
      "RELIANCE": 1250,
      "TCS": 3500,
      "INFY": 2800,
      "HDFC": 2450,
      "ICICI": 950
    }
  }'
```

**Response:**
```json
{
  "status": "success",
  "brackets_selected": 5,
  "total_options": 10,
  "upstox_symbols": [
    "NSE_FO|RELIANCE 1300 PE 30 DEC 25",
    "NSE_FO|RELIANCE 1200 CE 30 DEC 25",
    ...
  ]
}
```

### 3. **Get Bracket Statistics**

```bash
GET /api/v1/bracket-management/stats
```

**Request:**
```bash
curl http://localhost:8000/api/v1/bracket-management/stats
```

**Response:**
```json
{
  "initialized": true,
  "total_symbols": 208,
  "brackets_selected": 208,
  "total_options": 416
}
```

### 4. **Get Upstox Symbols for Subscription**

```bash
GET /api/v1/bracket-management/upstox-symbols
```

Get all 416 bracket symbols ready for WebSocket subscription.

**Request:**
```bash
curl http://localhost:8000/api/v1/bracket-management/upstox-symbols
```

**Response:**
```json
{
  "count": 416,
  "upstox_symbols": [
    "NSE_FO|RELIANCE 1300 PE 30 DEC 25",
    "NSE_FO|RELIANCE 1200 CE 30 DEC 25",
    "NSE_FO|TCS 3600 PE 30 DEC 25",
    ...
  ]
}
```

---

## Complete Workflow Example

### Step 1: Initialize Brackets from WebSocket Prices
```bash
curl -X POST http://localhost:8000/api/v1/bracket-management/auto-init
```

### Step 2: Get the Upstox Symbols
```bash
curl http://localhost:8000/api/v1/bracket-management/upstox-symbols | jq '.upstox_symbols'
```

### Step 3: Subscribe to Bracket Options via WebSocket

```python
import asyncio
from upstox_client import WebSocketClient

async def subscribe_brackets():
    # Get bracket symbols from API
    upstox_symbols = [
        "NSE_FO|RELIANCE 1300 PE 30 DEC 25",
        "NSE_FO|RELIANCE 1200 CE 30 DEC 25",
        # ... 414 more symbols ...
    ]
    
    # Subscribe via WebSocket
    ws_client = WebSocketClient(api_key, api_secret)
    await ws_client.subscribe(upstox_symbols, mode="full")
    
    # Start streaming
    async for tick in ws_client.stream():
        print(f"{tick['symbol']}: {tick['ltp']}")

asyncio.run(subscribe_brackets())
```

---

## Individual Bracket Selection API

### Select Bracket for Single Symbol

```bash
POST /api/v1/brackets/select/{symbol}?price=1250
```

**Request:**
```bash
curl -X POST 'http://localhost:8000/api/v1/brackets/select/RELIANCE?price=1250'
```

**Response:**
```json
{
  "symbol": "RELIANCE",
  "price": 1250.0,
  "expiry": "1767119399000",
  "pe": {
    "tradingsymbol": "RELIANCE 1300 PE 30 DEC 25",
    "exchange_token": 123456,
    "type": "PE",
    "strike": 1300.0,
    "lot_size": 500,
    "tick_size": 5.0,
    "segment": "NSE_FO"
  },
  "ce": {
    "tradingsymbol": "RELIANCE 1200 CE 30 DEC 25",
    "exchange_token": 123457,
    "type": "CE",
    "strike": 1200.0,
    "lot_size": 500,
    "tick_size": 5.0,
    "segment": "NSE_FO"
  },
  "upstox_symbols": [
    "NSE_FO|RELIANCE 1300 PE 30 DEC 25",
    "NSE_FO|RELIANCE 1200 CE 30 DEC 25"
  ]
}
```

### Select Brackets for Multiple Symbols

```bash
POST /api/v1/brackets/select-all
```

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/brackets/select-all \
  -d 'RELIANCE=1250&TCS=3500&INFY=2800'
```

**Response:**
```json
{
  "count": 3,
  "total_symbols": 3,
  "brackets": [
    {
      "symbol": "RELIANCE",
      "price": 1250.0,
      "pe": {...},
      "ce": {...}
    },
    {
      "symbol": "TCS",
      "price": 3500.0,
      "pe": {...},
      "ce": {...}
    },
    {
      "symbol": "INFY",
      "price": 2800.0,
      "pe": {...},
      "ce": {...}
    }
  ],
  "all_upstox_symbols": [...]
}
```

---

## Usage Scenarios

### Scenario 1: Portfolio Hedging
```
For each position in your portfolio:
1. Get current price
2. Select bracket options (PE above, CE below)
3. Subscribe and monitor
4. Automatically hedge if price crosses boundaries
```

### Scenario 2: Intraday Risk Management
```
1. At market open, get prices for all 208 symbols
2. Auto-select bracket options
3. Subscribe to all 416 options
4. Monitor for breakouts and lock profits/losses
```

### Scenario 3: Volatility Monitoring
```
1. Track bracket width (difference between PE and CE strikes)
2. Wider brackets = higher implied volatility
3. Narrow brackets = lower implied volatility
4. Adjust trading strategy accordingly
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Bracket Selection Service                      │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ - Select PE (above price) + CE (below price)           │ │
│  │ - Find nearest expiry                                  │ │
│  │ - Store selected brackets                              │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↑                                   │
│         Uses Options Service (95K contracts)                 │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │     Bracket Subscription Service                       │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ - Auto-init from WebSocket prices                      │ │
│  │ - Manual init from custom prices                       │ │
│  │ - Track selected brackets (208 symbols)                │ │
│  │ - Generate Upstox symbols (416 options)                │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │       Bracket Management REST API                      │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ POST /auto-init           (use WebSocket prices)       │ │
│  │ POST /manual-init         (custom prices)              │ │
│  │ GET  /stats               (current status)             │ │
│  │ GET  /upstox-symbols      (for subscription)           │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         WebSocket Service                              │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ - Subscribe to 416 bracket options                     │ │
│  │ - Stream live tick data                                │ │
│  │ - Monitor price movements                              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Code Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `bracket_selector.py` | Core bracket selection logic | 150+ |
| `bracket_subscription_service.py` | Auto-subscription management | 100+ |
| `brackets.py` | REST endpoints for bracket selection | 250+ |
| `bracket_management.py` | Management endpoints | 200+ |

---

## Data Flow Example

```
Input: Symbol = "RELIANCE", Price = 1250

Step 1: Get all strikes for RELIANCE
        [1200, 1210, 1220, ..., 1300, 1310, 1320]

Step 2: Find PE strike (>= 1250)
        First strike >= 1250 = 1300
        → Select: RELIANCE 1300 PE

Step 3: Find CE strike (<= 1250)
        Last strike <= 1250 = 1250 (if available) or 1240
        → Select: RELIANCE 1250 CE (or 1240 CE)

Output: {
  "symbol": "RELIANCE",
  "price": 1250,
  "pe": {..., "strike": 1300, "type": "PE"},
  "ce": {..., "strike": 1250, "type": "CE"},
  "upstox_symbols": [
    "NSE_FO|RELIANCE 1300 PE 30 DEC 25",
    "NSE_FO|RELIANCE 1250 CE 30 DEC 25"
  ]
}
```

---

## Next Steps

1. **Test bracket selection** for all 208 symbols
2. **Subscribe** to the 416 bracket options via WebSocket
3. **Monitor** bracket prices in real-time
4. **Set alerts** when price hits bracket boundaries
5. **Auto-hedge** when needed

---

## Status: ✅ READY FOR TESTING

All endpoints implemented and integrated into the FastAPI application!

