import pytest
import pandas as pd
import numpy as np
from src.trading.strategy import ScalpingStrategy
from src.config.settings import Settings

def test_strategy_buy_signal():
    # Create a DataFrame that satisfies BUY conditions
    # EMA Cross Up, Price > VWAP, RSI bullish, Vol Spike, Not overextended
    
    periods = 30
    df = pd.DataFrame({
        'ema_fast': np.linspace(10, 20, periods),
        'ema_slow': np.linspace(11, 19, periods), # Fast crosses slow at the end
        'rsi': [50] * periods,
        'vwap': [10] * periods,
        'close': [25] * periods,
        'volume_spike': [True] * periods,
        'adx': [30] * periods,
        'bb_upper': [100] * periods,
        'bb_lower': [0] * periods,
        'atr': [1.0] * periods
    })
    df.index = pd.date_range(start='2026-01-03 10:00:00', periods=periods, freq='1min')
    
    # Ensure EMA crossover: prev fast <= prev slow, curr fast > curr slow
    # Row -2: fast=18.96, slow=18.72 (Wait, linspace might not be perfect)
    # Let's set them manually for the last two rows
    df.loc[df.index[-2], 'ema_fast'] = 15.0
    df.loc[df.index[-2], 'ema_slow'] = 15.5
    df.loc[df.index[-1], 'ema_fast'] = 16.0
    df.loc[df.index[-1], 'ema_slow'] = 15.5
    
    signal = ScalpingStrategy.check_signal(df)
    
    assert signal is not None
    assert signal['side'] == 'BUY'
    assert 'EMA Cross Up' in signal['reason']

def test_strategy_no_signal_low_adx():
    periods = 30
    df = pd.DataFrame({
        'ema_fast': np.linspace(15, 16, periods),
        'ema_slow': np.linspace(15, 15.5, periods),
        'rsi': [50] * periods,
        'vwap': [10] * periods,
        'close': [25] * periods,
        'volume_spike': [True] * periods,
        'adx': [10] * periods, # Low ADX
        'bb_upper': [100] * periods,
        'bb_lower': [0] * periods,
        'atr': [1.0] * periods
    })
    df.index = pd.date_range(start='2026-01-03 10:00:00', periods=periods, freq='1min')
    
    signal = ScalpingStrategy.check_signal(df)
    assert signal is None
