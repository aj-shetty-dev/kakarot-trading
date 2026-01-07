"""
Data models for Upstox Trading Bot
SQLAlchemy ORM models for database
"""

from typing import Optional, Dict, Any
from enum import Enum
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from ..config.constants import (
    OrderStatus, OrderType, OrderSide, SignalStatus, SignalType,
    TradeStatus, PositionStatus, SymbolStatus
)

from ..config.timezone import ist_now

Base = declarative_base()


class Symbol(Base):
    """Represents a tradeable symbol (stock with options/futures)"""
    __tablename__ = "symbols"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100))
    sector = Column(String(50))
    is_fno = Column(Boolean, default=True)
    has_options = Column(Boolean, default=True)
    has_futures = Column(Boolean, default=True)
    status = Column(SQLEnum(SymbolStatus), default=SymbolStatus.ACTIVE)

    # ISIN and instrument identifiers (for correct Upstox API calls)
    isin = Column(String(20))  # International Securities Identification Number
    instrument_token = Column(String(50))  # Full NSE_EQ|ISIN format for API calls

    # Metadata
    oi_shares = Column(Integer)  # Open Interest in shares
    avg_daily_volume = Column(Float)
    liquidity_score = Column(Float)  # 0-1

    # Timestamps
    created_at = Column(DateTime, default=ist_now)
    updated_at = Column(DateTime, default=ist_now, onupdate=ist_now)
    last_refreshed = Column(DateTime)

    # Relationships
    ticks = relationship("Tick", back_populates="symbol")
    signals = relationship("Signal", back_populates="symbol")
    trades = relationship("Trade", back_populates="symbol")
    positions = relationship("Position", back_populates="symbol")

    def __repr__(self):
        return f"<Symbol({self.symbol})>"


class Tick(Base):
    """Represents a single price tick"""
    __tablename__ = "ticks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id"), nullable=False, index=True)
    symbol = relationship("Symbol", back_populates="ticks")

    # Price data
    price = Column(Float, nullable=False)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    
    # Volume
    volume = Column(Integer, nullable=False)
    oi = Column(Integer)  # Open Interest

    # Greeks (for options)
    iv = Column(Float)  # Implied Volatility
    delta = Column(Float)
    gamma = Column(Float)
    theta = Column(Float)
    vega = Column(Float)

    # Market data
    bid = Column(Float)
    ask = Column(Float)
    bid_volume = Column(Integer)
    ask_volume = Column(Integer)

    # Timestamp
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=ist_now, index=True)

    # Relationships
    signals = relationship("Signal", back_populates="tick")

    def __repr__(self):
        return f"<Tick({self.symbol}, {self.price}, {self.timestamp})>"


class Candle(Base):
    """Represents a 1-minute OHLCV candle"""
    __tablename__ = "candles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id"), nullable=False, index=True)
    symbol = relationship("Symbol")

    timeframe = Column(String(10), default="1m", index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=ist_now)

    def __repr__(self):
        return f"<Candle({self.symbol}, {self.timeframe}, {self.timestamp})>"


class Signal(Base):
    """Represents a detected trading signal"""
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id"), nullable=False, index=True)
    symbol = relationship("Symbol", back_populates="signals")

    tick_id = Column(UUID(as_uuid=True), ForeignKey("ticks.id"), nullable=True)
    tick = relationship("Tick", back_populates="signals")

    # Signal details
    signal_type = Column(SQLEnum(SignalType), nullable=False)
    status = Column(SQLEnum(SignalStatus), default=SignalStatus.DETECTED)
    strength = Column(Float, nullable=False)  # 0-1 confidence
    is_noise = Column(Boolean, default=False)
    noise_probability = Column(Float, default=0.0)  # 0-1

    # Technical indicators at signal
    rsi = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)
    bollinger_upper = Column(Float)
    bollinger_lower = Column(Float)
    atr = Column(Float)

    # Metadata
    price_at_signal = Column(Float, nullable=False)
    volume_at_signal = Column(Integer)
    entry_price = Column(Float)
    exit_price = Column(Float)

    # JSON storage for additional data
    signal_metadata = Column(JSON, default={})

    # Timestamps
    detected_at = Column(DateTime, nullable=False, index=True)
    validated_at = Column(DateTime)
    executed_at = Column(DateTime)
    closed_at = Column(DateTime)

    # Relationships
    trade = relationship("Trade", uselist=False, back_populates="signal")

    def __repr__(self):
        return f"<Signal({self.symbol}, {self.signal_type}, {self.strength})>"


