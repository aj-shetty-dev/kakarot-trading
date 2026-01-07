# Connection Resilience - Deployment & Verification Checklist

**Date**: January 7, 2026  
**Status**: ✅ READY FOR DEPLOYMENT  
**Risk Level**: 🟢 MINIMAL (Non-disruptive changes only)

---

## Pre-Deployment Verification

### Code Quality ✅
- [x] No syntax errors
- [x] All imports working
- [x] New methods tested locally
- [x] Backward compatible (all existing APIs unchanged)

### Test Coverage ✅
- [x] DNS fallback logic verified
- [x] Price caching verified
- [x] Position monitoring with fallback verified
- [x] Emergency close API endpoints created
- [x] Connection health monitoring endpoint created

### Documentation ✅
- [x] CONNECTION_RESILIENCE_IMPROVEMENTS.md created
- [x] CONNECTION_RESILIENCE_QUICKSTART.md created
- [x] IMPLEMENTATION_SUMMARY.md created

---

## Deployment Steps

### Step 1: Verify Current State
```bash
# Check WebSocket connection
curl http://localhost:8000/api/v1/monitoring/connection-health

# Check current logs
docker logs upstox_trading_bot | tail -50 | grep -E "websocket|connection"
```

### Step 2: Deploy Code Changes
```bash
# The following files were modified (non-disruptive):
# ✅ backend/src/config/constants.py         (+19 lines)
# ✅ backend/src/websocket/client.py         (+100 lines) 
# ✅ backend/src/trading/service.py          (+50 lines)
# ✅ backend/src/api/routes/monitoring.py    (+80 lines)
# ✅ docs/* (new documentation)

# No database migrations needed
# No breaking changes to existing APIs
# No configuration changes required
```

### Step 3: Restart System
```bash
# Rebuild Docker image with new code
docker-compose down
docker-compose up -d --build

# Verify all containers are running
docker ps | grep upstox

# Should show 4 healthy containers:
# - upstox_trading_bot
# - upstox_dashboard
# - upstox_postgres
# - upstox_redis
```

### Step 4: Verify Deployment
```bash
# Check API health
curl http://localhost:8000/api/v1/monitoring/health

# Check WebSocket status
curl http://localhost:8000/api/v1/monitoring/connection-health | jq

# Check logs for startup
docker logs upstox_trading_bot | tail -100 | grep -E "SUCCESS|ERROR"
```

---

## Post-Deployment Verification

### Immediate (First 5 minutes)
- [ ] All containers running and healthy
- [ ] Trading bot API responding on port 8000
- [ ] Dashboard responsive on port 8501
- [ ] WebSocket connecting successfully
- [ ] No new error messages in logs

**Verification commands**:
```bash
# 1. Container health
docker ps --format "table {{.Names}}\t{{.Status}}"

# 2. API health
curl http://localhost:8000/api/v1/monitoring/health

# 3. Dashboard health  
curl http://localhost:8501

# 4. WebSocket status
curl http://localhost:8000/api/v1/monitoring/connection-health | jq .websocket

# 5. No errors in last 100 lines
docker logs upstox_trading_bot | tail -100 | grep ERROR
```

### Short-term (First 30 minutes)
- [ ] Signals detected and logged
- [ ] Trades executing normally
- [ ] Price data flowing to database
- [ ] Position monitoring active
- [ ] No fallback usage (normal operation)

**Verification commands**:
```bash
# 1. Check signals
docker logs upstox_trading_bot | grep "SIGNAL DETECTED" | wc -l

# 2. Check trades
curl http://localhost:8000/api/v1/monitoring/status | jq .trades

# 3. Check price updates
docker logs upstox_trading_bot | grep "LIVE FEED" | tail -5

# 4. Check monitoring
docker logs upstox_trading_bot | grep "position monitoring" | tail -5

# 5. Check fallback (should be empty)
docker logs upstox_trading_bot | grep "FALLBACK" | wc -l  # Should be 0
```

### Medium-term (First few hours)
- [ ] Multiple candles processed
- [ ] Position exits executing correctly
- [ ] No stale price warnings (normal)
- [ ] Reconnection working if disconnection occurs
- [ ] Cache operating silently in background

**Verification commands**:
```bash
# 1. Candle processing
docker logs upstox_trading_bot | grep "candle" | wc -l

# 2. Position closes
docker logs upstox_trading_bot | grep -E "\[TP\]|\[SL\]" | wc -l

# 3. System stability
docker stats --no-stream | grep upstox

# 4. Error count
docker logs upstox_trading_bot | grep ERROR | wc -l
```

---

## Emergency Rollback Procedure

If any issues are found, rollback is immediate and non-breaking:

```bash
# Option 1: Revert code changes (if in git)
git revert <commit-hash>

# Option 2: Restore from backup (if available)
# ... restore files from previous backup

# Restart system
docker-compose down
docker-compose up -d --build

# Verify
curl http://localhost:8000/api/v1/monitoring/health
```

**No data loss occurs during rollback** ✅

---

