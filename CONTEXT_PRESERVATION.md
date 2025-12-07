# Project Context & Session Continuity

## Quick Context Reference

### Project Overview
- **Name**: Upstox Algorithmic Trading Bot
- **Objective**: Automated FNO trading with AI-powered spike detection
- **Stack**: FastAPI, PostgreSQL, WebSockets, Python 3.11
- **Location**: `/Users/shetta20/Projects/upstox/`

### Upstox API Credentials (in `.env`)
```
UPSTOX_API_KEY=your_key
UPSTOX_API_SECRET=your_secret
UPSTOX_ACCESS_TOKEN=your_token
UPSTOX_CLIENT_CODE=49CLBQ
```

### Trading Parameters
- **Account Size**: ₹1,00,000
- **Risk Per Trade**: 5%
- **Position Size**: 30% of account
- **Stop Loss**: 5%
- **Take Profit**: 4%
- **Trailing Stop**: 2%
- **Max Positions**: 3 concurrent
- **Daily Loss Limit**: 2%

### FNO Trading Universe
- **All NSE FNO Symbols** EXCEPT: NIFTY, BANKNIFTY, FINANCENIFTY, NIFTYNEXT50
- **Total Symbols**: ~156 FNO symbols
- **Auto-loaded** from database on startup

### Critical API Details
- **WebSocket Endpoint**: `wss://api.upstox.com/v3` (V3 API - explicitly specified)
- **Authentication**: Bearer token in HTTP headers
- **Token Format**: `NSE_FO|SYMBOL` (e.g., `NSE_FO|INFY`)
- **Subscription Mode**: "full" (complete market data with Greeks)

### Project Structure
```
/Users/shetta20/Projects/upstox/
├── backend/
│   ├── src/
│   │   ├── config/          (settings, constants, logging)
│   │   ├── data/            (database models, ORM)
│   │   ├── websocket/       (Phase 2 - complete)
│   │   │   ├── client.py
│   │   │   ├── data_models.py
│   │   │   ├── subscription_manager.py
│   │   │   ├── handlers.py
│   │   │   ├── service.py
│   │   │   └── __init__.py
│   │   ├── signals/         (Phase 3 - pending)
│   │   ├── trading/         (Phase 5 - pending)
│   │   ├── monitoring/      (Phase 6 - pending)
│   │   └── main.py
│   ├── tests/
│   │   └── test_websocket_integration.py
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env
├── docs/
└── IMPLEMENTATION_PLAN.md
```

### Completed Phases

#### Phase 1: Foundation ✅ Complete
- Project scaffolding (13 directories)
- Configuration system (Pydantic BaseSettings)
- Database schema (8 ORM models)
- FastAPI initialization
- Docker setup
- FNO symbol screener
- Documentation (6 files)

#### Phase 2: WebSocket Integration ✅ Complete
- WebSocket client (V3 API with Bearer auth)
- Real-time tick data streaming (~1000 ticks/sec)
- Subscription batching (50 symbols/batch)
- Database persistence (Tick table)
- In-memory aggregation (latest prices)
- API endpoints for monitoring
- Integration tests (40+ test cases)
- Comprehensive documentation (5 files)

### Pending Phases

#### Phase 3: Spike Detection ⏳ Ready to Start
- Technical indicators (MA20, MA50, MA200)
- Volume spike analysis
- Momentum calculation
- Greeks analysis
- Signal generation

#### Phase 4: AI Noise Filter ⏸️ Queued
- Feature engineering
- Pre-trained ML model integration
- Confidence scoring

#### Phases 5-9 ⏸️ Queued
- Order execution
- Monitoring & dashboards
- Advanced testing
- Deployment & documentation

### Key Design Decisions

1. **Batch Subscription**: 50 symbols per batch with 1s delays
   - Prevents overwhelming Upstox API
   - 156 FNO symbols → 4-5 seconds to fully subscribe

2. **Dual-Handler Architecture**:
   - **TickDataHandler**: Persists to PostgreSQL (historical analysis)
   - **AggregatedTickHandler**: In-memory cache (real-time queries, O(1) lookup)

3. **Automatic Reconnection**: Exponential backoff (2s → 1024s, max 10 attempts)

4. **Bearer Token Auth**: In HTTP headers, not in URL or body

### Performance Targets
- **Tick Rate**: ~1,000 ticks/second
- **End-to-End Latency**: <20ms average
- **Subscription Time**: 4-5 seconds for 156 symbols
- **Memory Usage**: ~50MB base + 1MB per 100 symbols

### Documentation Files
- `PHASE_2_QUICK_REFERENCE.md` - Developer quick start
- `PHASE_2_COMPLETE.md` - Full technical documentation
- `PHASE_2_ARCHITECTURE.md` - Visual diagrams
- `PHASE_2_STATUS_REPORT.md` - Implementation report
- `IMPLEMENTATION_PLAN.md` - 9-phase roadmap

### Common Commands

**Check WebSocket Status**:
```bash
curl http://localhost:8000/api/v1/websocket/status
```

**View Latest Ticks**:
```bash
curl http://localhost:8000/api/v1/websocket/latest-ticks
```

**Run Tests**:
```bash
pytest backend/tests/test_websocket_integration.py -v
```

**View Logs**:
```bash
tail -f /app/logs/trading.log
```

**Check Docker**:
```bash
docker-compose ps
docker-compose logs -f
```

### Important Notes for Session Continuity

1. **Always Reference**: Phase 2 is complete; start Phase 3 spike detection next
2. **FNO Universe**: Auto-loaded from database, no manual symbol entry needed
3. **Credentials**: Stored in `.env`, loaded on startup, never logged
4. **WebSocket**: Automatically connects on app startup, auto-reconnects on failure
5. **Database**: PostgreSQL with 8 ORM models, auto-creates tables
6. **API Format**: All responses are JSON, endpoints start with `/api/v1/`

### Previous Context Summary

**Message Flow to Reach Here**:
1. User showed trading system flowchart
2. Confirmed AI-powered implementation possible
3. Created 9-phase implementation plan
4. Gathered Upstox credentials (API Key, Secret, Access Token, Client Code: 49CLBQ)
5. Completed Phase 1: Foundation & infrastructure
6. Completed Phase 2: WebSocket integration with V3 API
7. Now ready for Phase 3: Spike detection algorithm

**Key User Preferences**:
- Prefers end-to-end implementation without requiring custom ML training
- Wants production-ready code with proper error handling
- Appreciates comprehensive documentation
- Values clear architecture and extensibility
- Wants runnable demos/verification scripts

---

**Use this document as reference when resuming work to maintain continuity!**
