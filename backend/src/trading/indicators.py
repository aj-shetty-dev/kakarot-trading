import pandas as pd
import ta
from typing import Dict

class IndicatorCalculator:
    """
    Calculates technical indicators for scalping strategy.
    """
    
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add technical indicators to the DataFrame.
        Expects DataFrame with columns: 'open', 'high', 'low', 'close', 'volume'.
        """
        if df.empty:
            return df
            
        # Ensure columns are numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # 1. EMA (9, 21)
        df['ema_9'] = ta.trend.EMAIndicator(close=df['close'], window=9).ema_indicator()
        df['ema_21'] = ta.trend.EMAIndicator(close=df['close'], window=21).ema_indicator()
        
        # 2. RSI (14)
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        
        # 3. Bollinger Bands (20, 2)
        bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_mid'] = bb.bollinger_mavg()
        
        # 4. VWAP
        # ta library's VWAP requires high, low, close, volume
        vwap = ta.volume.VolumeWeightedAveragePrice(
            high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], window=14
        )
        df['vwap'] = vwap.volume_weighted_average_price()
        
        # 5. Volume Spike (Volume > 2 * SMA(20) of Volume)
        # Using SMA for average volume
        df['vol_ma_20'] = ta.trend.SMAIndicator(close=df['volume'], window=20).sma_indicator()
        df['volume_spike'] = df['volume'] > (2 * df['vol_ma_20'])
        
        # 6. ADX (Average Directional Index) - Trend Strength
        adx = ta.trend.ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
        df['adx'] = adx.adx()
        
        return df
