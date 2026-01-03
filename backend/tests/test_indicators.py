import pytest
import pandas as pd
import numpy as np
from src.trading.indicators import IndicatorCalculator

def test_indicator_calculation():
    # Create a dummy DataFrame with 30 rows (enough for EMA 21 and ADX 14)
    data = {
        'open': np.linspace(100, 130, 30),
        'high': np.linspace(105, 135, 30),
        'low': np.linspace(95, 125, 30),
        'close': np.linspace(102, 132, 30),
        'volume': np.random.randint(1000, 5000, 30)
    }
    df = pd.DataFrame(data)
    df.index = pd.date_range(start='2026-01-03 10:00:00', periods=30, freq='1min')
    
    result_df = IndicatorCalculator.calculate_indicators(df)
    
    # Check if indicators are present
    expected_columns = [
        'ema_fast', 'ema_slow', 'rsi', 'bb_upper', 'bb_lower', 
        'bb_mid', 'vwap', 'vol_ma', 'volume_spike', 'adx', 'atr'
    ]
    for col in expected_columns:
        assert col in result_df.columns
        # The first few rows might be NaN due to windowing
        assert not result_df[col].iloc[-1] == np.nan
        
    # Check specific logic (e.g., volume spike)
    # Force a volume spike in the last row
    df.loc[df.index[-1], 'volume'] = 100000
    df.loc[df.index[-20:-1], 'volume'] = 1000 # Low volume for MA
    
    result_df = IndicatorCalculator.calculate_indicators(df)
    assert result_df['volume_spike'].iloc[-1] == True
