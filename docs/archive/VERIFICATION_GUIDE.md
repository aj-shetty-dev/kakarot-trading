# Phase 2 Verification & Testing Guide

## 🎯 Overview

Phase 2 is complete and ready for verification! This guide shows you how to check that everything is working correctly and see real market data flowing through the system.

## ✅ Verification Options

### Option 1: Quick Shell Check (Recommended for Quick Verification)

**File**: `verify_phase2.sh`

Simple bash script using `curl` - no dependencies needed!

```bash
# Make executable
chmod +x /Users/shetta20/Projects/upstox/backend/verify_phase2.sh

# Run full verification
./verify_phase2.sh

# Or run specific checks
./verify_phase2.sh health          # Check if app is running
./verify_phase2.sh status          # Get WebSocket status
./verify_phase2.sh ticks           # Get latest tick data
./verify_phase2.sh monitor 30      # Monitor for 30 seconds
```

**Output**:
```
✅ Application is running
📋 Subscriptions:
  Total Symbols:    156
  Subscribed:       156
  Failed:           0
  Success Rate:     100.00%

📈 Latest market data...
Updates: 45,230
✅ Data is flowing! Latest prices available.
```

### Option 2: Python Dashboard (Best for Monitoring)

**File**: `dashboard.py`

Interactive Python dashboard showing real-time data - uses only standard library!

```bash
# Make executable
chmod +x /Users/shetta20/Projects/upstox/backend/dashboard.py

# Run dashboard
python3 /Users/shetta20/Projects/upstox/backend/dashboard.py

# Or from backend directory
cd /Users/shetta20/Projects/upstox/backend
python3 dashboard.py
```

**Features**:
- ✅ Real-time status display
- ✅ Live data monitoring (shows updates/sec)
- ✅ Performance metrics
- ✅ Interactive (asks if you want to monitor)

**Output**:
```
╔════════════════════════════════════════════════════════════════════════════════╗
║                  🎯 PHASE 2 LIVE DASHBOARD                                    ║
║                   WebSocket Market Data Verification                          ║
╚════════════════════════════════════════════════════════════════════════════════╝

═════════════════════════════════════════════════════════════════════════════════
 📊 WEBSOCKET STATUS
═════════════════════════════════════════════════════════════════════════════════

 Running:          ✅ True
 Connected:        ✅ True

 📋 SUBSCRIPTIONS:
    Total Symbols:    156
    Subscribed:       156
    Failed:           0
    Success Rate:     100.00%

 🔤 SAMPLE SYMBOLS (first 10):
    • INFY
    • TCS
    • RELIANCE
    • SBIN
    • HDFC
    ...
```

### Option 3: Direct API Calls with Curl

**No scripts needed** - use curl directly:

```bash
# Check health
curl http://localhost:8000/health

# Get WebSocket status
curl http://localhost:8000/api/v1/websocket/status

# Get subscriptions
curl http://localhost:8000/api/v1/websocket/subscriptions

# Get latest ticks
curl http://localhost:8000/api/v1/websocket/latest-ticks
```

**With pretty formatting (requires jq)**:
```bash
# Install jq
brew install jq

# Get status with pretty formatting
curl -s http://localhost:8000/api/v1/websocket/status | jq .

# Get latest ticks (first 3)
curl -s http://localhost:8000/api/v1/websocket/latest-ticks | jq '.latest_ticks | to_entries[:3]'
```

## 🚀 Getting Started

### Step 1: Start the Application

```bash
cd /Users/shetta20/Projects/upstox/backend
docker-compose up
```

**Wait for startup messages:**
```
upstox-app-1     | ✅ Database initialized
upstox-app-1     | 📡 Initializing WebSocket service...
upstox-app-1     | ✅ WebSocket service initialized
upstox-app-1     | Uvicorn running on 0.0.0.0:8000
```

### Step 2: Verify in Another Terminal

```bash
# Option A: Quick bash check
./backend/verify_phase2.sh full

# Option B: Interactive dashboard
python3 backend/dashboard.py

# Option C: Direct curl
curl http://localhost:8000/api/v1/websocket/status | jq .
```

### Step 3: Interpret Results

**✅ Success Indicators**:
- `is_running: true`
- `websocket_connected: true`
- `subscribed_count: 156` (or close to it)
- `subscription_rate: 100.00%`
- `price_updates: > 0`

**⚠️ Warning Signs**:
- `websocket_connected: false` - Check network, Upstox credentials
- `price_updates: 0` - Market may be closed, or subscription pending
- `failed_count: > 0` - Some subscriptions failed, check logs

## 📊 What You Should See

### During Market Hours

```
✅ Application running
✅ WebSocket connected
✅ 156/156 symbols subscribed (100%)
✅ Updates flowing in (thousands per minute)
✅ Latest prices available in cache
✅ Database recording ticks
```

### After Market Hours

```
✅ Application running
✅ WebSocket connected
✅ 156/156 symbols subscribed (100%)
⏳ Updates minimal (market closed)
✅ Latest prices available (from last trading)
✅ System ready for next market open
```

