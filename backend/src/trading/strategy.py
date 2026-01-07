import pandas as pd
import logging
from typing import Optional, Dict
from ..config.settings import settings

logger = logging.getLogger(__name__)

class ScalpingStrategy:
    """
    Scalping strategy using EMA, RSI, VWAP, Bollinger Bands, and Volume Spikes.
    """
    
    @staticmethod
    def check_signal(df: pd.DataFrame) -> Optional[Dict]:
        """
        Analyze the DataFrame and return a signal if conditions are met.
        Returns: {'side': 'BUY'|'SELL', 'reason': str} or None
        """
        if len(df) < settings.ema_slow + 1: # Need enough data
            return None
            
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Indicators
        ema_fast = curr['ema_fast']
        ema_slow = curr['ema_slow']
        ema_trend = curr['ema_trend']
        prev_ema_fast = prev['ema_fast']
        prev_ema_slow = prev['ema_slow']
        
        rsi = curr['rsi']
        vwap = curr['vwap']
        close = curr['close']
        volume_spike = curr['volume_spike']
        adx = curr['adx']
        bb_upper = curr['bb_upper']
        bb_lower = curr['bb_lower']
        atr = curr['atr']
        
        # Logic
        
        # Common Filters
        # 1. ADX > threshold (Ensure trend strength, avoid chop)
        # Increased from 20 to 25 for higher quality signals
        strong_trend = adx > 25.0
        
        if not strong_trend:
            if settings.debug:
                logger.debug(f"Signal rejected for {df.index[-1]}: ADX {adx:.2f} < 25.0")
            return None

        # 2. ATR Filter: Ensure volatility is high enough to cover brokerage
        # If ATR is too low, the price move might be smaller than the ₹40 round-trip cost
        if atr < (close * 0.002): # Minimum 0.2% volatility
            if settings.debug:
                logger.debug(f"Signal rejected for {df.index[-1]}: ATR {atr:.2f} too low")
            return None

        # BUY SIGNAL
        # 1. Trend Filter: Price must be above long-term EMA
        above_trend = close > ema_trend
        
        # 2. EMA Crossover: fast crosses above slow
        ema_crossover_up = (prev_ema_fast <= prev_ema_slow) and (ema_fast > ema_slow)
        
        # 3. Price above VWAP (Bullish trend)
        above_vwap = close > vwap
        
        # 4. RSI in "Sweet Spot" (Momentum)
        # Narrowed from 30-70 to 50-65 for higher probability buy
        rsi_bullish = 50 < rsi < 65
        
        # 5. Not overextended (Price < Upper BB)
        not_overextended_buy = close < bb_upper
        
        # 6. Stricter Volume Spike (3x instead of 2x)
        volume_ma = df['volume'].rolling(window=20).mean().iloc[-1]
        significant_volume = curr['volume'] > (volume_ma * 3.0)
        
        if above_trend and ema_crossover_up and above_vwap and rsi_bullish and significant_volume and not_overextended_buy:
            return {
                'side': 'BUY',
                'reason': f"High-Quality BUY: Trend+, EMA Cross, VWAP+, RSI {rsi:.2f}, Vol 3x",
                'atr': atr
            }
            
        # SELL SIGNAL
        # 1. Trend Filter: Price must be below long-term EMA
        below_trend = close < ema_trend
        
        # 2. EMA Crossover: fast crosses below slow
        ema_crossover_down = (prev_ema_fast >= prev_ema_slow) and (ema_fast < ema_slow)
        
        # 3. Price below VWAP (Bearish trend)
        below_vwap = close < vwap
        
        # 4. RSI in "Sweet Spot" (Momentum)
        # Narrowed from 30-70 to 35-50 for higher probability sell
        rsi_bearish = 35 < rsi < 50
        
        # 5. Not overextended (Price > Lower BB)
        not_overextended_sell = close > bb_lower
        
        if below_trend and ema_crossover_down and below_vwap and rsi_bearish and significant_volume and not_overextended_sell:
            return {
                'side': 'SELL',
                'reason': f"High-Quality SELL: Trend-, EMA Cross, VWAP-, RSI {rsi:.2f}, Vol 3x",
                'atr': atr
            }
            
        return None
