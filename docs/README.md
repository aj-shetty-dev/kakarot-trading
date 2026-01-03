# Upstox Algorithmic Trading Bot

Intelligent trading system for NSE FNO instruments with AI-powered signal detection and automated order execution.

## Features

- ✅ Real-time WebSocket data from Upstox
- ✅ Spike detection with technical indicators
- ✅ AI-powered noise filtering
- ✅ Automated order management with rate limiting
- ✅ Risk management with stop-loss and trailing stops
- ✅ Paper trading mode for testing
- ✅ PostgreSQL for data persistence
- ✅ Docker deployment ready
- ✅ **AI-Driven Daily Analysis**: Automated post-trade review for strategy optimization

## AI Analysis & Optimization

This project is designed for continuous improvement through AI-driven analysis. After each trading day, the system's logs are analyzed to refine entry/exit logic and risk parameters.

See the [AI Trading Expert & Analysis Guide](AI_TRADING_EXPERT_GUIDE.md) for details on the analysis workflow.

## Trading Parameters

```
Account Size: ₹1,00,000
Risk Per Trade: 5%
Position Size: 30% per trade
Stop Loss: 5%
Take Profit: 4%
Trailing Stop: 2%
Max Concurrent Positions: 3
Daily Loss Limit: 2%
```

## Trading Universe

**All NSE FNO symbols EXCEPT:**
- NIFTY
- BANKNIFTY
- FINANCENIFTY
- NIFTYNEXT50

## Project Structure

```
upstox/
├── backend/
│   ├── src/
│   │   ├── config/           # Configuration and settings
│   │   ├── screening/        # FNO symbol management
│   │   ├── websocket/        # Real-time data connection
│   │   ├── data/             # Database models and operations
│   │   ├── signals/          # Spike detection and validation
│   │   ├── trading/          # Order management
│   │   ├── risk/             # Risk calculations
│   │   ├── monitoring/       # Logging and metrics
│   │   └── main.py           # FastAPI entry point
│   ├── tests/                # Test suite
│   ├── requirements.txt      # Python dependencies
│   ├── Dockerfile            # Docker image
│   └── .env.example          # Environment variables template
├── docker-compose.yml        # Docker services (PostgreSQL, Redis)
└── IMPLEMENTATION_PLAN.md    # Detailed implementation guide
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Upstox API credentials

### Installation

1. **Clone and setup:**
```bash
cd upstox/backend
cp .env.example .env
# Edit .env with your credentials
```

2. **Start services with Docker:**
```bash
docker-compose up -d
```

3. **Initialize database:**
```bash
docker exec upstox_trading_bot python -c "from src.data.database import init_db; init_db()"
```

4. **Visit API docs:**
```
http://localhost:8000/docs
```

## Configuration

All settings are in `.env` file:

```env
# Upstox API
UPSTOX_API_KEY=your_key
UPSTOX_API_SECRET=your_secret
UPSTOX_ACCESS_TOKEN=your_token

# Trading Settings
ACCOUNT_SIZE=100000
RISK_PER_TRADE=0.05
POSITION_SIZE_PERCENT=0.30
```

See `.env.example` for all available options.

## Development

### Running Locally (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Run application
uvicorn src.main:app --reload
```

### Running Tests

```bash
pytest tests/ -v
```

## API Endpoints

- `GET /` - Health check
- `GET /api/v1/symbols` - List tradeable symbols
- `GET /api/v1/signals` - Recent signals
- `GET /api/v1/trades` - Trade history
- `GET /api/v1/positions` - Current positions
- `GET /api/v1/account` - Account information

## Trading Workflow

```
1. Fetch FNO Universe
   ↓
2. Subscribe to WebSocket
   ↓
3. Receive Price Ticks
   ↓
4. Detect Spikes (Technical Analysis)
   ↓
5. Filter Noise (AI Model)
   ↓
6. Validate Signal
   ↓
7. Calculate Position Size
   ↓
8. Submit Order to Upstox
   ↓
9. Monitor Position
   ↓
10. Exit (TP/SL/Trailing)
```

## Risk Management

- Position size capped at 30% of account
- Stop loss at 5% below entry
- Take profit at 4% above entry
- Trailing stop at 2% after hitting TP
- Daily loss limit: 2% of account
- Max 3 concurrent positions

## Monitoring & Logging

Logs are stored in `backend/logs/`:
- `trading.log` - Trading operations
- `signals.log` - Signal detection
- `errors.log` - Error tracking

## Next Steps

1. Implement WebSocket client for real-time data
2. Build spike detection algorithm
3. Integrate AI noise filter
4. Implement order execution
5. Complete risk management
6. Paper trading validation
7. Go live!

## Support

For issues or questions, refer to:
- `IMPLEMENTATION_PLAN.md` - Detailed implementation guide
- `docs/` - API documentation

---

**Status**: 🔧 In Development (Phase 1 complete)

**Last Updated**: 29-Nov-2025
