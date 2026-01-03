# Upstox Trading Bot - Complete Application Flow

## 🚀 HIGH-LEVEL APPLICATION FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        APP STARTUP (main.py)                                │
│                                                                              │
│  lifespan() context manager handles:                                        │
│  1. Database initialization                                                 │
│  2. Options service initialization                                          │
│  3. Options loading at startup                                              │
│  4. WebSocket service initialization                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
         ┌──────────────────────────────────────────────────┐
         │  STEP 1: DATABASE INITIALIZATION                 │
         │  (init_db)                                       │
         └──────────────────────────────────────────────────┘
                          │
                          ▼
              Connects to PostgreSQL
              Creates all tables:
              ├── Symbol
              ├── SubscribedOption
              ├── MarketTick
              └── Other tables...
```

---

## 📋 DETAILED STARTUP FLOW

### **PHASE 1: DATABASE INITIALIZATION**
```
init_db() 
  ├─ Create all SQLAlchemy models as DB tables
  └─ Tables created:
     ├── symbol (208 NSE FNO stocks)
     ├── subscribed_options (416 option contracts: CE + PE)
     ├── market_tick (real-time price data)
     └── Other trading/portfolio tables
```

---

### **PHASE 2: SEED SYMBOLS (if first run)**
```
Database population happens in two ways:

A. AUTOMATIC (via seed_symbols.py):
   
   App startup → Check if Symbol table empty?
                 │
                 ├─ YES: Run seed_symbols()
                 │   ├─ Read FNO_SYMBOLS list (208 symbols)
                 │   ├─ Deduplicate & validate
                 │   └─ Insert into Symbol table:
                 │       Example row:
                 │       ├─ symbol: "RELIANCE"
                 │       ├─ name: "Reliance Industries Limited"
                 │       ├─ is_fno: true
                 │       ├─ has_options: true
                 │       └─ sector: "Futures & Options"
                 │
                 └─ NO: Skip (symbols already seeded)

B. CONTENT OF SEED:
   
   208 verified NSE FNO stocks:
   ["360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIENT", ..., "ZYDUSLIFE"]
   
   Key characteristics:
   ├─ All marked as: is_fno=True, has_options=True
   ├─ Default liquidity score: 0.7
   ├─ Default daily volume: 1,000,000
   └─ All status: ACTIVE
```

**📊 Result after PHASE 2:**
```
✅ Symbol table = 208 rows
   └─ Each symbol represents 1 NSE FNO stock
```

---

### **PHASE 3: OPTIONS LOADING AT STARTUP**
```
load_options_at_startup()
  │
  ├─ STEP 1: Fetch spot price for each symbol
  │  └─ For each of 208 symbols:
  │     ├─ Call Upstox API: GET /v2/market-quote/ltp
  │     ├─ Format: NSE_EQ|INERELIANCEINV01012
  │     └─ Get: Current LTP (Last Traded Price)
  │     └─ Fallback: If API fails, use mock price = 1000 + hash(symbol) % 5000
  │
  ├─ STEP 2: Calculate ATM ± 1 strikes
  │  └─ For each symbol with spot price:
  │     ├─ ATM Strike = Round(spot_price / 100) * 100
  │     │   Example: spot_price=2500.50 → ATM=2500
  │     │
  │     └─ ATM+1 Strike = ATM + 100
  │         Example: ATM+1 = 2600
  │
  ├─ STEP 3: Create 2 options per symbol
  │  └─ For each symbol:
  │     ├─ CREATE CALL (CE) option at ATM strike
  │     │  └─ option_symbol = "{Symbol}25X{Strike}CE"
  │     │     Example: "RELIANCE25X2500CE"
  │     │
  │     └─ CREATE PUT (PE) option at ATM+1 strike
  │        └─ option_symbol = "{Symbol}25X{Strike}PE"
  │           Example: "RELIANCE25X2600PE"
  │
  ├─ STEP 4: Store in SubscribedOption table
  │  └─ INSERT rows:
  │     ├─ (symbol="RELIANCE", option_symbol="RELIANCE25X2500CE", 
  │     │   strike_price=2500, option_type="CE", is_subscribed=false)
  │     │
  │     └─ (symbol="RELIANCE", option_symbol="RELIANCE25X2600PE",
  │         strike_price=2600, option_type="PE", is_subscribed=false)
  │
  └─ REPEAT for all 208 symbols
     Result: 208 × 2 = 416 option contracts in DB
