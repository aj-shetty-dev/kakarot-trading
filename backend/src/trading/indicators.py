import pandas as pd
import ta
from typing import Dict
from ..config.settings import settings

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

        # 1. EMA
        df['ema_fast'] = ta.trend.EMAIndicator(close=df['close'], window=settings.ema_fast).ema_indicator()
        df['ema_slow'] = ta.trend.EMAIndicator(close=df['close'], window=settings.ema_slow).ema_indicator()
        
        # 2. RSI
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=settings.rsi_period).rsi()
        
        # 3. Bollinger Bands
        bb = ta.volatility.BollingerBands(close=df['close'], window=settings.bb_period, window_dev=settings.bb_std)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_mid'] = bb.bollinger_mavg()
        
        # 4. VWAP
        # ta library's VWAP requires high, low, close, volume
        vwap = ta.volume.VolumeWeightedAveragePrice(
            high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], window=settings.rsi_period # Using rsi_period as default window
        )
        df['vwap'] = vwap.volume_weighted_average_price()
        
        # 5. Volume Spike
        df['vol_ma'] = ta.trend.SMAIndicator(close=df['volume'], window=settings.volume_ma_period).sma_indicator()
        df['volume_spike'] = df['volume'] > (settings.volume_spike_multiplier * df['vol_ma'])
        
        # 6. ADX (Average Directional Index) - Trend Strength
        adx = ta.trend.ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=settings.adx_period)
        df['adx'] = adx.adx()

        # 7. ATR (Average True Range) - Volatility for SL/TP
        df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=settings.atr_period).average_true_range()
        
        return df
