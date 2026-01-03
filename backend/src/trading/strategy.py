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
        strong_trend = adx > settings.adx_threshold
        
        if not strong_trend:
            if settings.debug:
                logger.debug(f"Signal rejected for {df.index[-1]}: ADX {adx:.2f} < {settings.adx_threshold}")
            return None

        # BUY SIGNAL
        # 1. EMA Crossover: fast crosses above slow
        ema_crossover_up = (prev_ema_fast <= prev_ema_slow) and (ema_fast > ema_slow)
        
        # 2. Price above VWAP (Bullish trend)
        above_vwap = close > vwap
        
        # 3. RSI not overbought (Room to grow)
        rsi_bullish = settings.rsi_oversold + 10 < rsi < settings.rsi_overbought
        
        # 4. Not overextended (Price < Upper BB)
        not_overextended_buy = close < bb_upper
        
        # 5. Volume Spike (Confirmation)
        
        if ema_crossover_up and above_vwap and rsi_bullish and volume_spike and not_overextended_buy:
            return {
                'side': 'BUY',
                'reason': f"EMA Cross Up, Price > VWAP, RSI {rsi:.2f}, ADX {adx:.2f}, Vol Spike",
                'atr': atr
            }
        elif settings.debug and ema_crossover_up:
            logger.debug(f"BUY near-miss: VWAP:{above_vwap}, RSI:{rsi_bullish}, Vol:{volume_spike}, BB:{not_overextended_buy}")
            
        # SELL SIGNAL
        # 1. EMA Crossover: fast crosses below slow
        ema_crossover_down = (prev_ema_fast >= prev_ema_slow) and (ema_fast < ema_slow)
        
        # 2. Price below VWAP (Bearish trend)
        below_vwap = close < vwap
        
        # 3. RSI not oversold (Room to fall)
        rsi_bearish = settings.rsi_oversold < rsi < settings.rsi_overbought - 10
        
        # 4. Not overextended (Price > Lower BB)
        not_overextended_sell = close > bb_lower
        
        if ema_crossover_down and below_vwap and rsi_bearish and volume_spike and not_overextended_sell:
            return {
                'side': 'SELL',
                'reason': f"EMA Cross Down, Price < VWAP, RSI {rsi:.2f}, ADX {adx:.2f}, Vol Spike",
                'atr': atr
            }
            
        return None
        rsi_bearish = 30 < rsi < 60
        
        if ema_crossover_down and below_vwap and rsi_bearish and volume_spike:
            return {
                'side': 'SELL',
                'reason': f"EMA Crossover Down, Price < VWAP, RSI {rsi:.2f}, Vol Spike"
            }
            
        return None
