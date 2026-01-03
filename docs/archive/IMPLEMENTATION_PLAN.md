# Upstox Algorithmic Trading System - Implementation Plan

## Overview
Build an end-to-end algorithmic trading system that detects market spikes, filters noise using AI, validates signals, and executes trades via Upstox API with rate limiting and risk management.

---

## Phase 1: Foundation & Setup (Days 1-2)

### 1.1 Project Structure
```
upstox-trading-bot/
├── backend/
│   ├── src/
│   │   ├── config/
│   │   │   ├── constants.py
│   │   │   ├── settings.py
│   │   │   └── logging.py
│   │   ├── screening/
│   │   │   ├── symbol_screener.py (Fetch all FNO symbols)
│   │   │   ├── fno_universe.py (Manage FNO watchlist)
│   │   │   └── symbol_filter.py (Filter excluded symbols)
│   │   ├── websocket/
│   │   │   ├── client.py (Upstox WebSocket connection)
│   │   │   └── handlers.py (Message parsing)
│   │   ├── data/
│   │   │   ├── models.py (Data structures)
│   │   │   └── storage.py (DB operations)
│   │   ├── signals/
│   │   │   ├── spike_detector.py
│   │   │   ├── noise_filter.py
│   │   │   └── validators.py
│   │   ├── trading/
│   │   │   ├── order_manager.py
│   │   │   ├── rate_limiter.py
│   │   │   └── upstox_api.py
│   │   ├── risk/
│   │   │   ├── position_manager.py
│   │   │   └── risk_calculator.py
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── docker-compose.yml
├── frontend/
│   ├── dashboard/ (Optional - Streamlit/FastAPI endpoint)
├── docs/
│   ├── API_REFERENCE.md
│   └── TRADING_RULES.md
├── data/
│   ├── models/ (Pre-trained AI models)
│   └── symbol_lists/
│       └── fno_universe.json (All FNO symbols)
└── README.md
```

### 1.2 Technology Stack Selection

**Backend Framework**: FastAPI (Python)
- ✅ Async support for WebSocket
- ✅ Easy API development
- ✅ Built-in async/await

**Database**: PostgreSQL
- ✅ Structured trading data
- ✅ Time-series capabilities
- ✅ JSONB for flexible signal data

**AI/ML**: 
- Scikit-learn (anomaly detection - lightweight)
- HuggingFace (pre-trained models for classification)
- Optionally: OpenAI API (for advanced signal validation)

**WebSocket**: `websockets` + `aiohttp`

**Task Queue**: Celery + Redis (for async order processing)

**Monitoring**: Prometheus + Grafana (optional, for production)

### 1.3 Initial Setup Tasks
- [ ] Create GitHub repo
- [ ] Set up Python venv with Python 3.10+
- [ ] Install core dependencies: FastAPI, asyncio, websockets, sqlalchemy, psycopg2
- [ ] Create PostgreSQL database locally
- [ ] Set up environment configuration (.env file)
- [ ] Create basic logging system
- [ ] Set up docker-compose for local development

**Deliverable**: Repo structure + local dev environment ready

---

## Phase 1.5: FNO Symbol Screening (Day 2-3)

### 1.5.1 FNO Universe Definition
**File**: `backend/src/screening/fno_universe.py`

**Trading Universe**:
```
All NSE FNO Symbols EXCEPT:
- NIFTY
- BANKNIFTY
- FINANCENIFTY
- NIFTYNEXT50
```

**Symbols Included**: ~150-200 actively traded stocks with futures & options

**Tasks**:
- [ ] Fetch complete NSE FNO symbol list from Upstox API
- [ ] Filter out excluded symbols (NIFTY, BANKNIFTY, FINANCENIFTY, NIFTYNEXT50)
- [ ] Store filtered list in database
- [ ] Implement daily refresh (market close)
- [ ] Validate all symbols have active options contracts

### 1.5.2 Symbol Data Structure
**File**: `backend/src/data/models.py`

```python
class Symbol:
    symbol: str  # e.g., "INFY"
    name: str  # Full name
    sector: str
    is_fno: bool = True
    has_options: bool = True
    has_futures: bool = True
    status: Enum  # ACTIVE, INACTIVE, SUSPENDED
    last_updated: datetime
    
    # Metadata
    oi_shares: int  # Open Interest
    avg_daily_volume: int
    liquidity_score: float  # 0-1
```

