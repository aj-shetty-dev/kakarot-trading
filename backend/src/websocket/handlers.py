"""
WebSocket message handlers
Process incoming tick data and store in database

Updated for Upstox V3: 
- Tick data uses instrument_key (e.g., NSE_FO|60965) as symbol
- Lookup is done via SubscribedOption.instrument_key
- Live prices logged to /app/logs/live_prices.log
- Log rotation enabled to prevent disk space issues
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
import logging
from logging.handlers import RotatingFileHandler

from ..config.logging import websocket_logger as logger
from ..data.models import Tick, Symbol, SubscribedOption
from ..data.database import SessionLocal
from .data_models import TickData

# ============================================================
# LOGGING CONFIGURATION - Space-efficient with rotation
# ============================================================
# Set to False to disable file logging entirely (DB only)
ENABLE_FILE_LOGGING = os.environ.get('ENABLE_FILE_LOGGING', 'true').lower() == 'true'

# Optional: enable/disable TOON logging independently
ENABLE_TOON_LOGGING = os.environ.get('ENABLE_TOON_LOGGING', 'true').lower() == 'true'

# Max size per log file: 50MB (rotates to .1, .2, etc.)
MAX_LOG_SIZE = int(os.environ.get('MAX_LOG_SIZE_MB', '50')) * 1024 * 1024

# Keep 3 backup files (50MB x 4 = 200MB max per log type)
BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', '3'))

# Sample rate: log every Nth tick to file (1 = all, 10 = every 10th)
# Database always gets ALL ticks, this only affects log files
LOG_SAMPLE_RATE = int(os.environ.get('LOG_SAMPLE_RATE', '1'))

log_dir = os.environ.get('LOG_DIR', '/app/logs')
os.makedirs(log_dir, exist_ok=True)

# Create a separate logger for live prices with ROTATION
price_logger = logging.getLogger('live_prices')
price_logger.setLevel(logging.INFO)

if ENABLE_FILE_LOGGING:
    # Rotating file handler - 50MB max, keeps 3 backups (200MB total max)
    price_file_handler = RotatingFileHandler(
        f'{log_dir}/live_prices.log',
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    price_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    price_logger.addHandler(price_file_handler)

# JSON log file for programmatic access (also with rotation)
json_log_path = f'{log_dir}/live_prices.jsonl'

# TOON log file for token-efficient representation
toon_log_path = f'{log_dir}/live_prices.toon'

# Counter for sampling (shared across JSON/TOON writes)
_sample_counter = 0


def _should_sample() -> bool:
    """Return True if this tick should be logged based on sampling."""
    global _sample_counter
    _sample_counter += 1
    if LOG_SAMPLE_RATE > 1 and _sample_counter % LOG_SAMPLE_RATE != 0:
        return False
    return True


def _write_json_log(tick_data: TickData, option_name: str):
    """Write a single tick as JSONL (rotation handled)."""
    try:
        tick_json = {
            "ts": datetime.utcnow().strftime('%H:%M:%S'),  # Shorter timestamp
            "opt": option_name[:30],  # Truncate option name
            "key": tick_data.symbol,
            "ltp": round(tick_data.last_price, 2),
            "d": round(tick_data.delta, 3) if tick_data.delta is not None else None,
            "iv": round(tick_data.iv * 100, 1) if tick_data.iv is not None else None,
            "oi": tick_data.oi
        }

        # Check file size and rotate if needed
        if os.path.exists(json_log_path):
            if os.path.getsize(json_log_path) > MAX_LOG_SIZE:
                _rotate_json_log()

        with open(json_log_path, 'a') as f:
            f.write(json.dumps(tick_json, separators=(',', ':')) + '\n')
    except Exception as e:
        logger.error(f"Error writing JSON log: {e}")


def _ensure_toon_header():
    """Ensure TOON file has a header before appending rows."""
    try:
        if not os.path.exists(toon_log_path) or os.path.getsize(toon_log_path) == 0:
            with open(toon_log_path, 'a') as f:
                f.write("ticks{ts,opt,key,ltp,d,iv,oi}:\n")
    except Exception as e:
        logger.error(f"Error preparing TOON log header: {e}")


def _write_toon_log(tick_data: TickData, option_name: str):
    """Write a single tick row in TOON tabular form (rotation + header)."""
    try:
        # Rotate if needed before writing
        if os.path.exists(toon_log_path):
            if os.path.getsize(toon_log_path) > MAX_LOG_SIZE:
                _rotate_toon_log()

        _ensure_toon_header()

        ts = datetime.utcnow().strftime('%H:%M:%S')
        opt = option_name[:50]  # keep readable but bounded
        key = tick_data.symbol
        ltp = f"{tick_data.last_price:.2f}" if tick_data.last_price is not None else "null"
        d = "null" if tick_data.delta is None else f"{tick_data.delta:.3f}"
        iv = "null" if tick_data.iv is None else f"{tick_data.iv * 100:.1f}"
        oi = "null" if tick_data.oi is None else str(tick_data.oi)

        # TOON tabular row (comma-separated, indented)
        row = f"  {ts},{opt},{key},{ltp},{d},{iv},{oi}\n"

        with open(toon_log_path, 'a') as f:
            f.write(row)
    except Exception as e:
        logger.error(f"Error writing TOON log: {e}")


def _rotate_toon_log():
    """Rotate TOON log file (similar to JSON rotation)."""
    try:
        for i in range(BACKUP_COUNT, 0, -1):
            old = f"{toon_log_path}.{i}"
            new = f"{toon_log_path}.{i+1}"
            if os.path.exists(old):
                if i == BACKUP_COUNT:
                    os.remove(old)
                else:
                    os.rename(old, new)
        os.rename(toon_log_path, f"{toon_log_path}.1")
    except Exception as e:
        logger.error(f"Error rotating TOON log: {e}")


def _rotate_json_log():
    """Manually rotate JSON log file"""
    try:
        for i in range(BACKUP_COUNT, 0, -1):
            old = f"{json_log_path}.{i}"
            new = f"{json_log_path}.{i+1}"
            if os.path.exists(old):
                if i == BACKUP_COUNT:
                    os.remove(old)  # Delete oldest
                else:
                    os.rename(old, new)
        os.rename(json_log_path, f"{json_log_path}.1")
    except Exception as e:
        logger.error(f"Error rotating JSON log: {e}")


def log_tick_structured(tick_data: TickData, option_name: str):
    """Sample once and write tick to JSONL and TOON logs if enabled."""
    if not (ENABLE_FILE_LOGGING or ENABLE_TOON_LOGGING):
        return

    if not _should_sample():
        return

    if ENABLE_FILE_LOGGING:
        _write_json_log(tick_data, option_name)

    if ENABLE_TOON_LOGGING:
        _write_toon_log(tick_data, option_name)


class TickDataHandler:
    """Handles incoming tick data from WebSocket"""

    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize tick handler
        
        Args:
            db_session: Database session (creates new if None)
        """
        self.db = db_session
        self.tick_count = 0
        self.last_log_time = datetime.utcnow()
        
        # Cache instrument_key -> symbol_id mapping
        self._instrument_key_cache: Dict[str, int] = {}
        # Cache instrument_key -> option_symbol for readable logging
        self._instrument_key_to_name: Dict[str, str] = {}
        self._cache_loaded = False

    def _load_instrument_key_cache(self):
        """Load instrument_key to symbol_id mapping from SubscribedOption table"""
        if self._cache_loaded:
            return
            
        try:
            if not self.db:
                self.db = SessionLocal()
            
            # Load all subscribed options with their instrument_key
            options = self.db.query(SubscribedOption).all()
            
            for opt in options:
                if opt.instrument_key:
                    # Try to find corresponding symbol
                    symbol = self.db.query(Symbol).filter(
                        Symbol.symbol == opt.symbol
                    ).first()
                    
                    if symbol:
                        self._instrument_key_cache[opt.instrument_key] = symbol.id
                    
                    # Also cache readable name for logging
                    self._instrument_key_to_name[opt.instrument_key] = opt.option_symbol or opt.symbol
            
            self._cache_loaded = True
            logger.info(f"✅ Loaded {len(self._instrument_key_cache)} instrument_key -> symbol_id mappings")
            
        except Exception as e:
            logger.error(f"Error loading instrument key cache: {e}")

    async def handle_tick(self, tick_data: TickData) -> bool:
        """
        Handle incoming tick data
        
        Args:
            tick_data: TickData model from WebSocket
        
        Returns:
            bool: True if handled successfully
        """
        try:
            # Ensure we have a database session
            if not self.db:
                self.db = SessionLocal()
            
            # Load cache if not loaded
            if not self._cache_loaded:
                self._load_instrument_key_cache()

            # For V3: tick_data.symbol contains instrument_key (e.g., NSE_FO|60965)
            instrument_key = tick_data.symbol
            
            # Look up symbol_id from cache
            symbol_id = self._instrument_key_cache.get(instrument_key)
            
            if not symbol_id:
                # Try direct lookup as fallback (for non-V3 format)
                symbol = self.db.query(Symbol).filter(
                    Symbol.symbol == instrument_key
                ).first()
                
                if symbol:
                    symbol_id = symbol.id
                    self._instrument_key_cache[instrument_key] = symbol_id
                else:
                    logger.debug(f"Instrument key {instrument_key} not found in cache or Symbol table")
                    return False

            # Create tick record
            tick = Tick(
                symbol_id=symbol_id,
                price=tick_data.last_price,
                open_price=tick_data.open_price,
                high_price=tick_data.high_price,
                low_price=tick_data.low_price,
                close_price=tick_data.close_price,
                volume=tick_data.volume,
                oi=tick_data.oi,
                iv=tick_data.iv,
                delta=tick_data.delta,
                gamma=tick_data.gamma,
                theta=tick_data.theta,
                vega=tick_data.vega,
                bid=tick_data.bid,
                ask=tick_data.ask,
                bid_volume=tick_data.bid_volume,
                ask_volume=tick_data.ask_volume,
                timestamp=tick_data.timestamp
            )

            # Add to session
            self.db.add(tick)
            self.db.commit()

            self.tick_count += 1
            
            # Log live price to file (respects sample rate and enable flag)
            option_name = self._instrument_key_to_name.get(instrument_key, instrument_key)
            
            if ENABLE_FILE_LOGGING and (LOG_SAMPLE_RATE == 1 or self.tick_count % LOG_SAMPLE_RATE == 0):
                price_logger.info(
                    f"{option_name[:30]} | {tick_data.last_price:.2f} | "
                    f"Δ:{tick_data.delta:.2f} | IV:{tick_data.iv:.1%} | OI:{tick_data.oi}"
                )
            
            # Also log structured files (JSONL + TOON) with sampling/rotation
            log_tick_structured(tick_data, option_name)

            # Log progress periodically to main log
            now = datetime.utcnow()
            elapsed = (now - self.last_log_time).total_seconds()
            
            if elapsed > 60:  # Log every 60 seconds
                logger.info(f"📊 Processed {self.tick_count} ticks")
                self.last_log_time = now

            return True

        except Exception as e:
            logger.error(f"Error handling tick for {tick_data.symbol}: {e}")
            if self.db:
                self.db.rollback()
            return False

    def close(self):
        """Close database session"""
        if self.db:
            self.db.close()
            self.db = None

    def get_stats(self) -> dict:
        """Get handler statistics"""
        return {
            "ticks_processed": self.tick_count,
            "status": "active"
        }


