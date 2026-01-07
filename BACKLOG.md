# Scalping Bot Implementation Backlog

## Phase 1: Infrastructure & Data (Current Focus)
- [x] **Dependency Update**: Add `pandas_ta` to `requirements.txt` and rebuild Docker containers.
- [x] **Candle Aggregation**: Implement a `CandleManager` to convert real-time ticks into 1-minute OHLCV bars. `pandas_ta` requires candle data, not just raw ticks.
- [x] **Data Persistence**: Ensure candles are stored/cached efficiently for indicator calculation (need at least 200 bars for some indicators).

## Phase 2: Technical Indicators
- [x] **Indicator Service**: Create `src/signals/indicators.py` to wrap `pandas_ta` calls.
    - [x] EMA (9, 21, 50, 200)
    - [x] RSI (14)
    - [x] VWAP
    - [x] Bollinger Bands (20, 2)
    - [x] Volume Moving Average

## Phase 3: Strategy Implementation
- [x] **Strategy Interface**: Define a common interface for strategies.
- [x] **Momentum Strategy**: Implement EMA Crossover + RSI logic.
- [x] **Mean Reversion Strategy**: Implement VWAP + Bollinger Band logic.
- [x] **Breakout Strategy**: Implement Support/Resistance + Volume Spike logic.
- [x] **Signal Service Update**: Integrate these strategies into the main `SignalService` loop.

## Phase 4: Risk Management & Execution
- [x] **ATR Calculation**: Add ATR indicator for dynamic stops.
- [x] **Dynamic Risk Manager**: Update `RiskManager` to accept dynamic SL/TP prices from the strategy.
- [ ] **Execution Logic**: Ensure `TradingService` respects the specific order parameters (Limit vs Market) if strategies dictate them.

## Phase 5: Testing & Tuning
- [ ] **Paper Trading Verification**: Run in paper mode and verify signals against chart data.
- [x] **Parameter Tuning**: Move strategy parameters (periods, thresholds) to `config.json`.

## Phase 6: AI & Machine Learning Integration
- [x] **ML Data Pipeline**: Implement a data collector to log features (indicators, price action) and labels (trade outcome) for model training.
- [ ] **Signal Validation Agent**: Train a local classifier (XGBoost/Scikit-learn) to filter out low-probability signals.
- [ ] **Market Regime Classifier**: Develop a model to identify market states (Trending, Ranging, Volatile) and switch strategies dynamically.
- [ ] **Dynamic Risk/Position Sizing**: Implement an AI agent to adjust capital allocation based on signal confidence scores.
- [ ] **Local Inference Engine**: Integrate models into the `SignalService` for real-time, low-latency decision making.