**Database Table**:
- [ ] `symbols` - Master symbol list with metadata
- [ ] `symbol_update_log` - Track symbol changes

### 1.5.3 WebSocket Subscription Manager
**File**: `backend/src/websocket/subscription_manager.py`

**Responsibilities**:
```python
class SubscriptionManager:
    def __init__(self):
        - Load FNO universe
        - Filter out excluded symbols
    
    def get_active_symbols(self) → List[str]:
        - Return current trading universe
    
    def subscribe_to_all(self, websocket: WebSocket):
        - Subscribe to all FNO symbols (except excluded)
        - Handle subscription limits (Upstox may have limits)
        - Batch subscriptions if needed
    
    def update_universe(self):
        - Refresh symbol list daily
        - Add new FNO listings
        - Remove delisted symbols
```

**Key Points**:
- Upstox WebSocket may have **subscription limits** (e.g., max 50 symbols per connection)
- If so, use **multiple WebSocket connections** or **rotating subscriptions**
- Store subscription state in Redis for resilience

### 1.5.4 Excluded Symbols Configuration
**File**: `backend/src/config/constants.py`

```python
EXCLUDED_SYMBOLS = {
    "NIFTY",
    "BANKNIFTY", 
    "FINANCENIFTY",
    "NIFTYNEXT50"
}

# Why exclude?
# - Index contracts (different behavior from stock options)
# - High volatility + large moves
# - Might be handled separately with different strategies
```

**Deliverable**: FNO symbol universe loaded, WebSocket subscribed to all tradeable symbols

---

## Phase 2: Data Pipeline (Days 4-5)

### 2.1 Upstox WebSocket Integration
**File**: `backend/src/websocket/client.py`

**Tasks**:
- [ ] Authenticate with Upstox API (API key/token)
- [ ] Establish WebSocket connection to V3 feed
- [ ] Handle connection lifecycle (connect, reconnect, disconnect)
- [ ] Implement message parsing for price/volume data
- [ ] Structure incoming data (OHLCV format)

**Key Functions**:
```python
- async def connect_websocket() → WebSocket connection
- async def handle_message(msg) → Parse tick data
- async def parse_greeks(msg) → Extract options data
- async def emit_tick(symbol, price, volume, timestamp)
```

### 2.2 Data Models & Storage
**File**: `backend/src/data/models.py` + `storage.py`

**Data Structures**:
```python
class Tick:
    symbol: str
    price: float
    volume: int
    bid: float
    ask: float
    timestamp: datetime
    iv: float  # Implied Volatility
    greeks: Dict  # delta, gamma, theta, vega

class Signal:
    id: UUID
    symbol: str
    signal_type: Enum  # SPIKE, REVERSAL, etc.
    strength: float  # 0-1 confidence
    timestamp: datetime
    raw_data: Tick
    is_noise: bool
    validation_status: Enum

class Trade:
    id: UUID
    symbol: str
    order_type: Enum  # BUY, SELL
    quantity: int
    entry_price: float
    status: Enum  # PENDING, EXECUTED, FAILED
    timestamp: datetime
    signal_id: UUID
```

**Database Tables**:
- [ ] `ticks` (time-series price data)
- [ ] `signals` (detected signals with metadata)
- [ ] `trades` (executed orders)
- [ ] `positions` (current holdings)
- [ ] `rate_limit_log` (tracking API calls)

### 2.3 Greeks Calculation
**File**: `backend/src/data/greeks_calculator.py`

**Tasks**:
- [ ] Parse Greeks from Upstox feed (if available)
- [ ] OR calculate Greeks using Black-Scholes model
- [ ] Store Greeks for options analysis
- [ ] Create functions for delta, gamma, theta, vega retrieval

**Deliverable**: Live data flowing into database, WebSocket connected and stable

---

## Phase 3: Signal Detection (Days 5-6)

### 3.1 Spike Detection Logic
**File**: `backend/src/signals/spike_detector.py`

**Algorithm**:
1. **Moving Average Analysis**
   - Calculate 20-period and 50-period MA
   - Detect when price > MA + (std_dev × 2)

2. **Volume Spike Detection**
   - Compare current volume to 20-period average
   - Flag if volume > avg_volume × 2.5

3. **Price Momentum**
   - Calculate ROC (Rate of Change)
   - Flag if ROC > threshold

4. **IV (Implied Volatility) Spike** (for options)
   - Track IV changes > 20% in short timeframe

