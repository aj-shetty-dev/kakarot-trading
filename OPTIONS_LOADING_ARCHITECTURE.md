# Options Loading & Subscription Flow - Architecture

## Overview

At app startup, we load ~416 options (ATM ± 1 strike for 208 symbols) and store them for WebSocket subscription.

## Architecture

```
App Startup
    ↓
1. Load 208 base symbols from database (RELIANCE, HDFC, TCS, etc.)
    ↓
2. For each symbol:
   a. Fetch spot price (ATM) via Upstox API
   b. Calculate ATM ± 1 strike levels
   c. Create 2 options:
      - ATM Call (CE)
      - ATM+1 Put (PE)
   d. Store in SubscribedOption table
    ↓
3. Load ~416 SubscribedOption records from database
    ↓
4. Subscribe to WebSocket for each option
    ↓
5. Update WebSocket status as subscriptions succeed
    ↓
6. Monitor real-time pricing via WebSocket
```

## Data Models

### Symbol Table (Already Exists)
- 208 records with `has_options=True`
- Example: RELIANCE, HDFC, TCS, INFY, MARUTI, etc.

### SubscribedOption Table (NEW)
```python
- id (UUID)
- symbol: "RELIANCE"                          # Base symbol
- option_symbol: "RELIANCE25X2500CE"          # Full trading symbol
- option_type: "CE" or "PE"                   # Call or Put
- strike_price: 2500.0                        # Strike price
- spot_price_at_subscription: 2468.50         # Spot at time of load
- is_subscribed: False → True (after WS)      # Subscription status
- websocket_token: "xyz123"                   # Token from Upstox
- last_price: 15.50                           # Updated by WebSocket
- created_at, updated_at                      # Timestamps
```

## Services

### OptionsLoaderService (`options_loader.py`)
- **Method**: `load_and_store_options(db)`
  - Called at app startup
  - For each symbol: fetch spot → calculate strikes → store in DB
  - Returns: count of options loaded (~416)
  
- **Methods**:
  - `fetch_spot_price(symbol)` → Calls Upstox API
  - `fetch_options_chain(symbol)` → Calls Upstox API (future)
  - `find_atm_plus_one_strikes(spot, available_strikes)` → Calculates which strikes to use

### WebSocket Manager (Existing)
- After options are stored, WebSocket manager subscribes to each option
- Updates `SubscribedOption.is_subscribed = True` when successful
- Updates `SubscribedOption.websocket_token` with Upstox token
- Receives real-time pricing updates

## Flow Timeline

```
9:18 AM (or App Startup during dev)
    ↓
OptionsLoaderService.load_and_store_options()
    └─ ~5-10 seconds: Fetch spot prices for 208 symbols
    └─ ~1-2 seconds: Calculate strikes and create 416 SubscribedOption records
    └─ Result: 416 records in DB with is_subscribed=False
    ↓
WebSocketService subscribes to all 416 options
    └─ Batch subscribe or individual: calls Upstox WebSocket API
    └─ Updates is_subscribed=True and websocket_token for each
    ↓
Real-time data flows in
    └─ Last_price updated continuously for all 416 options
    ↓
GreeksCalculator subscribes to this data
    └─ Calculates IV, Delta, Gamma, Theta, Vega
    └─ Stores in Tick table
    ↓
SignalDetector analyzes for trading signals
    └─ Uses Greeks and price data
    └─ Triggers BUY/SELL signals
```

## Storage Strategy

**Why only store ~416 filtered options?**
1. **Focused**: Only tracking options we actually care about (ATM ± 1)
2. **Efficient**: Avoids storing 1000+ unused options
3. **Updatable**: Can refresh spot prices during trading hours if needed
4. **Traceable**: Each option has `spot_price_at_subscription` - can see if ATM moved far

**Refresh Strategy**:
- Current: Refresh at app startup (or 9:18 AM)
- Future: Can add periodic refresh (every N hours) to catch big spot moves

## Next Steps

1. **Integrate Upstox API**: Implement real API calls in `fetch_spot_price()` and `fetch_options_chain()`
2. **WebSocket Subscription**: Update `WebSocketService` to subscribe to SubscribedOption records
3. **Test Flow**: Boot app → Check SubscribedOption table → Verify ~416 records → Verify WebSocket subscriptions
4. **Greeks Calculation**: Once pricing flows in, calculate Greeks for each option
5. **Signal Generation**: Detect trading signals based on Greeks changes

## Current Status

- ✅ Symbol table: 188 FNO symbols loaded
- ✅ SubscribedOption model: Created and ready
- ✅ OptionsLoaderService: Implemented (mock data for now)
- ✅ Integration into main.py: Done
- ⏳ Upstox API integration: Pending (currently uses mock spot prices)
- ⏳ WebSocket subscription: Pending (currently options created but not subscribed)

## Testing

To test locally:
```bash
# Start app
docker compose up

# Check logs - should see:
# 📋 Loading options at startup...
# [Progress] Processed 50/188 symbols...
# ✅ Options loaded: 416 subscribed options ready

# Verify in database:
SELECT COUNT(*) FROM subscribed_options;  -- Should be ~416
SELECT symbol, option_type, strike_price FROM subscribed_options LIMIT 10;
```
