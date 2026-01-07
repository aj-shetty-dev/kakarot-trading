"""
Signal Service - Orchestrates signal detection and persistence
"""

import logging
import os
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from ..config.logging import logger
from ..config.settings import settings
from ..config.timezone import ist_now
from ..config.constants import SignalStatus, SignalType
from ..data.models import Signal, Tick, Symbol, SubscribedOption
from ..data.database import SessionLocal
from ..websocket.data_models import TickData
from .spike_detector import spike_detector
from ..notifications.telegram import get_telegram_service
from ..trading.service import trading_service

# Create a separate logger for signals
signal_logger = logging.getLogger('signals')
signal_logger.setLevel(logging.INFO)

# Ensure log directory exists
date_str = ist_now().strftime('%Y-%m-%d')
signal_log_dir = os.path.join(settings.log_dir, date_str, "signals")
os.makedirs(signal_log_dir, exist_ok=True)

# File handler for signals
signal_file = os.path.join(signal_log_dir, "detections.log")
handler = logging.FileHandler(signal_file)
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
signal_logger.addHandler(handler)

class SignalService:
    """Service to handle signal detection and processing"""

    def __init__(self):
        self.db: Optional[Session] = None
        self.telegram = get_telegram_service(settings)
        self._instrument_to_symbol_id: Dict[str, Any] = {}
        self._cache_loaded = False
        self._last_signal_time: Dict[str, datetime] = {}
        self.cooldown_seconds = 60

    def _load_cache(self):
        """Load instrument_key to symbol_id mapping"""
        if self._cache_loaded:
            return
            
        db = SessionLocal()
        try:
            options = db.query(SubscribedOption).all()
            for opt in options:
                if opt.instrument_key:
                    # Find symbol ID
                    symbol = db.query(Symbol).filter(Symbol.symbol == opt.symbol).first()
                    if symbol:
                        self._instrument_to_symbol_id[opt.instrument_key] = {
                            "id": symbol.id,
                            "name": opt.option_symbol or opt.symbol
                        }
            self._cache_loaded = True
            logger.info(f"✅ SignalService cache loaded: {len(self._instrument_to_symbol_id)} mappings")
        except Exception as e:
            logger.error(f"Error loading SignalService cache: {e}")
        finally:
            db.close()

    async def process_tick(self, tick_data: TickData) -> List[Signal]:
        """
        Process a tick for signals and save to DB if detected
        """
        if not self._cache_loaded:
            self._load_cache()

        # Get signals from spike detector
        detected_signals = spike_detector.process_tick(tick_data)
        
        if not detected_signals:
            return []

        # Get symbol info
        symbol_info = self._instrument_to_symbol_id.get(tick_data.symbol)
        if not symbol_info:
            return []

        signals_to_return = []
        db = SessionLocal()
        try:
            for sig_data in detected_signals:
                # Apply cooldown to prevent signal storms
                sig_type = sig_data['type']
                cooldown_key = f"{symbol_info['name']}_{sig_type}"
                now = ist_now()
                
                if cooldown_key in self._last_signal_time:
                    elapsed = (now - self._last_signal_time[cooldown_key]).total_seconds()
                    if elapsed < self.cooldown_seconds:
                        continue
                
                # Update last signal time
                self._last_signal_time[cooldown_key] = now

                # Log the detection
                msg = (f"🎯 SIGNAL DETECTED: {symbol_info['name']} | "
                       f"Type: {sig_data['type']} | "
                       f"Strength: {sig_data['strength']:.2f} | "
                       f"Price: {tick_data.last_price}")
                signal_logger.info(msg)
                
                # Create Signal record
                signal = Signal(
                    symbol_id=symbol_info['id'],
                    tick_id=None, # We'll need to link this if we save ticks to DB first
                    signal_type=sig_data['type'],
                    status=SignalStatus.DETECTED,
                    strength=sig_data['strength'],
                    price_at_signal=tick_data.last_price,
                    volume_at_signal=tick_data.volume,
                    detected_at=ist_now(),
                    signal_metadata={
                        **sig_data['metadata'],
                        "instrument_key": tick_data.symbol,
                        "option_name": symbol_info['name']
                    }
                )
                
                db.add(signal)
                db.commit()
                db.refresh(signal)
                
                signals_to_return.append(signal)
                
                # Trigger trading service
                asyncio.create_task(trading_service.handle_signal(signal.id))

            return signals_to_return
            
        except Exception as e:
            logger.error(f"Error saving signals: {e}")
            db.rollback()
            return []
        finally:
            db.close()

# Global instance
signal_service = SignalService()
