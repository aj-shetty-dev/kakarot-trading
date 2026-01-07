# Connection Resilience Quick Start Guide

## Overview

The system now has **3 layers of resilience** to handle WebSocket disconnections:

1. **Layer 1 - Live WebSocket Prices** (Normal operation)
2. **Layer 2 - Cached Prices** (Fallback for ~5 minutes)
3. **Layer 3 - Manual API** (Emergency control)

---

## Automatic Features (No Action Needed)

### 1. DNS Fallback Resolution
When system DNS fails to resolve api.upstox.com:
- ✅ Automatically tries Google DNS
- ✅ Then tries Cloudflare DNS
- ✅ Fallback happens silently

**Check DNS in logs**:
```bash
docker logs upstox_trading_bot | grep "\[DNS\]"
```

Example output:
```
[DNS] ⚠️ System DNS failed: Name or service not known
[DNS] Trying 8.8.8.8...
[DNS] ✅ Resolved api.upstox.com → 8.8.8.8 (via Google)
```

---

### 2. Automatic Position Monitoring with Fallback
When WebSocket disconnects:
- ✅ Position monitoring continues
- ✅ Uses last cached prices
- ✅ Triggers SL/TP automatically
- ✅ Logs when using fallback data

**Check position monitoring in logs**:
```bash
docker logs upstox_trading_bot | grep -E "\[FALLBACK\]|\[SL\]|\[TP\]"
```

Example output:
```
[FALLBACK] Using stale price for BOSCHLTD: ₹575 (45s old)
[SL] BOSCHLTD: Price ₹575 <= SL ₹698.25 (FALLBACK)
Position closed successfully
```

---

### 3. Smarter Reconnection
Enhanced exponential backoff with:
- ✅ Random jitter (prevents thundering herd)
- ✅ DNS health checks every 3 attempts
- ✅ Automatic resubscription after reconnect

**Check reconnection in logs**:
```bash
docker logs upstox_trading_bot | grep -E "\[VERBOSE\] Reconnecting"
```

Example:
```
[VERBOSE] Reconnecting (attempt 1/10)...
[VERBOSE] Waiting 6.2 seconds before retry (with jitter)...
[DNS] Checking DNS health...
[DNS] ✅ Resolved api.upstox.com → 1.1.1.1 (via Cloudflare DNS)
```

---

## Manual Features (When Needed)

### Check Connection Health

See real-time status of WebSocket and price cache:

```bash
curl http://localhost:8000/api/v1/monitoring/connection-health | jq
```

**Response**:
```json
{
    "timestamp": "2026-01-07T11:30:00+05:30",
    "websocket": {
        "connected": false,
        "subscribed_symbols": 208,
        "reconnect_attempts": 5,
        "network_errors": 3
    },
    "price_cache": {
        "cached_symbols": 45,
        "last_update": 1704534000.0,
        "cache_entries": {
            "BOSCHLTD": {
                "price": 575.00,
                "age_seconds": 45,
                "is_stale": true
            },
            "KAYNES": {
                "price": 204.10,
                "age_seconds": 3,
                "is_stale": false
            }
        }
    }
}
```

**What it tells you**:
- `connected: false` → WebSocket is down
- `age_seconds: 45` → Price is 45 seconds old
- `is_stale: true` → Price older than 30 seconds (warning)
- `cache_entries` → Sample of cached prices

---

### Emergency: Manually Close a Position

**Use when**: WebSocket has been down for 5+ minutes and position monitoring used all cached prices

**Command**:
```bash
curl -X POST http://localhost:8000/api/v1/monitoring/emergency-close-position \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BOSCHLTD",
    "reason": "stop_loss"
  }'
```

**Reasons**:
- `"stop_loss"` - Close due to hitting stop loss
- `"take_profit"` - Close due to hitting take profit
- `"emergency"` - Close for any other reason

**Response**:
```json
{
    "status": "success",
    "symbol": "BOSCHLTD",
    "entry_price": 735.00,
    "exit_price": 575.00,
    "pnl": -6195.00,
    "reason": "stop_loss",
    "message": "Position BOSCHLTD closed successfully"
}
```

---

## Decision Tree: What to Do During Outage

```
Network Down?
    ↓
Check: curl http://localhost:8000/api/v1/monitoring/connection-health
    ↓
Is WebSocket Connected?
    ├─ YES: Automatic fallback in progress, wait for reconnection
    │
    └─ NO: Check Time Since Last Price Update
         ├─ < 30 seconds: Position monitoring using fresh cached prices
         │                Wait 2-3 minutes for reconnection
         │
         ├─ 30-300 seconds: Position monitoring using stale cached prices
         │                  Monitor logs for SL/TP triggers
         │                  Be prepared to manually close if needed
         │
         └─ > 300 seconds: Cache expired, no fallback available
                           Manually close risky positions
                           Use emergency API endpoint
```

