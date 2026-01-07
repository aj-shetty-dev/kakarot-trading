"""
Spike Detector - Identifies price and volume anomalies in real-time
"""

import logging
from collections import deque
from typing import Dict, List, Optional, Any
import numpy as np
from datetime import datetime

from ..config.settings import settings
from ..config.constants import SignalType, SignalStatus
from ..websocket.data_models import TickData

logger = logging.getLogger(__name__)

class SpikeDetector:
    """
    Detects price and volume spikes in real-time tick data.
    Uses a rolling window to calculate statistics and identify anomalies.
    """

    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        # symbol -> deque of prices
        self.price_windows: Dict[str, deque] = {}
        # symbol -> deque of volumes
        self.volume_windows: Dict[str, deque] = {}
        
        # Incremental stats: {symbol: {'sum': float, 'sum_sq': float, 'count': int}}
        self.price_stats: Dict[str, Dict[str, float]] = {}
        self.volume_stats: Dict[str, Dict[str, float]] = {}
        
        # symbol -> last processed cumulative volume
        self.last_volumes: Dict[str, int] = {}
        
        logger.info(f"🚀 SpikeDetector initialized with window_size={window_size}")

    def _update_stats(self, stats_dict: Dict[str, Dict], symbol: str, val: float, old_val: Optional[float] = None):
        """Update incremental sum and sum_squares for std dev calculation"""
        if symbol not in stats_dict:
            stats_dict[symbol] = {'sum': 0.0, 'sum_sq': 0.0, 'count': 0}
        
        stats = stats_dict[symbol]
        
        if old_val is not None:
            stats['sum'] -= old_val
            stats['sum_sq'] -= old_val * old_val
            stats['count'] -= 1
            
        stats['sum'] += val
        stats['sum_sq'] += val * val
        stats['count'] += 1

    def process_tick(self, tick: TickData) -> List[Dict[str, Any]]:
        """
        Process a new tick and return any detected signals.
        """
        symbol = tick.symbol
        price = tick.last_price
        
        # Initialize windows if not present
        if symbol not in self.price_windows:
            self.price_windows[symbol] = deque(maxlen=self.window_size)
            self.volume_windows[symbol] = deque(maxlen=self.window_size)
            self.last_volumes[symbol] = tick.volume
            self.price_stats[symbol] = {'sum': 0.0, 'sum_sq': 0.0, 'count': 0}
            self.volume_stats[symbol] = {'sum': 0.0, 'sum_sq': 0.0, 'count': 0}
            return []
            
        # Calculate tick volume
        cumulative_volume = tick.volume
        last_vol = self.last_volumes.get(symbol, cumulative_volume)
        tick_volume = float(cumulative_volume - last_vol)
        self.last_volumes[symbol] = cumulative_volume
        
        # Add price to window and update stats
        old_price = None
        if len(self.price_windows[symbol]) == self.window_size:
            old_price = self.price_windows[symbol][0]
        
        self.price_windows[symbol].append(price)
        self._update_stats(self.price_stats, symbol, price, old_price)
        
        # Add volume to window and update stats
        if tick_volume > 0:
            old_vol = None
            if len(self.volume_windows[symbol]) == self.window_size:
                old_vol = self.volume_windows[symbol][0]
            
            self.volume_windows[symbol].append(tick_volume)
            self._update_stats(self.volume_stats, symbol, tick_volume, old_vol)
            
        # Need enough data to calculate stats
        stats = self.price_stats[symbol]
        if stats['count'] < 10:
            return []
            
        signals = []
        
        # 1. Price Spike Detection (using incremental stats)
        # Standard Deviation formula: sqrt((sum_sq / n) - (mean^2))
        n = stats['count']
        mean_price = stats['sum'] / n
        variance = (stats['sum_sq'] / n) - (mean_price * mean_price)
        std_price = (variance ** 0.5) if variance > 0 else 0
        
        if std_price > 1e-6: # Avoid division by zero
            z_score = abs(price - mean_price) / std_price
            if z_score > settings.spike_threshold:
                strength = min(z_score / 10.0, 1.0)
                if strength >= settings.min_signal_strength:
                    signals.append({
                        "type": SignalType.SPIKE,
                        "strength": strength,
                        "metadata": {
                            "z_score": round(float(z_score), 2),
                            "mean": round(float(mean_price), 2),
                            "std": round(float(std_price), 4),
                            "price": price
                        }
                    })
                
        # 2. Volume Surge Detection
        vol_stats = self.volume_stats[symbol]
        if vol_stats['count'] >= 10 and tick_volume > 0:
            avg_vol = vol_stats['sum'] / vol_stats['count']
            if avg_vol > 0:
                vol_ratio = tick_volume / avg_vol
                if vol_ratio > settings.volume_multiplier:
                    strength = min(vol_ratio / 10.0, 1.0)
                    if strength >= settings.min_signal_strength:
                        signals.append({
                            "type": SignalType.VOLUME_SURGE,
                            "strength": strength,
                            "metadata": {
                                "vol_ratio": round(float(vol_ratio), 2),
                                "avg_vol": round(float(avg_vol), 2),
                                "tick_vol": tick_volume
                            }
                        })
                        
        # 3. Momentum Detection (ROC over window)
        prices = self.price_windows[symbol]
        start_price = prices[0]
        if start_price > 0:
            roc = ((price - start_price) / start_price) * 100
            # Flag if ROC > 1.5% in the window (approx 50 ticks)
            if abs(roc) > 1.5:
                strength = min(abs(roc) / 5.0, 1.0)
                if strength >= settings.min_signal_strength:
                    signals.append({
                        "type": SignalType.MOMENTUM,
                        "strength": strength,
                        "metadata": {
                            "roc": round(float(roc), 2),
                            "window_start_price": start_price
                        }
                    })
            
        return signals

# Global instance
spike_detector = SpikeDetector()
