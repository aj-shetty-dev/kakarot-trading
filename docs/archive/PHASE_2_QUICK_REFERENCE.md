# Phase 2 Quick Reference Guide

## 🚀 Getting Started with WebSocket Data

### Start the WebSocket Service
```python
# Automatically started in main.py lifespan
# Just run: python -m uvicorn src.main:app --reload
```

### Check Status
```bash
# WebSocket connection status
curl http://localhost:8000/api/v1/websocket/status

# Subscription details
curl http://localhost:8000/api/v1/websocket/subscriptions

# Latest tick data
curl http://localhost:8000/api/v1/websocket/latest-ticks
```

## 📡 How It Works

### The Complete Flow
1. **Startup** → WebSocketService initializes in main.py
2. **Connection** → UpstoxWebSocketClient connects with Bearer token
3. **Loading** → SubscriptionManager loads FNO symbols from database
4. **Subscription** → Symbols subscribed in batches of 50
5. **Listening** → WebSocket receives tick messages continuously
6. **Processing** → Each tick routed through TickDataHandler and AggregatedTickHandler
7. **Storage** → Persisted to PostgreSQL, cached in memory
8. **API Access** → Query via endpoints or use aggregated handler directly

### Example Response
```json
{
  "is_running": true,
  "websocket_connected": true,
  "subscriptions": {
    "total_symbols": 156,
    "subscribed_count": 156,
    "failed_count": 0,
    "subscription_rate": "100.00%"
  }
}
```

## 🔧 Common Tasks

### Access Latest Tick for a Symbol
```python
from src.websocket.handlers import get_aggregated_handler

handler = get_aggregated_handler()
latest_tick = handler.get_latest_tick("INFY")
print(f"Price: {latest_tick['price']}, Volume: {latest_tick['volume']}")
```

### Subscribe to Additional Symbols
```python
from src.websocket.service import get_websocket_service

service = get_websocket_service()
await service.subscribe_symbol("TCS")  # Add a new symbol
```

### Get All Subscribed Symbols
```python
from src.websocket.service import get_websocket_service

service = get_websocket_service()
status = service.get_status()
symbols = status["subscribed_symbols"]
print(f"Subscribed to {len(symbols)} symbols")
```

### Access Tick Statistics
```python
from src.websocket.handlers import get_tick_handlers

handlers = get_tick_handlers()
db_stats = handlers["db_handler"].get_stats()
agg_stats = handlers["aggregated_handler"].get_stats()

print(f"Ticks in DB: {db_stats['ticks_processed']}")
print(f"Symbols tracked: {agg_stats['symbols_tracked']}")
```

## 🐛 Troubleshooting

### No Ticks Arriving?
```python
# Check WebSocket connection
service = get_websocket_service()
print(f"Connected: {service.ws_client.is_connected}")
print(f"Subscribed: {len(service.ws_client.get_subscribed_symbols())} symbols")

# Check handlers
handlers = get_tick_handlers()
print(f"DB ticks: {handlers['db_handler'].tick_count}")
```

### API Key Error?
```bash
# Verify credentials in .env
cat .env | grep UPSTOX

# Check logs
tail -f /app/logs/errors.log | grep -i auth
```

### Database Not Receiving Ticks?
```bash
# Check database connection
docker ps | grep postgres

# Query ticks
docker exec upstox-postgres psql -U trading -d upstox_trading -c "SELECT COUNT(*) FROM tick LIMIT 1;"
```

## 📚 Key Components

### UpstoxWebSocketClient
```python
# Location: src/websocket/client.py
# Purpose: WebSocket connection management
# Key Methods: connect(), subscribe(), listen(), register_handler()
```

### SubscriptionManager
```python
# Location: src/websocket/subscription_manager.py
# Purpose: Symbol subscription management
# Key Methods: subscribe_to_universe(), subscribe_to_symbols(), get_subscription_status()
```

### Handlers
```python
# Location: src/websocket/handlers.py
# Purpose: Tick processing
# Types: TickDataHandler (persistence), AggregatedTickHandler (cache)
```

### WebSocketService
```python
# Location: src/websocket/service.py
# Purpose: Main orchestrator
# Key Methods: start(), stop(), get_status()
```

## 🔌 Adding Custom Handlers

### Create New Handler
```python
from src.websocket.data_models import TickData
from src.websocket.client import get_websocket_client

class MyCustomHandler:
    async def handle_tick(self, tick: TickData) -> bool:
        # Your custom logic here
        print(f"Got tick: {tick.symbol} @ {tick.last_price}")
        return True

# Register with client
client = get_websocket_client()
await client.register_handler(MyCustomHandler().handle_tick)
```

## 📊 Performance Tips

### High Frequency Requirements
- Use AggregatedTickHandler for O(1) lookups
- Avoid querying database during peak hours
- Cache latest ticks in application layer

### Historical Analysis
- Query Tick table during off-hours
- Use pagination for large queries
- Consider data aggregation (1min, 5min OHLC)

### Memory Management
- Clear aggregated cache periodically
- Monitor database connection pool
- Watch for memory leaks in custom handlers

## 📝 Logging Reference

### Check Recent Logs
```bash
# All events
tail -f /app/logs/trading.log

# Errors only
tail -f /app/logs/errors.log

# Signal events
tail -f /app/logs/signals.log

# Search for specific symbol
grep "INFY" /app/logs/trading.log
```

### Log Levels
- `INFO` - Normal operations
- `WARNING` - Non-critical issues
- `ERROR` - Critical issues
- `DEBUG` - Detailed debugging

## 🧪 Testing

### Run All Tests
```bash
pytest backend/tests/test_websocket_integration.py -v
```

### Test Specific Component
```bash
# Client tests only
pytest backend/tests/test_websocket_integration.py::TestUpstoxWebSocketClient -v

# Handler tests only
pytest backend/tests/test_websocket_integration.py::TestTickDataHandlers -v
```

### With Coverage
```bash
pytest backend/tests/ --cov=src/websocket --cov-report=html
open htmlcov/index.html
```

## 🔐 Security Checklist

- [ ] .env file has correct permissions (600)
- [ ] No credentials in version control
- [ ] Access token refreshed before expiry
- [ ] TLS/SSL connection (wss://)
- [ ] Logs don't contain sensitive data

## 📞 Support

### Common Issues

| Issue | Solution |
|-------|----------|
| WebSocket disconnects | Check network, increase keepalive interval |
| Slow tick processing | Optimize handlers, increase batch size |
| High memory usage | Reduce cache size, restart service |
| Missing ticks | Check subscriptions, verify handler registration |
| Database errors | Check connection, verify schema, check disk space |

### Debug Mode
```python
import logging
logging.getLogger("websocket").setLevel(logging.DEBUG)
```

## 📋 Deployment Checklist

```bash
# Pre-deployment verification
python -m pytest backend/tests/ -v
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/websocket/status

# Docker deployment
docker-compose up -d
docker-compose logs -f websocket

# Post-deployment verification
docker-compose ps
docker exec upstox-app curl http://localhost:8000/health
```

## 🎯 What's Next?

Phase 2 complete! Ready for:
- **Phase 3:** Spike detection algorithm
- **Phase 4:** AI noise filtering
- **Phase 5:** Order execution

Start Phase 3 when ready:
```bash
git checkout -b phase-3-spike-detection
```

---

**Keep this guide handy for quick reference!**