class Trade(Base):
    """Represents an executed trade"""
    __tablename__ = "trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"), unique=True, nullable=False)
    signal = relationship("Signal", back_populates="trade")

    symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id"), nullable=False, index=True)
    symbol = relationship("Symbol", back_populates="trades")

    # Order details
    order_type = Column(SQLEnum(OrderType), default=OrderType.MARKET)
    order_side = Column(SQLEnum(OrderSide), nullable=False)
    status = Column(SQLEnum(TradeStatus), default=TradeStatus.OPEN)
    trade_type = Column(String(20), default="LIVE") # LIVE, PAPER, SCALPING

    # Execution details
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float)
    exit_price = Column(Float)

    # Stop loss and take profit
    stop_loss_price = Column(Float)
    take_profit_price = Column(Float)
    trailing_stop_price = Column(Float)

    # P&L
    pnl = Column(Float, default=0.0)
    pnl_percent = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)

    # Execution timestamps
    created_at = Column(DateTime, default=ist_now, index=True)
    entry_time = Column(DateTime)
    exit_time = Column(DateTime, index=True)

    # Upstox order IDs
    upstox_order_id = Column(String(50))
    upstox_exit_order_id = Column(String(50))

    # Metadata
    notes = Column(String(500))
    trade_metadata = Column(JSON, default={})

    def __repr__(self):
        return f"<Trade({self.symbol}, {self.order_side}, {self.status}, {self.trade_type})>"


class Position(Base):
    """Represents a current open position"""
    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id"), nullable=False, unique=True, index=True)
    symbol = relationship("Symbol", back_populates="positions")

    # Position details
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float)
    status = Column(SQLEnum(PositionStatus), default=PositionStatus.ACTIVE)

    # Risk management
    stop_loss_price = Column(Float)
    take_profit_price = Column(Float)
    trailing_stop_price = Column(Float)

    # P&L tracking
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_percent = Column(Float, default=0.0)
    max_pnl = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)

    # Timestamps
    opened_at = Column(DateTime, default=ist_now)
    closed_at = Column(DateTime)

    # Metadata
    trade_ids = Column(JSON, default=[])  # List of related trade IDs
    position_metadata = Column(JSON, default={})

    def __repr__(self):
        return f"<Position({self.symbol}, qty={self.quantity})>"


class OptionChain(Base):
    """Represents an options chain contract"""
    __tablename__ = "option_chains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Symbol information
    symbol = Column(String(20), nullable=False, index=True)  # Base symbol (e.g., "RELIANCE")
    
    # Option details
    option_type = Column(String(2), nullable=False)  # "CE" or "PE"
    strike_price = Column(Float, nullable=False, index=True)
    expiry_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD format
    
    # Trading information
    trading_symbol = Column(String(50), unique=True, nullable=False)
    lot_size = Column(Integer, nullable=False)
    exchange_token = Column(String(50), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=ist_now, index=True)
    updated_at = Column(DateTime, default=ist_now, onupdate=ist_now)

    def __repr__(self):
        return f"<OptionChain({self.symbol} {self.strike_price} {self.option_type} {self.expiry_date})>"


class RateLimitLog(Base):
    """Tracks API rate limits and order submissions"""
    __tablename__ = "rate_limit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    order_count_minute = Column(Integer, default=0)
    order_count_hour = Column(Integer, default=0)
    last_order_time = Column(DateTime)
    window_start_minute = Column(DateTime)
    window_start_hour = Column(DateTime)
    created_at = Column(DateTime, default=ist_now)

    def __repr__(self):
        return f"<RateLimitLog({self.symbol})>"