**Key Functions**:
```python
- detect_price_spike(ticks: List[Tick]) → Signal
- detect_volume_spike(ticks: List[Tick]) → Signal
- detect_momentum_shift(ticks: List[Tick]) → Signal
- combine_signals(signals: List[Signal]) → Signal (aggregate)
```

### 3.2 Raw Data Processing
**File**: `backend/src/data/preprocessing.py`

**Tasks**:
- [ ] Normalize price data
- [ ] Handle missing data points
- [ ] Calculate technical indicators (RSI, MACD, Bollinger Bands)
- [ ] Create rolling windows for analysis
- [ ] Store processed data for ML models

**Deliverable**: Spike detection engine working on live data

---

## Phase 4: AI Noise Filter (Days 7-9)

### 4.1 Anomaly Detection Model
**File**: `backend/src/signals/noise_filter.py`

**Approach 1: Statistical (Lightweight)**
```python
- Isolation Forest for outlier detection
- Local Outlier Factor (LOF)
- DBSCAN clustering
```

**Approach 2: Pre-trained ML (Recommended)**
```python
- HuggingFace Time Series Classification
- Or: Train on historical market data (outside scope for now)
```

**Approach 3: Hybrid (Best)**
- Combine statistical + ML confidence scores
- Weighted voting system

**Implementation**:
```python
class NoiseFilter:
    def __init__(self):
        - Load pre-trained model (or sklearn)
        - Initialize statistical thresholds
    
    def filter(self, signal: Signal) → float (0-1 confidence):
        - Extract features from signal
        - Run through anomaly detector
        - Calculate noise probability
        - Return validation score
```

### 4.2 Feature Engineering
**File**: `backend/src/signals/feature_extractor.py`

**Features to Extract**:
- Price momentum (ROC, MACD)
- Volume profile
- Volatility (ATR, Bollinger Band width)
- Trend strength (ADX)
- Support/Resistance levels
- Market microstructure (bid-ask spread)
- Time-of-day factor
- Market regime (trending vs. ranging)

**Dataset Creation**:
- [ ] Backtest on 6-12 months historical data
- [ ] Label signals as TRUE_POSITIVE or FALSE_POSITIVE
- [ ] Create training dataset
- [ ] Train noise classifier

### 4.3 Signal Validation
**File**: `backend/src/signals/validators.py`

**Validation Rules**:
```python
- Minimum signal strength threshold (> 0.6)
- Volume confirmation (volume > avg × 1.5)
- Trend confirmation (price in direction of trend)
- Multiple timeframe confirmation (1m + 5m aligned)
- No conflicting signals in same instrument
- Market hours only (9:15 AM - 3:30 PM IST for NSE)
- Liquidity check (bid-ask spread < threshold)
```

**Deliverable**: AI noise filter reducing false signals by 70%+

---

## Phase 5: Order Management & Execution (Days 10-12)

### 5.1 Rate Limiting System
**File**: `backend/src/trading/rate_limiter.py`

**Rules**:
```python
- Max X orders per minute per symbol
- Max Y orders per hour overall
- Max Z concurrent positions
- Min time between orders for same symbol
- Daily order quota
```

**Implementation**:
```python
class RateLimiter:
    def __init__(self):
        - Redis for distributed rate tracking
    
    def can_execute_order(self, symbol, order_type) → bool:
        - Check all rate limit rules
        - Return True/False
    
    def queue_order(self, order) → UUID:
        - If limit exceeded, queue order
        - Return order ID for later execution
```

### 5.2 Order Manager
**File**: `backend/src/trading/order_manager.py`

**Responsibilities**:
```python
class OrderManager:
    def create_order(self, signal: Signal) → Order:
        - Calculate position size (based on risk)
        - Set stop-loss and take-profit
        - Create order object
    
    def validate_order(self, order: Order) → bool:
        - Check liquidity
        - Check account balance
        - Check risk limits
        - Check market hours
    
    def submit_order(self, order: Order) → OrderResult:
        - Call Upstox API
        - Log execution
        - Update DB
    
    def manage_positions(self):
        - Track open positions
        - Check stop-losses
        - Check take-profits
        - Close expired positions
```

### 5.3 Upstox API Integration
**File**: `backend/src/trading/upstox_api.py`

