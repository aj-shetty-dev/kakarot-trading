# Upstox Algorithmic Trading Bot

Intelligent trading system for NSE FNO instruments with AI-powered signal detection and automated order execution.

## 🚀 Quick Start

### For Developers (Local Build)
1.  **Configure Credentials**: Update `backend/.env` with your Upstox API Key, Secret, and Access Token.
2.  **Launch System**: Run `./dev.sh` in the project root.
3.  **Access Dashboard**: Open [http://localhost:8501](http://localhost:8501) in your browser.

### For Distribution (Pre-built)
If you are using the version shared in the `dist/` folder:
1.  **Configure Credentials**: Update the `.env` file in the `dist/upstox-trading-bot/` folder.
2.  **Launch System**: Run `./start.sh` inside that folder.
3.  **Access Dashboard**: Open [http://localhost:8501](http://localhost:8501).

## 📁 Project Structure

- `backend/`: Core trading logic, FastAPI services, and WebSocket V3 integration.
- `backend/logs/`: **Centralized logging** for all services (Trading, Signals, Dashboard).
- `scripts/`: Maintenance tools (token refresh, ISIN mapping) and distribution scripts.
- `docs/`: Technical guides, architecture diagrams, and archived phase reports.
- `dist/`: Shareable distribution package pre-configured for Docker Hub.

## 🛠 Key Components

- **Session Manager**: Automated lifecycle management based on IST market hours.
- **WebSocket V3 Client**: High-speed binary data feed with auto-reconnection.
- **Signal Engine**: Real-time spike detection with AI-powered noise filtering.
- **Telegram Bot**: Instant alerts for trades, session changes, and settings updates.

## 📋 Features

- ✅ **Real-time Data**: Native Upstox V3 WebSocket integration.
- ✅ **Smart Filtering**: Technical indicators combined with AI noise reduction.
- ✅ **Risk Management**: Automated SL, TP, and Trailing Stop execution.
- ✅ **Immediate Feedback**: Telegram notifications for manual settings updates.
- ✅ **Dockerized**: Fully containerized environment for consistent deployment.
- ✅ **AI Analysis**: Automated post-trade review for strategy refinement.

## 📊 Trading Parameters

```text
Account Size: ₹1,00,000
Risk Per Trade: 5%
Position Size: 30% per trade
Stop Loss: 5% | Take Profit: 4% | Trailing Stop: 2%
Max Concurrent Positions: 3
Daily Loss Limit: 2%
```

## 🌌 Trading Universe

**All NSE FNO symbols EXCEPT indices:**
- NIFTY, BANKNIFTY, FINANCENIFTY, NIFTYNEXT50.

## 📈 Monitoring & Logs

All logs are stored in `backend/logs/` organized by date:
- **Live Trading**: `tail -f backend/logs/$(date +%Y-%m-%d)/trading.log`
- **Signal Detection**: `tail -f backend/logs/$(date +%Y-%m-%d)/signals.log`

## 📄 Documentation Index

- [Operations Guide](docs/OPERATIONS_GUIDE.md): Daily workflow and troubleshooting.
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md): Steps for production setup.
- [WebSocket Guide](docs/WEBSOCKET_GUIDE.md): Technical details on the V3 feed.
- [ISIN Integration](docs/ISIN_INTEGRATION_GUIDE.md): How instrument mapping works.
- [Archived Reports](docs/archive/): Historical phase reports and test results.

---

**Status**: 🚀 Production Ready
**Last Updated**: January 2026
