"""
Constants for Upstox Trading Bot
"""

from enum import Enum
from typing import Set

# ========== EXCLUDED SYMBOLS ==========
EXCLUDED_SYMBOLS: Set[str] = {
    "NIFTY",
    "BANKNIFTY",
    "FINANCENIFTY",
    "NIFTYNEXT50",
    "INDIAVIX"
}

# ========== MARKET HOURS (IST) ==========
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
PRE_MARKET_OPEN = "09:00"

TRADING_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# ========== UPSTOX API ENDPOINTS ==========
UPSTOX_API_BASE_URL = "https://api.upstox.com"
UPSTOX_WEBSOCKET_URL = "wss://api.upstox.com/v3/feed/market-data-feed"  # Correct V3 market data endpoint

# ========== ORDER TYPES ==========
class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LIMIT = "STOP_LIMIT"


# ========== ORDER SIDE ==========
class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


# ========== ORDER STATUS ==========
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PLACED = "PLACED"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


# ========== SIGNAL TYPES ==========
class SignalType(str, Enum):
    SPIKE = "SPIKE"
    REVERSAL = "REVERSAL"
    MOMENTUM = "MOMENTUM"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    BREAKOUT = "BREAKOUT"


# ========== SIGNAL STATUS ==========
class SignalStatus(str, Enum):
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    CLOSED = "CLOSED"


# ========== TRADE STATUS ==========
class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STOPPED_OUT = "STOPPED_OUT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_SL = "TRAILING_SL"


# ========== POSITION STATUS ==========
class PositionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


# ========== SYMBOL STATUS ==========
class SymbolStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    DELISTED = "DELISTED"


# ========== TECHNICAL INDICATORS ==========
MA_PERIODS = {
    "short": 20,      # 20-period moving average
    "medium": 50,     # 50-period moving average
    "long": 200       # 200-period moving average
}

RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

ATR_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ========== CANDLE PATTERNS ==========
MIN_CANDLE_SIZE = 0.001  # Minimum candle size to consider
DOJI_THRESHOLD = 0.1  # Within 10% considered as doji

# ========== RATE LIMITING ==========
MAX_WEBSOCKET_SUBSCRIPTIONS = 200
WEBSOCKET_RECONNECT_DELAY = 5  # seconds
WEBSOCKET_MAX_RECONNECT_ATTEMPTS = 10

# ========== DATABASE ==========
DB_ECHO = False  # Set to True to see SQL queries
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10

# ========== TIMEOUTS ==========
API_TIMEOUT = 30  # seconds
WEBSOCKET_TIMEOUT = 60  # seconds

# ========== LOGGING FORMAT ==========
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ========== NSE HOLIDAYS (2025) ==========
NSE_HOLIDAYS_2025 = [
    "2025-01-26",  # Republic Day
    "2025-03-08",  # Maha Shivaratri
    "2025-03-25",  # Holi
    "2025-03-29",  # Good Friday
    "2025-04-17",  # Ram Navami
    "2025-04-21",  # Mahavir Jayanti
    "2025-05-23",  # Buddha Purnima
    "2025-08-15",  # Independence Day
    "2025-08-27",  # Janmashtami
    "2025-09-16",  # Milad-un-Nabi
    "2025-10-02",  # Gandhi Jayanti
    "2025-10-12",  # Dussehra
    "2025-10-31",  # Diwali
    "2025-11-01",  # Diwali (cont.)
    "2025-11-15",  # Guru Nanak Jayanti
    "2025-12-25",  # Christmas
]

# ========== CIRCUIT BREAKERS ==========
CIRCUIT_BREAKER_10_PERCENT = 0.10  # 10% circuit
CIRCUIT_BREAKER_15_PERCENT = 0.15  # 15% circuit
CIRCUIT_BREAKER_20_PERCENT = 0.20  # 20% circuit
