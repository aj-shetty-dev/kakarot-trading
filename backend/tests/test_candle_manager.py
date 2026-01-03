import pytest
from datetime import datetime, timedelta
from src.trading.candle_manager import CandleManager
from src.websocket.data_models import TickData

class MockTick:
    def __init__(self, symbol, price, volume, timestamp=None):
        self.symbol = symbol
        self.last_price = price
        self.volume = volume
        self.timestamp = timestamp or datetime.now()

def test_candle_aggregation():
    manager = CandleManager()
    symbol = "RELIANCE"
    base_time = datetime(2026, 1, 3, 10, 0, 0)
    
    # Tick 1: 10:00:05
    manager.update_candle(MockTick(symbol, 2500.0, 100, base_time + timedelta(seconds=5)))
    
    # Tick 2: 10:00:30
    manager.update_candle(MockTick(symbol, 2510.0, 250, base_time + timedelta(seconds=30)))
    
    # Tick 3: 10:01:05 (Should close previous candle)
    manager.update_candle(MockTick(symbol, 2505.0, 400, base_time + timedelta(seconds=65)))
    
    df = manager.get_candles(symbol)
    
    assert len(df) >= 1
    # The first candle (10:00) should be closed and in the main storage
    # The second candle (10:01) should be in current_candles
    
    # Check the closed candle (10:00)
    # Note: get_candles returns both closed and current
    # The first row should be the 10:00 candle
    candle_10_00 = df.iloc[0]
    assert candle_10_00['open'] == 2500.0
    assert candle_10_00['high'] == 2510.0
    assert candle_10_00['low'] == 2500.0
    assert candle_10_00['close'] == 2510.0
    assert candle_10_00['volume'] == 150 # 250 - 100

def test_volume_delta_calculation():
    manager = CandleManager()
    symbol = "SBIN"
    base_time = datetime(2026, 1, 3, 10, 0, 0)
    
    # Initial tick
    manager.update_candle(MockTick(symbol, 600.0, 1000, base_time))
    # Volume delta should be 0 for the first tick since we don't have a previous volume
    
    # Second tick in same minute
    manager.update_candle(MockTick(symbol, 601.0, 1200, base_time + timedelta(seconds=10)))
    # Volume delta = 1200 - 1000 = 200
    
    df = manager.get_candles(symbol)
    assert df.iloc[0]['volume'] == 200
