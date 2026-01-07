# Project Context & Session Continuity (Updated: Jan 3, 2026)

## 🚀 Project Overview
- **Name**: Upstox Algorithmic Trading Bot
- **Objective**: Automated FNO scalping with AI-powered noise filtering and dynamic risk management.
- **Stack**: Python 3.11, FastAPI, SQLAlchemy (PostgreSQL), Redis, Streamlit, Docker.
- **Market Hours**: 09:15 - 15:30 IST (Auto-managed by `MarketSessionManager`).

## 🛠️ Current Architecture & State

### 1. Core Services (All ACTIVE)
- **Trading Engine (`TradingService`)**: Handles order execution, position tracking, and square-offs.
- **WebSocket V3 (`UpstoxWebSocketClient`)**: Real-time binary protobuf feed from Upstox V3 API.
- **Risk Manager (`RiskManager`)**: Implements **ATR-based dynamic SL/TP** and account-level risk limits.
- **ML Pipeline (`MLDataPipeline`)**: Logs 25+ features per signal to PostgreSQL for future AI training.
- **Session Manager (`MarketSessionManager`)**: Automates daily startup/shutdown and token health checks.

### 2. Recent Major Implementations (Phase 5 & 6)
- **ATR Risk Management**: Stop-loss and Take-profit are now calculated dynamically based on 14-period ATR (1.5x for SL, 2.0x for TP).
- **ML Feature Logging**: Every signal now captures technical context (RSI, ADX, Bollinger Bands, Volume Multipliers) into the `ml_feature_logs` table.
- **Robustness Audit Fixes**:
    - **DB Schema**: Fixed `tick_id` nullability issue in `signals` table that caused missed trades.
    - **Resilience**: Added `pool_pre_ping` to SQLAlchemy and 3-attempt retry logic with exponential backoff to `OptionsLoader`.
    - **Health Monitoring**: Enhanced `/health` endpoint and added `TelegramAlertHandler` for `CRITICAL` errors.

### 3. Operational Flow (Monday Morning Routine)
- **Token Management**: Upstox tokens expire daily.
- **One-Click Update**: Use the **Dashboard (Port 8501) -> Settings Tab**.
    - Paste the new **Access Token** directly.
    - The bot automatically: Saves to `config.json` -> Restarts WebSocket -> Refreshes Options -> Verifies Connection -> Notifies Telegram.
- **Telegram Bot**: All major events (Session Start, Trades, Errors, EOD Reports) are sent to the configured Telegram channel.

## 📊 Database Schema Highlights
- **`signals`**: Stores all detected opportunities. `tick_id` is now NULLABLE to support manual/simulated signals.
- **`trades`**: Tracks execution, PnL, and exit reasons.
- **`ml_feature_logs`**: Stores high-dimensional data for AI training (Target: 100+ samples before training Phase 6 model).
- **`trading_sessions`**: Logs daily bot activity.

## 🧪 Testing & Quality
- **Test Suite**: 23 automated tests covering Risk, API, ML, and Integration.
- **Execution**: Always run via Docker: `docker exec -it upstox_trading_bot env PYTHONPATH=/app pytest tests/`.
- **Status**: All tests PASSING as of Jan 3, 2026.

## 📝 Backlog & Next Steps
1. **Phase 6 (AI Integration)**: Train the Market Regime Classifier once 100 labeled samples are collected in `ml_feature_logs`.
2. **Performance Optimization**: Implement Redis-based caching for historical candle data to speed up indicator calculation.
3. **Dashboard Expansion**: Add a "Trade Review" tab to manually label ML samples if needed.

## 🔑 Environment & Ports
- **API**: `http://localhost:8000`
- **Dashboard**: `http://localhost:8501`
- **Postgres**: `localhost:5432` (User: `upstox_user`, DB: `upstox_trading`)
- **Config**: `backend/config.json` (Primary source of truth for runtime settings).

---
**Note for Future AI Sessions**: Always check `backend/config.json` for the current active token and `backend/logs/` for today's trading activity.
