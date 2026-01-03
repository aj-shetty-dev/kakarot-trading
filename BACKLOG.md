# Scalping Bot Implementation Backlog

## Phase 1: Infrastructure & Data (Current Focus)
- [ ] **Dependency Update**: Add `pandas_ta` to `requirements.txt` and rebuild Docker containers.
- [ ] **Candle Aggregation**: Implement a `CandleManager` to convert real-time ticks into 1-minute OHLCV bars. `pandas_ta` requires candle data, not just raw ticks.
- [ ] **Data Persistence**: Ensure candles are stored/cached efficiently for indicator calculation (need at least 200 bars for some indicators).

## Phase 2: Technical Indicators
- [ ] **Indicator Service**: Create `src/signals/indicators.py` to wrap `pandas_ta` calls.
    - [ ] EMA (9, 21, 50, 200)
    - [ ] RSI (14)
    - [ ] VWAP
    - [ ] Bollinger Bands (20, 2)
    - [ ] Volume Moving Average

## Phase 3: Strategy Implementation
- [ ] **Strategy Interface**: Define a common interface for strategies.
- [ ] **Momentum Strategy**: Implement EMA Crossover + RSI logic.
- [ ] **Mean Reversion Strategy**: Implement VWAP + Bollinger Band logic.
- [ ] **Breakout Strategy**: Implement Support/Resistance + Volume Spike logic.
- [ ] **Signal Service Update**: Integrate these strategies into the main `SignalService` loop.

## Phase 4: Risk Management & Execution
- [ ] **ATR Calculation**: Add ATR indicator for dynamic stops.
- [ ] **Dynamic Risk Manager**: Update `RiskManager` to accept dynamic SL/TP prices from the strategy.
- [ ] **Execution Logic**: Ensure `TradingService` respects the specific order parameters (Limit vs Market) if strategies dictate them.

## Phase 5: Testing & Tuning
- [ ] **Paper Trading Verification**: Run in paper mode and verify signals against chart data.
- [ ] **Parameter Tuning**: Move strategy parameters (periods, thresholds) to `config.json`.