**Tasks**:
- [ ] Implement Upstox REST API client
- [ ] Place orders (MARKET, LIMIT, STOP-LOSS)
- [ ] Fetch account balance
- [ ] Get position details
- [ ] Handle order status updates
- [ ] Implement error handling & retries

**Key Functions**:
```python
- place_market_order(symbol, quantity, side) → OrderID
- place_limit_order(symbol, quantity, price, side) → OrderID
- get_account_balance() → float
- get_positions() → List[Position]
- cancel_order(order_id) → bool
- update_order_status(order_id) → OrderStatus
```

### 5.4 Risk Management
**File**: `backend/src/risk/risk_calculator.py`

**Risk Rules**:
```python
- Max position size: 5% of account per trade
- Max daily loss: 2% of account
- Max concurrent positions: 3
- Max portfolio leverage: 1.5x
- Stop-loss: Always 2% below entry
- Take-profit: Always 4% above entry
```

**Deliverable**: Orders executing successfully with rate limiting

---

## Phase 6: Monitoring & Logging (Days 13-14)

### 6.1 Logging System
**File**: `backend/src/config/logging.py`

**Log Events**:
- WebSocket connections/disconnections
- Signals detected
- Noise filter results
- Order submissions
- Trade executions
- Errors and exceptions
- API rate limit status

**Implementation**:
- [ ] Structured logging with JSON format
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR
- [ ] Separate log files for trading, signals, errors
- [ ] Log rotation

### 6.2 Metrics & Dashboard
**File**: `backend/src/monitoring/metrics.py`

**Metrics to Track**:
- Signals detected per hour/day
- Noise filter accuracy
- Win rate
- Average trade duration
- Daily P&L
- Sharpe ratio
- Max drawdown
- API response times

**Dashboard** (Optional - Streamlit):
- [ ] Real-time signal visualization
- [ ] Trade history
- [ ] Performance metrics
- [ ] Position overview
- [ ] Alert system

### 6.3 Alerting System
**File**: `backend/src/monitoring/alerts.py`

**Alerts**:
- Large losses (> 1% daily)
- Consecutive losing trades
- API connection issues
- Rate limit exceeded
- Unusual order rejections

**Channels**: Email, Slack, webhook

**Deliverable**: Full observability and monitoring

---

## Phase 7: Testing & Backtesting (Days 15-17)

### 7.1 Unit Tests
**File**: `backend/tests/`

**Test Coverage**:
- [ ] Spike detection algorithm
- [ ] Noise filter accuracy
- [ ] Signal validation rules
- [ ] Rate limiter logic
- [ ] Order manager functions
- [ ] Risk calculations

### 7.2 Integration Tests
- [ ] End-to-end signal → order flow
- [ ] WebSocket connection handling
- [ ] Database operations
- [ ] Upstox API integration

### 7.3 Backtesting Framework
**File**: `backend/src/backtesting/engine.py`

**Functionality**:
```python
class Backtester:
    def run(self, symbol, start_date, end_date):
        - Load historical data
        - Replay signals
        - Execute orders (simulated)
        - Track P&L
        - Calculate metrics
        - Generate report
```

**Metrics Calculated**:
- Total return
- Win rate
- Sharpe ratio
- Max drawdown
- Profit factor
- Average trade duration

**Deliverable**: Backtest results with > 50% win rate minimum

---

## Phase 8: Deployment & Go-Live (Days 18-19)

### 8.1 Docker Setup
- [ ] Create Dockerfile for FastAPI app
- [ ] Create docker-compose with PostgreSQL, Redis
- [ ] Test local containerized deployment

### 8.2 Environment Configuration
- [ ] Production .env file
- [ ] API rate limits adjusted for live trading
- [ ] Risk limits in place
- [ ] Monitoring configured

### 8.3 Pre-Launch Checklist
- [ ] All tests passing
- [ ] Logging working
- [ ] Alerts configured
- [ ] Paper trading successful
- [ ] Risk limits verified
- [ ] Emergency stop procedures in place

### 8.4 Paper Trading (2-3 days)
- [ ] Run system for 2-3 days in paper trading mode
- [ ] Monitor signal quality
- [ ] Verify order execution
- [ ] Check risk management

### 8.5 Live Trading (Gradual Rollout)
- [ ] Start with 1 symbol
- [ ] Small position sizes (0.5% account)
- [ ] Monitor closely for 1 week
- [ ] Scale to 2-3 symbols
- [ ] Increase position sizes gradually