## 🔍 Troubleshooting

### "Connection refused"
**Problem**: App not running
```bash
# Check if containers are up
docker-compose ps

# If not, start them
docker-compose up -d
```

### "WebSocket not connected"
**Problem**: API credentials invalid or network issue
```bash
# Check credentials in .env
cat .env | grep UPSTOX

# Check logs
docker-compose logs app | grep -i websocket
```

### "No price updates"
**Problem**: Market closed or data not flowing
```bash
# Check current time
date

# Check if market is open (9:15 AM - 3:30 PM IST, Mon-Fri)
# If closed, data will resume at next market open

# Check subscriptions are working
curl http://localhost:8000/api/v1/websocket/subscriptions | jq .
```

### "High failed subscriptions"
**Problem**: Some symbols couldn't subscribe
```bash
# This is normal for a few symbols
# System will retry automatically

# Monitor retry status
./verify_phase2.sh monitor 60

# Check logs for details
docker-compose logs app | grep -i "failed\|retry"
```

## 📈 Understanding the Metrics

### `symbols_tracked`
- Number of symbols in in-memory cache
- Should be close to 156 (all FNO symbols minus exclusions)
- Only updates when data received

### `price_updates`
- Total number of tick updates received
- Increases continuously during market hours
- Indicates data flow rate

### `subscription_rate`
- Percentage of symbols successfully subscribed
- Should be 100% after 5 seconds
- Anything >95% is acceptable

### `updates_per_second` (in monitor mode)
- How many ticks per second being processed
- Typical: 50-500 updates/sec depending on volatility
- Peak: 1000+ during high volatility

## 🧪 Test Scenarios

### Test 1: Verify Connection (5 seconds)
```bash
./verify_phase2.sh health
```
**Expected**: ✅ App is running

### Test 2: Check Full Status (10 seconds)
```bash
./verify_phase2.sh status
```
**Expected**: All 156 symbols subscribed, 100% rate

### Test 3: Monitor Live Data (30 seconds)
```bash
./verify_phase2.sh monitor 30
```
**Expected**: Positive updates/second rate

### Test 4: Run Dashboard (1-2 minutes)
```bash
python3 dashboard.py
# Answer 'y' to monitor for 30 seconds
```
**Expected**: Continuous updates showing in monitoring

## 📝 Next Steps After Verification

### ✅ If Everything Works
Great! Phase 2 is operational. Move to **Phase 3: Spike Detection**
- Technical indicators (MA20, MA50, MA200)
- Volume analysis
- Signal generation

### ⚠️ If Issues Found
1. Check logs: `docker-compose logs app`
2. Verify credentials: `cat .env`
3. Check network: `ping api.upstox.com`
4. Restart: `docker-compose restart`

## 💡 Pro Tips

### Monitor with Tail (Watch log updates)
```bash
docker-compose logs -f app | grep -i "websocket\|subscribed\|tick"
```

### Count Total Ticks Received
```bash
sqlite3 /Users/shetta20/Projects/upstox/backend/upstox_trading.db \
  "SELECT COUNT(*) FROM tick;"
```

### Show Database Schema
```bash
sqlite3 /Users/shetta20/Projects/upstox/backend/upstox_trading.db \
  ".schema tick"
```

### Check Latest Ticks in Database
```bash
sqlite3 /Users/shetta20/Projects/upstox/backend/upstox_trading.db \
  "SELECT symbol_id, price, timestamp FROM tick ORDER BY timestamp DESC LIMIT 5;"
```

## 🎓 Understanding the Data Flow

```
Real Market Data (Upstox API)
            ↓
    WebSocket Connection
    (Bearer Token Auth)
            ↓
    Symbol Subscription
    (Batched: 50/batch)
            ↓
    Tick Reception
    (~1000 ticks/sec)
            ↓
    ┌─────────────┬──────────────┐
    ↓             ↓
  Database      In-Memory
  (Persistent)  (Fast Lookup)
    ↓             ↓
  PostgreSQL    Python Dict
  (or SQLite)   {symbol: tick}
    ↓             ↓
    └─────────────┬──────────────┘
            ↓
    HTTP API Endpoints
    (/api/v1/websocket/*)
```

## 📞 Quick Reference

| Task | Command |
|------|---------|
| Check health | `curl http://localhost:8000/health` |
| Get status | `./verify_phase2.sh status` |
| Monitor live | `python3 dashboard.py` |
| View logs | `docker-compose logs -f app` |
| Count ticks | `sqlite3 upstox_trading.db "SELECT COUNT(*) FROM tick;"` |
| Restart app | `docker-compose restart` |
| Full reset | `docker-compose down && docker-compose up` |

---

**Ready to verify? Start with:**
```bash
./verify_phase2.sh full
```

**Then monitor live data with:**
```bash
python3 dashboard.py
```

**Questions? Check logs:**
```bash
docker-compose logs app
```
