import logging
from collections import deque, defaultdict
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional
from ..websocket.data_models import TickData

logger = logging.getLogger(__name__)

class CandleManager:
    """
    Manages OHLCV candles for different symbols and timeframes.
    Currently supports 1-minute candles.
    """
    def __init__(self, max_candles: int = 1000):
        self.max_candles = max_candles
        # Structure: self.candles[symbol][timeframe] = deque()
        self.candles: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=max_candles)))
        # Keep track of the current incomplete candle
        self.current_candles: Dict[str, Dict[str, Dict]] = defaultdict(lambda: defaultdict(dict))
        # Track last volume to calculate delta
        self.last_volumes: Dict[str, int] = defaultdict(int)
        # Callbacks
        self.on_candle_close_callbacks = []

    def register_callback(self, callback):
        self.on_candle_close_callbacks.append(callback)

    def update_candle(self, tick: TickData):
        """
        Update candles with a new tick.
        """
        # Calculate volume delta
        current_total_volume = tick.volume
        volume_delta = 0
        
        if self.last_volumes[tick.symbol] > 0:
            volume_delta = current_total_volume - self.last_volumes[tick.symbol]
            if volume_delta < 0: # Reset or bad data
                volume_delta = 0
        
        self.last_volumes[tick.symbol] = current_total_volume
        
        # For now, we only support 1-minute candles ('1m')
        self._update_1m_candle(tick, volume_delta)

    def _update_1m_candle(self, tick: TickData, volume_delta: int):
        symbol = tick.symbol
        timestamp = tick.timestamp if hasattr(tick, 'timestamp') else datetime.now() # Fallback if timestamp missing
        
        # Round down to the nearest minute
        candle_time = timestamp.replace(second=0, microsecond=0)
        
        current_candle = self.current_candles[symbol]['1m']
        
        if not current_candle:
            # Initialize new candle
            self._init_candle(symbol, '1m', candle_time, tick, volume_delta)
        elif current_candle['timestamp'] == candle_time:
            # Update existing candle
            self._update_current_candle(current_candle, tick, volume_delta)
        elif current_candle['timestamp'] < candle_time:
            # Close previous candle and start new one
            closed_candle = current_candle.copy()
            self.candles[symbol]['1m'].append(closed_candle)
            
            # Trigger callbacks
            for callback in self.on_candle_close_callbacks:
                try:
                    callback(symbol, '1m', closed_candle)
                except Exception as e:
                    logger.error(f"Error in candle close callback: {e}")
            
            self._init_candle(symbol, '1m', candle_time, tick, volume_delta)
        else:
            # Late tick (ignore or handle separately)
            pass

    def _init_candle(self, symbol: str, timeframe: str, timestamp: datetime, tick: TickData, volume: int):
        self.current_candles[symbol][timeframe] = {
            'timestamp': timestamp,
            'open': tick.last_price,
            'high': tick.last_price,
            'low': tick.last_price,
            'close': tick.last_price,
            'volume': volume
        }

    def _update_current_candle(self, candle: Dict, tick: TickData, volume: int):
        candle['high'] = max(candle['high'], tick.last_price)
        candle['low'] = min(candle['low'], tick.last_price)
        candle['close'] = tick.last_price
        candle['volume'] += volume

    def get_candles(self, symbol: str, timeframe: str = '1m') -> pd.DataFrame:
        """
        Get candles as a DataFrame.
        """
        data = list(self.candles[symbol][timeframe])
        # Add current incomplete candle if exists
        if self.current_candles[symbol][timeframe]:
             data.append(self.current_candles[symbol][timeframe])
             
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

candle_manager = CandleManager()