class Account(Base):
    """Tracks account information and daily stats"""
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Account balance
    available_balance = Column(Float, nullable=False)
    used_margin = Column(Float, default=0.0)
    total_margin = Column(Float, default=0.0)
    
    # Daily statistics
    daily_pnl = Column(Float, default=0.0)
    daily_pnl_percent = Column(Float, default=0.0)
    trades_today = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    
    # Cumulative
    total_pnl = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # Timestamps
    date = Column(DateTime, default=ist_now, index=True)
    updated_at = Column(DateTime, default=ist_now, onupdate=ist_now)

    def __repr__(self):
        return f"<Account(balance={self.available_balance}, daily_pnl={self.daily_pnl})>"


class SubscribedOption(Base):
    """Represents an option we're actively subscribing to via WebSocket"""
    __tablename__ = "subscribed_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Base symbol and option details
    symbol = Column(String(20), nullable=False, index=True)  # e.g., "RELIANCE"
    option_symbol = Column(String(50), nullable=False, unique=True)  # e.g., "RELIANCE 1570 CE 30 DEC 25"
    option_type = Column(String(2), nullable=False)  # "CE" or "PE"
    strike_price = Column(Float, nullable=False)
    
    # ATM/OTM indicator (False = ATM, True = OTM)
    is_otm = Column(Boolean, default=False, index=True)
    
    # Upstox instrument key for API/WebSocket calls (e.g., "NSE_FO|135476")
    instrument_key = Column(String(50), index=True)
    
    # Spot price at time of subscription (used to determine if ATM ± 1 is still valid)
    spot_price_at_subscription = Column(Float, nullable=False)
    
    # Subscription tracking
    is_subscribed = Column(Boolean, default=False, index=True)
    subscribed_at = Column(DateTime)
    websocket_token = Column(String(100))  # Token from Upstox WebSocket subscription
    
    # Pricing data (updated by WebSocket)
    last_price = Column(Float)
    last_price_updated_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=ist_now, index=True)
    updated_at = Column(DateTime, default=ist_now, onupdate=ist_now)

    def __repr__(self):
        return f"<SubscribedOption({self.symbol} {self.strike_price} {self.option_type})>"


class AuditLog(Base):
    """Tracks all important events for auditing"""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(100))
    old_value = Column(JSON)
    new_value = Column(JSON)
    user = Column(String(50))  # System, API, etc.
    description = Column(String(500))
    created_at = Column(DateTime, default=ist_now, index=True)

    def __repr__(self):
        return f"<AuditLog({self.event_type}, {self.entity_type})>"


class TradingSession(Base):
    """Tracks historical bot sessions (start/stop times and summary)"""
    __tablename__ = "trading_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    
    # Summary stats for the session
    total_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    status = Column(String(20), default="ACTIVE")  # ACTIVE, COMPLETED, CRASHED
    
    # Environment info
    mode = Column(String(20))  # Paper/Live
    
    created_at = Column(DateTime, default=ist_now)

    def __repr__(self):
        return f"<TradingSession({self.start_time}, {self.status})>"


class MLFeatureLog(Base):
    """Logs features and outcomes for ML training"""
    __tablename__ = "ml_feature_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id"), nullable=False, index=True)
    
    # Features (Indicators at time of signal)
    features = Column(JSON, nullable=False)
    
    # Label (Outcome of the trade)
    # 1 = Profit, 0 = Loss, None = Pending
    label = Column(Integer)
    pnl_percent = Column(Float)
    
    # Metadata
    signal_type = Column(String(20))
    timestamp = Column(DateTime, default=ist_now, index=True)
    
    # Link to trade if executed
    trade_id = Column(UUID(as_uuid=True), ForeignKey("trades.id"))

    def __repr__(self):
        return f"<MLFeatureLog({self.timestamp}, label={self.label})>"