**Deliverable**: System running live with real trades

---

## Phase 9: Optimization & Refinement (Ongoing)

### 9.1 Performance Tuning
- [ ] Analyze trade results weekly
- [ ] Adjust spike detection thresholds
- [ ] Retrain noise filter if needed
- [ ] Optimize rate limiting
- [ ] Review risk settings

### 9.2 Model Improvement
- [ ] Collect more training data
- [ ] Experiment with different ML models
- [ ] Test new features
- [ ] A/B test signal validation rules

### 9.3 Scaling
- [ ] Add more symbols
- [ ] Add more trading strategies
- [ ] Multi-timeframe analysis
- [ ] Options trading logic

---

## Technology Stack Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend Framework | FastAPI | REST API + WebSocket |
| Language | Python 3.10+ | Development |
| Database | PostgreSQL | Time-series data storage |
| Cache/Queue | Redis + Celery | Order queuing, rate limiting |
| WebSocket | `websockets` | Real-time Upstox feed |
| ML/AI | Scikit-learn + HuggingFace | Anomaly detection, noise filtering |
| API Client | `aiohttp` + custom | Upstox API calls |
| Logging | Python logging + ELK | Structured logging |
| Monitoring | Prometheus + Grafana | Metrics (optional) |
| Testing | pytest | Unit/integration tests |
| Containerization | Docker | Deployment |

---

## Key Configuration Parameters

```python
# Signal Detection
SPIKE_THRESHOLD = 2.0  # Standard deviations
VOLUME_MULTIPLIER = 2.5  # Times average volume
ROC_THRESHOLD = 2.0  # Percent change

# Noise Filter
MIN_SIGNAL_STRENGTH = 0.6  # 0-1 confidence
FALSE_POSITIVE_THRESHOLD = 0.7

# Rate Limiting
MAX_ORDERS_PER_MINUTE = 10
MAX_CONCURRENT_POSITIONS = 3
MIN_ORDER_GAP_SECONDS = 30

# Risk Management
MAX_POSITION_SIZE = 0.05  # 5% of account
MAX_DAILY_LOSS = 0.02  # 2% of account
STOP_LOSS_PERCENT = 0.02  # 2%
TAKE_PROFIT_PERCENT = 0.04  # 4%

# Trading Hours (IST - Indian Standard Time)
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
```

---

## Success Criteria

- ✅ Signal detection: 80%+ accuracy
- ✅ Noise filter: 70%+ false positive reduction
- ✅ Backtest win rate: > 50%
- ✅ Order execution: < 500ms latency
- ✅ System uptime: 99.5%
- ✅ Paper trading: Positive P&L for 1 week
- ✅ Live trading: Profitable within first month

---

## Timeline Summary

| Phase | Duration | Status |
|-------|----------|--------|
| 1. Foundation & Setup | 2 days | 📋 Planning |
| 1.5. FNO Symbol Screening | 1 day | 🔄 Queue |
| 2. Data Pipeline | 2 days | 🔄 Queue |
| 3. Signal Detection | 2 days | 🔄 Queue |
| 4. AI Noise Filter | 3 days | 🔄 Queue |
| 5. Order Management | 3 days | 🔄 Queue |
| 6. Monitoring | 2 days | 🔄 Queue |
| 7. Testing | 3 days | 🔄 Queue |
| 8. Deployment | 2 days | 🔄 Queue |
| 9. Optimization | Ongoing | 🔄 Queue |
| **Total** | **~21 days** | |

---

## Next Steps

1. **Confirm Technology Stack**: Approve FastAPI, PostgreSQL, Python choices
2. **API Keys**: Get Upstox API credentials ready
3. **Historical Data**: Gather 12+ months of historical data for backtesting
4. **Market Rules**: Define specific trading rules (symbols, hours, position sizes)
5. **Start Phase 1**: Begin project setup

---

## Questions to Resolve

- [ ] Which symbols to trade? (Stocks, indices, options?)
- [ ] Trading timeframe? (1-min, 5-min, 15-min spikes?)
- [ ] Initial account size? (For position sizing calculations)
- [ ] Risk tolerance? (Max daily loss, max drawdown)
- [ ] Paper trading duration? (Before live trading)
- [ ] Cloud vs. local deployment?
- [ ] Need UI dashboard?

---

**Ready to begin Phase 1?** Let me know and I'll start scaffolding the project! 🚀