## New Features Verification

### Feature 1: DNS Fallback
```bash
# In logs, should see DNS resolution attempts
docker logs upstox_trading_bot | grep "\[DNS\]"

# Expected output:
# [DNS] Attempting to resolve api.upstox.com with system DNS...
# [DNS] ✅ Resolved api.upstox.com → X.X.X.X (system DNS)
```

### Feature 2: Price Caching
```bash
# Check that prices are being cached
curl http://localhost:8000/api/v1/monitoring/connection-health | jq .price_cache

# Expected:
# {
#   "cached_symbols": 208,
#   "cache_entries": { ... }
# }
```

### Feature 3: Enhanced Position Monitoring
```bash
# Monitoring should run normally
docker logs upstox_trading_bot | grep "position monitoring" | tail -3

# If SL/TP triggers, should see:
# [SL] SYMBOL: Price X <= SL Y
# [TP] SYMBOL: Price X >= TP Y
```

### Feature 4: Emergency Close API
```bash
# Test the API (will fail if no open trades, that's OK)
curl -X POST http://localhost:8000/api/v1/monitoring/emergency-close-position \
  -H "Content-Type: application/json" \
  -d '{"symbol": "INVALID", "reason": "test"}'

# Expected response for non-existent trade:
# {"detail":"No open trade found for INVALID"}
```

### Feature 5: Connection Health API
```bash
# Test the health endpoint
curl http://localhost:8000/api/v1/monitoring/connection-health | jq

# Should return full status
```

---

## Monitoring After Deployment

### Daily Checks (Every morning)
```bash
# 1. System health
curl http://localhost:8000/api/v1/monitoring/health

# 2. Connection status
curl http://localhost:8000/api/v1/monitoring/connection-health | jq .websocket

# 3. Error count in past 24h
docker logs upstox_trading_bot --since 24h | grep ERROR | wc -l
# Should be low (0-5 normal)
```

### Weekly Checks
```bash
# 1. DNS failures
docker logs upstox_trading_bot --since 7d | grep "\[DNS\]" | grep ERROR | wc -l
# Should be 0

# 2. Reconnection attempts
docker logs upstox_trading_bot --since 7d | grep "Reconnecting" | wc -l
# Should be 0 or very low

# 3. Fallback usage
docker logs upstox_trading_bot --since 7d | grep "\[FALLBACK\]" | wc -l
# Should be 0 (indicates no disconnections)
```

### Performance Impact
```bash
# Monitor resource usage
docker stats upstox_trading_bot --no-stream

# Expected (no significant increase):
# CPU: < 5%
# Memory: < 800MB
# Net I/O: Normal
```

---

## Issues & Resolution

### Issue: "DNS fallback not being used"
**Check**:
```bash
docker logs upstox_trading_bot | grep "\[DNS\]"
```

**Resolution**:
- If you see `[DNS] ✅ Resolved ... (system DNS)` → System DNS working fine
- DNS fallback only activates on failures
- This is expected behavior

---

### Issue: "Price cache not updating"
**Check**:
```bash
curl http://localhost:8000/api/v1/monitoring/connection-health | jq .price_cache
```

**Resolution**:
- If `cached_symbols: 0` → WebSocket may not be connected
- Check WebSocket connection: `... | jq .websocket`
- Verify access token is valid

---

### Issue: "Fallback triggering too often"
**Check**:
```bash
docker logs upstox_trading_bot | grep "\[FALLBACK\]" | wc -l
```

**Resolution**:
- More than 1-2 per day indicates network issues
- Check internet connection stability
- Monitor ISP DNS resolution status

---

### Issue: "Emergency close API returning error"
**Check**:
```bash
# Verify symbol and status
curl http://localhost:8000/api/v1/monitoring/status | jq .open_trades
```

**Resolution**:
- Ensure symbol exists in open trades
- Check exact symbol name (case-sensitive)
- Verify trade status is OPEN

---

## Success Criteria

Deployment is successful when:

✅ **All containers running** - No restart loops  
✅ **No new errors** - Error count same as before  
✅ **APIs responding** - All endpoints return 200 OK  
✅ **Price data flowing** - WebSocket receiving ticks  
✅ **Position monitoring active** - Monitoring running every 1 second  
✅ **No fallback triggers** - Cache used only on network issues  
✅ **Documentation complete** - All new features documented  

---

## Sign-Off

- [x] Code changes verified
- [x] Tests passed
- [x] Documentation complete
- [x] Rollback procedure ready
- [x] Monitoring plan established
- [x] Ready for deployment

**Deployed by**: Automated System  
**Deployment date**: January 7, 2026  
**Environment**: Production (upstox_trading_bot)

---

## Support

For issues or questions:
1. Check logs: `docker logs upstox_trading_bot`
2. Use health endpoint: `GET /api/v1/monitoring/connection-health`
3. Review documentation: See `docs/CONNECTION_RESILIENCE_QUICKSTART.md`
4. Emergency close: Use POST `/api/v1/monitoring/emergency-close-position`

