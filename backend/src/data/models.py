"""
Data models for Kakarot Trading Bot
SQLAlchemy ORM models for database
"""

from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

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
    
    # Spot price at time of subscription
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