class AggregatedTickHandler:
    """Aggregates ticks and provides statistics"""

    def __init__(self):
        """Initialize aggregated tick handler"""
        self.ticks_by_symbol = {}
        self.price_updates = 0

    async def handle_tick(self, tick_data: TickData) -> bool:
        """
        Handle tick with aggregation
        
        Args:
            tick_data: TickData from WebSocket
        
        Returns:
            bool: True if handled successfully
        """
        try:
            # Update in-memory cache
            if tick_data.symbol not in self.ticks_by_symbol:
                self.ticks_by_symbol[tick_data.symbol] = {}

            self.ticks_by_symbol[tick_data.symbol] = {
                "price": tick_data.last_price,
                "volume": tick_data.volume,
                "bid": tick_data.bid,
                "ask": tick_data.ask,
                "timestamp": tick_data.timestamp
            }

            self.price_updates += 1
            return True

        except Exception as e:
            logger.error(f"Error in aggregated handler: {e}")
            return False

    def get_latest_tick(self, symbol: str) -> Optional[dict]:
        """Get latest tick for a symbol"""
        return self.ticks_by_symbol.get(symbol)

    def get_stats(self) -> dict:
        """Get aggregation statistics"""
        return {
            "symbols_tracked": len(self.ticks_by_symbol),
            "price_updates": self.price_updates
        }