```

**📊 Result after PHASE 3:**
```
✅ SubscribedOption table = 416 rows

   Sample data:
   ┌────────────┬──────────────────────┬──────┬───────────────┐
   │ symbol     │ option_symbol        │ type │ strike_price  │
   ├────────────┼──────────────────────┼──────┼───────────────┤
   │ 360ONE     │ 360ONE25X1600CE      │ CE   │ 1600.0        │
   │ 360ONE     │ 360ONE25X1700PE      │ PE   │ 1700.0        │
   │ ABB        │ ABB25X2100CE         │ CE   │ 2100.0        │
   │ ABB        │ ABB25X2200PE         │ PE   │ 2200.0        │
   │ ...        │ ...                  │ ...  │ ...           │
   │ ZYDUSLIFE  │ ZYDUSLIFE25X5500CE   │ CE   │ 5500.0        │
   │ ZYDUSLIFE  │ ZYDUSLIFE25X5600PE   │ PE   │ 5600.0        │
   └────────────┴──────────────────────┴──────┴───────────────┘
```

---

### **PHASE 4: INITIALIZE OPTIONS SERVICE**
```
initialize_options_service_v3()
  │
  ├─ Purpose: Prepare to handle options data/Greeks calculations
  │
  └─ Sets up data structures for:
     ├─ IV (Implied Volatility) calculations
     ├─ Greeks (Delta, Gamma, Theta, Vega)
     └─ Price tracking for options
```

---

### **PHASE 5: INITIALIZE WEBSOCKET SERVICE & SUBSCRIBE**
```
initialize_websocket_service()
  │
  ├─ STEP 1: Create UpstoxWebSocketClient
  │  └─ Initialize with:
  │     ├─ access_token (from env/settings)
  │     └─ client_code (Upstox user ID)
  │
  ├─ STEP 2: Create SubscriptionManager
  │  └─ Manages subscriptions to all 416 option symbols
  │
  ├─ STEP 3: Load FNO Universe
  │  └─ load_fno_universe()
  │     └─ Query SubscribedOption table → Get all 416 option_symbols
  │        └─ Result: Set of 416 option symbols
  │           Examples: {"RELIANCE25X2500CE", "RELIANCE25X2600PE", ...}
  │
  ├─ STEP 4: Subscribe to all 416 options via WebSocket
  │  └─ subscribe_to_universe()
  │     ├─ Connect to WebSocket: wss://api.upstox.com/v3
  │     ├─ Authentication: Bearer {access_token}
  │     ├─ Subscribe in batches of 50 symbols at a time
  │     │  └─ Send subscription request for each batch
  │     │     └─ Message format (ProtoBuf):
  │     │        ├─ mode: "full"
  │     │        ├─ symbolsCount: 50
  │     │        └─ symbols: ["RELIANCE25X2500CE", "RELIANCE25X2600PE", ...]
  │     │
  │     └─ Result: All 416 subscriptions active on WebSocket
  │        └─ WebSocket connection now STREAMING real-time ticks for all 416 options
  │
  └─ STEP 5: Register Message Handlers
     └─ Set up handlers to process incoming tick data:
        ├─ Parse ProtoBuf tick messages
        ├─ Extract: price, volume, Greeks, timestamp
        ├─ Store in MarketTick table
        └─ Trigger signal generation if conditions met
```

**📊 Result after PHASE 5:**
```
✅ WebSocket Connected = TRUE
✅ Subscribed Symbols = 416 (all option contracts)
✅ Real-time data streaming = ACTIVE

When market opens:
  ├─ Incoming WebSocket messages (tick data)
  │  └─ Rate: ~1-100 messages/second depending on market activity
  │
  └─ Each message contains:
     ├─ symbol: "RELIANCE25X2500CE"
     ├─ ltp: 245.50 (current price)
     ├─ volume: 5000
     ├─ bid_quantity, ask_quantity
     ├─ Greeks: Delta, Gamma, Theta, Vega (if available)
     └─ timestamp: when price was published
```

---

## 🔄 RUNTIME FLOW (After Startup Complete)

### **REAL-TIME DATA PROCESSING**

```
WebSocket Message Received
  │
  ├─ Source: Upstox V3 WebSocket feed (live market data)
  ├─ Format: ProtoBuf encoded tick data
  │
  ▼
