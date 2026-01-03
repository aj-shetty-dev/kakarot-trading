import pandas as pd
from typing import Optional, Dict

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
        if len(df) < 22: # Need enough data for EMA 21
            return None
            
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Indicators
        ema_9 = curr['ema_9']
        ema_21 = curr['ema_21']
        prev_ema_9 = prev['ema_9']
        prev_ema_21 = prev['ema_21']
        
        rsi = curr['rsi']
        vwap = curr['vwap']
        close = curr['close']
        volume_spike = curr['volume_spike']
        adx = curr['adx']
        bb_upper = curr['bb_upper']
        bb_lower = curr['bb_lower']
        
        # Logic
        
        # Common Filters
        # 1. ADX > 20 (Ensure trend strength, avoid chop)
        strong_trend = adx > 20
        
        if not strong_trend:
            return None

        # BUY SIGNAL
        # 1. EMA Crossover: 9 crosses above 21
        ema_crossover_up = (prev_ema_9 <= prev_ema_21) and (ema_9 > ema_21)
        
        # 2. Price above VWAP (Bullish trend)
        above_vwap = close > vwap
        
        # 3. RSI not overbought (Room to grow)
        rsi_bullish = 40 < rsi < 70
        
        # 4. Not overextended (Price < Upper BB)
        not_overextended_buy = close < bb_upper
        
        # 5. Volume Spike (Confirmation)
        
        if ema_crossover_up and above_vwap and rsi_bullish and volume_spike and not_overextended_buy:
            return {
                'side': 'BUY',
                'reason': f"EMA Cross Up, Price > VWAP, RSI {rsi:.2f}, ADX {adx:.2f}, Vol Spike"
            }
            
        # SELL SIGNAL
        # 1. EMA Crossover: 9 crosses below 21
        ema_crossover_down = (prev_ema_9 >= prev_ema_21) and (ema_9 < ema_21)
        
        # 2. Price below VWAP (Bearish trend)
        below_vwap = close < vwap
        
        # 3. RSI not oversold (Room to fall)
        rsi_bearish = 30 < rsi < 60
        
        # 4. Not overextended (Price > Lower BB)
        not_overextended_sell = close > bb_lower
        
        if ema_crossover_down and below_vwap and rsi_bearish and volume_spike and not_overextended_sell:
            return {
                'side': 'SELL',
                'reason': f"EMA Cross Down, Price < VWAP, RSI {rsi:.2f}, ADX {adx:.2f}, Vol Spike"
            }
            
        return None
        rsi_bearish = 30 < rsi < 60
        
        if ema_crossover_down and below_vwap and rsi_bearish and volume_spike:
            return {
                'side': 'SELL',
                'reason': f"EMA Crossover Down, Price < VWAP, RSI {rsi:.2f}, Vol Spike"
            }
            
        return None