# Create global handlers
tick_db_handler: Optional[TickDataHandler] = None
aggregated_handler: Optional[AggregatedTickHandler] = None


async def initialize_handlers():
    """Initialize message handlers"""
    global tick_db_handler, aggregated_handler

    try:
        # Database handler for persistence
        tick_db_handler = TickDataHandler()
        
        # In-memory aggregation handler
        aggregated_handler = AggregatedTickHandler()
        
        logger.info("✅ Message handlers initialized")
        
    except Exception as e:
        logger.error(f"Error initializing handlers: {e}")


async def process_tick(tick_data: TickData) -> bool:
    """
    Process incoming tick data through all handlers
    
    Args:
        tick_data: TickData from WebSocket
    
    Returns:
        bool: True if all handlers successful
    """
    results = []
    
    # Process through database handler
    if tick_db_handler:
        result = await tick_db_handler.handle_tick(tick_data)
        results.append(result)
    
    # Process through aggregation handler
    if aggregated_handler:
        result = await aggregated_handler.handle_tick(tick_data)
        results.append(result)
    
    return all(results)


def get_tick_handlers():
    """Get all tick handlers"""
    return {
        "db_handler": tick_db_handler,
        "aggregated_handler": aggregated_handler
    }


def get_aggregated_handler() -> Optional[AggregatedTickHandler]:
    """Get the aggregated tick handler"""
    return aggregated_handler