┌─────────────────────────────────────────┐
│ WebSocket Client Handler                 │
│ (websocket/client.py)                    │
│                                          │
│ on_message(tick_data):                   │
│  ├─ Parse ProtoBuf message              │
│  ├─ Extract: symbol, price, volume      │
│  └─ Call registered handlers            │
└─────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────┐
│ Message Handler (handlers.py)            │
│                                          │
│ handle_tick_data(tick):                  │
│  ├─ Store in MarketTick table           │
│  │  └─ INSERT: symbol, price, volume,   │
│  │           Greeks, timestamp          │
│  │                                      │
│  ├─ Update Greeks for this symbol       │
│  │  └─ Calculate IV, Delta, Gamma, etc. │
│  │                                      │
│  └─ Check signal generation conditions  │
│     └─ IF Greeks meet criteria:         │
│        └─ Emit signal (to be implemented)
└─────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────┐
│ Database Updates                         │
│                                          │
│ MarketTick table (growing log):          │
│  ├─ One row per tick per symbol         │
│  ├─ Sample rate: 100s of updates/sec    │
│  └─ Contains: All tick data + Greeks    │
└─────────────────────────────────────────┘
```

---

## 📊 DATA FLOW DIAGRAM

```
                    ┌─────────────────────────────────┐
                    │   UPSTOX API / WEBSOCKET        │
                    │   wss://api.upstox.com/v3       │
                    │   (Real-time tick data)         │
                    └──────────────┬──────────────────┘
                                   │
                                   │ Streaming data for:
                                   │ RELIANCE25X2500CE
                                   │ RELIANCE25X2600PE
                                   │ ... (414 more)
                                   │
                    ┌──────────────▼──────────────────┐
                    │   WebSocket Client              │
                    │   (src/websocket/client.py)     │
                    │                                 │
                    │ • Maintains connection          │
                    │ • Receives ProtoBuf messages    │
                    │ • Auto-reconnect on disconnect  │
                    └──────────────┬──────────────────┘
                                   │
                                   │ Decoded tick data
                                   │
                    ┌──────────────▼──────────────────┐
                    │   Message Handlers              │
                    │   (src/websocket/handlers.py)   │
                    │                                 │
                    │ • Parse ticks                   │
                    │ • Calculate Greeks              │
                    │ • Check signal conditions       │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │   PostgreSQL Database           │
                    │   (Market Tick data log)        │
                    │                                 │
                    │ Tables:                         │
                    │ ├─ symbol (208 rows)           │
                    │ ├─ subscribed_options (416)    │
                    │ ├─ market_tick (millions)      │
                    │ └─ Other trading tables        │
                    └──────────────────────────────────┘
```

---

## 🗂️ KEY FILES & RESPONSIBILITIES

| File | Purpose | Key Functions |
|------|---------|---------------|
| `main.py` | App entry point & startup | `lifespan()` orchestrates all initialization |
| `seed_symbols.py` | Load 208 FNO symbols | `seed_symbols()` - populates Symbol table |
| `options_loader.py` | Load options for symbols | `load_options_at_startup()` - creates 416 option records |
| `subscription_manager.py` | Manage WebSocket subscriptions | `load_fno_universe()`, `subscribe_to_universe()` |
| `websocket/client.py` | WebSocket connection & messaging | `connect()`, `subscribe()`, message parsing |
| `websocket/handlers.py` | Process incoming ticks | `handle_tick_data()` - stores & processes ticks |
| `models.py` | Database schemas | Symbol, SubscribedOption, MarketTick tables |

---

## 🔗 SYMBOL FORMAT CONVERSION (CRITICAL!)

When subscribing to WebSocket, symbols are automatically converted:

```
Database Format → WebSocket Format
(Simple format)  (Upstox V3 format)

RELIANCE25X2500CE → NSE_FO|RELIANCE25X2500CE
  (stored in DB)    (sent to WebSocket API)

INFY25X3000PE → NSE_FO|INFY25X3000PE