---

## Real-Time Log Monitoring

### Watch All WebSocket Activity
```bash
docker logs -f upstox_trading_bot | grep websocket
```

### Watch Position Monitoring
```bash
docker logs -f upstox_trading_bot | grep -E "\[SL\]|\[TP\]|\[FALLBACK\]"
```

### Watch DNS Issues
```bash
docker logs -f upstox_trading_bot | grep "\[DNS\]"
```

### Watch Reconnection Attempts
```bash
docker logs -f upstox_trading_bot | grep "\[VERBOSE\] Attempting reconnection"
```

---

## Scenario Examples

### Example 1: Brief Disconnection (30 seconds)

**Time**: 11:24:16 - Disconnection detected

**What Happens Automatically**:
```
11:24:16 [WARNING] WebSocket connection closed
11:24:20 [VERBOSE] Reconnecting (attempt 1/10)...
11:24:25 [VERBOSE] Attempting reconnection...
11:24:25 [SUCCESS] Reconnection successful!
11:24:26 [FALLBACK] Using cached price for KAYNES: ₹204.10 (10s old)
11:24:26 [TP] KAYNES: Price ₹204.10 >= TP ₹197.76 (FALLBACK)
Position closed successfully
```

**No manual action needed** ✅

---

### Example 2: Extended Disconnection (5+ minutes)

**Time**: 11:24:16 - Disconnection detected

**What Happens**:
```
11:24:16 [WARNING] WebSocket connection closed
11:24:20 [VERBOSE] Reconnecting (attempt 1/10)...  
11:24:25 [ERROR] Reconnection failed - DNS still failing
11:24:30 [VERBOSE] Reconnecting (attempt 2/10)...
11:24:40 [ERROR] Reconnection failed
...continues trying every 5-10 seconds...
11:29:16 [FALLBACK] Price cache expired for BOSCHLTD
11:29:16 [WARNING] Can't monitor BOSCHLTD - no fresh prices
```

**Manual Action Needed**:
```bash
# Check status
curl http://localhost:8000/api/v1/monitoring/connection-health

# If WebSocket still down, close the position
curl -X POST http://localhost:8000/api/v1/monitoring/emergency-close-position \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BOSCHLTD", "reason": "emergency"}'
```

---

### Example 3: DNS Resolution Failure

**Symptom**: WebSocket connects but immediately fails with DNS error

**Automatic Handling**:
```
[ERROR] Network error during authorization: ClientConnectorError
[VERBOSE] Cannot connect to host api.upstox.com:443 ssl:default [Temporary failure in name resolution]
[DNS] Checking DNS health...
[DNS] ⚠️ System DNS failed: Name or service not known
[DNS] Trying 8.8.8.8...
[DNS] ✅ Resolved api.upstox.com → 8.8.8.8 (via Google DNS)
[VERBOSE] Attempting reconnection with fallback DNS...
[SUCCESS] WebSocket connection established!
```

**No manual action needed** ✅

---

## Monitoring During Normal Operation

### Daily Health Check
```bash
# Quick health check
curl http://localhost:8000/api/v1/monitoring/connection-health | jq .websocket

# Should show:
# {
#   "connected": true,
#   "subscribed_symbols": 208,
#   "reconnect_attempts": 0,
#   "network_errors": 0
# }
```

### Weekly Review
```bash
# Check DNS failure history
docker logs upstox_trading_bot | grep "\[DNS\]" | wc -l

# Should be 0 for healthy system
```

---

## Troubleshooting

### "Price is stale" warnings in logs

**What it means**: WebSocket down for 30+ seconds, using cached prices

**What to do**:
1. Check connection: `curl http://localhost:8000/api/v1/monitoring/connection-health`
2. Wait 2-3 minutes for automatic reconnection
3. Monitor logs for reconnection attempts
4. If still down after 5 min, manually close at-risk positions

---

### "Cannot resolve api.upstox.com"

**What it means**: DNS resolution failed even with fallbacks

**What to do**:
1. Check your internet connection
2. System will keep trying automatically
3. If persistent > 5 min, check ISP status
4. Can manually close positions via emergency API

---

### No prices being cached

**What it means**: WebSocket has never connected successfully

**What to do**:
1. Check access token: `curl http://localhost:8000/api/v1/monitoring/status`
2. Verify Upstox API credentials in .env
3. Restart trading bot: `docker-compose restart`

---

## Summary

| Layer | Trigger | Action | Duration |
|-------|---------|--------|----------|
| **Layer 1** | Normal | Use live WebSocket | Always |
| **Layer 2** | WebSocket down | Use cached prices | 5 minutes |
| **Layer 3** | Cache expired | Manual API close | On demand |

The system now handles network issues gracefully with automatic fallbacks. Manual intervention is only needed for extended outages (> 5 minutes).

