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
        # symbol -> last processed cumulative volume
        self.last_volumes: Dict[str, int] = {}
        
        logger.info(f"🚀 SpikeDetector initialized with window_size={window_size}")

    def process_tick(self, tick: TickData) -> List[Dict[str, Any]]:
        """
        Process a new tick and return any detected signals.
        
        Args:
            tick: TickData from WebSocket
            
        Returns:
            List of signal dictionaries
        """
        symbol = tick.symbol
        price = tick.last_price
        
        # Initialize windows if not present
        if symbol not in self.price_windows:
            self.price_windows[symbol] = deque(maxlen=self.window_size)
            self.volume_windows[symbol] = deque(maxlen=self.window_size)
            self.last_volumes[symbol] = tick.volume
            return []
            
        # Calculate tick volume (Upstox volume is cumulative for the day)
        cumulative_volume = tick.volume
        last_vol = self.last_volumes.get(symbol, cumulative_volume)
        tick_volume = cumulative_volume - last_vol
        self.last_volumes[symbol] = cumulative_volume
        
        # Add to windows
        self.price_windows[symbol].append(price)
        if tick_volume > 0:
            self.volume_windows[symbol].append(tick_volume)
            
        # Need enough data to calculate stats (at least 10 ticks)
        if len(self.price_windows[symbol]) < 10:
            return []
            
        signals = []
        
        # 1. Price Spike Detection (Standard Deviation)
        prices = list(self.price_windows[symbol])
        # Use all prices except the current one for baseline
        baseline_prices = prices[:-1]
        mean_price = np.mean(baseline_prices)
        std_price = np.std(baseline_prices)
        
        if std_price > 0:
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
        if len(self.volume_windows[symbol]) >= 10 and tick_volume > 0:
            volumes = list(self.volume_windows[symbol])
            baseline_volumes = volumes[:-1]
            avg_vol = np.mean(baseline_volumes)
            if avg_vol > 0:
                vol_ratio = tick_volume / avg_vol
                if vol_ratio > settings.volume_multiplier:
                    strength = min(vol_ratio / 10.0, 1.0)
                    if strength >= settings.min_signal_strength:
                        signals.append({
                            "type": SignalType.VOLUME_SPIKE,
                            "strength": strength,
                            "metadata": {
                                "vol_ratio": round(float(vol_ratio), 2),
                                "avg_vol": round(float(avg_vol), 2),
                                "tick_vol": tick_volume
                            }
                        })
                    
        # 3. Momentum Detection (ROC over window)
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