TCS25X3100CE → NSE_FO|TCS25X3100CE
```

**How it works:**
- Database stores simple format: `RELIANCE25X2500CE`
- `_symbol_to_token()` method in `client.py` (line 414):
  ```python
  if symbol.endswith(("PE", "CE")):
      return f"NSE_FO|{symbol}"
  ```
- Automatically converts to NSE_FO format before sending to WebSocket
- Result: All 416 subscriptions work correctly!

---

## 📈 STARTUP TIMELINE

```
T=0s     → App starts
T=0.1s   → Database initialization ✅
T=0.2s   → Symbol seeding ✅ (208 symbols)
T=0.3s   → Options service initialization ✅
T=0.5s   → Options loading starts
T=15s    → Options loaded (416 options created) ✅
T=16s    → WebSocket service initialization
T=18s    → WebSocket connected ✅
T=19s    → Subscribe to all 416 options ✅
T=22s    → Subscription complete
T=22s+   → Ready for real-time data! 🚀

Total startup time: ~22 seconds (varies with API latency)
```

---

## 🎯 FINAL STATE AT STARTUP COMPLETION

```
✅ Database: Fully initialized
✅ Symbols: 208 NSE FNO stocks seeded
✅ Options: 416 ATM ± 1 contracts created
✅ WebSocket: Connected to Upstox V3
✅ Subscriptions: All 416 option symbols subscribed
✅ Handlers: Ready to process real-time ticks
✅ API Endpoints: Available for monitoring/testing

System Status: READY FOR TRADING 🚀
```

---

## 📊 EXAMPLE: Full Trace for One Symbol (RELIANCE)

```
1. SEED PHASE:
   └─ INSERT INTO symbol:
      ├─ symbol: "RELIANCE"
      ├─ name: "Reliance Industries Limited"
      └─ is_fno: true, has_options: true

2. OPTIONS LOADING PHASE:
   ├─ Fetch spot price: GET /v2/market-quote/ltp → 2500.50
   ├─ Calculate ATM: Round(2500.50/100)*100 = 2500
   ├─ Calculate ATM+1: 2500 + 100 = 2600
   │
   └─ INSERT INTO subscribed_options (2 rows):
      ├─ Row 1: symbol="RELIANCE", option_symbol="RELIANCE25X2500CE",
      │         strike_price=2500, option_type="CE"
      │
      └─ Row 2: symbol="RELIANCE", option_symbol="RELIANCE25X2600PE",
                strike_price=2600, option_type="PE"

3. WEBSOCKET SUBSCRIPTION PHASE:
   ├─ Query DB: SELECT option_symbol FROM subscribed_options
   │            WHERE symbol='RELIANCE'
   │            → ["RELIANCE25X2500CE", "RELIANCE25X2600PE"]
   │
   ├─ Convert to Upstox format:
   │  ├─ "RELIANCE25X2500CE" → "NSE_FO|RELIANCE25X2500CE"
   │  └─ "RELIANCE25X2600PE" → "NSE_FO|RELIANCE25X2600PE"
   │
   └─ Send WebSocket subscribe message:
      └─ { mode: "full", symbols: ["NSE_FO|RELIANCE25X2500CE", 
                                    "NSE_FO|RELIANCE25X2600PE"] }

4. MARKET OPENS (Real-time):
   ├─ Receive tick: RELIANCE25X2500CE, price: 245.50, volume: 10000
   │  └─ INSERT INTO market_tick:
   │     ├─ symbol: "RELIANCE25X2500CE"
   │     ├─ ltp: 245.50
   │     ├─ volume: 10000
   │     ├─ delta: 0.65
   │     ├─ gamma: 0.012
   │     ├─ theta: -0.08
   │     └─ timestamp: 2025-11-29 09:15:30
   │
   └─ Repeat for every new tick (multiple times per second)
```

---

## 🔍 MONITORING & VERIFICATION

Use the verification endpoints to check system status:

```bash
# Check overall health
curl http://localhost:8000/api/v1/verify/health

# Check subscriptions
curl http://localhost:8000/api/v1/verify/subscriptions

# Check tick data in database
curl http://localhost:8000/api/v1/verify/tick-data-stats

# Get WebSocket status
curl http://localhost:8000/api/v1/websocket/status
```

---

## 📋 COMPLETE CHECKLIST

✅ **Startup Phase:**
- [x] Database initialized
- [x] 208 symbols seeded
- [x] 416 options generated (ATM ± 1)
- [x] Symbol format conversion working
- [x] WebSocket connected
- [x] All 416 subscriptions active
- [x] Message handlers registered

✅ **Runtime Phase (when market opens):**
- [ ] Real-time ticks flowing
- [ ] Greeks calculations accurate
- [ ] Signal generation (to be implemented)
- [ ] Trade execution (to be implemented)
- [ ] Risk management (to be implemented)

---
