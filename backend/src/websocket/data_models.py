"""
Data models for Upstox V3 WebSocket messages
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TickData(BaseModel):
    """Real-time tick data from WebSocket"""
    
    # Symbol identification
    symbol: str
    token: str
    
    # Price data
    last_price: float
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    
    # Volume
    volume: int
    oi: int = 0  # Open Interest
    
    # Bid/Ask
    bid: float
    ask: float
    bid_volume: int = 0
    ask_volume: int = 0
    
    # Greeks (for options)
    iv: float = 0.0  # Implied Volatility
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    
    # Timestamp
    timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "INFY",
                "token": "NSE_FO|INFY",
                "last_price": 1500.50,
                "open_price": 1495.00,
                "high_price": 1510.00,
                "low_price": 1490.00,
                "close_price": 1505.00,
                "volume": 1000000,
                "oi": 500000,
                "bid": 1500.00,
                "ask": 1501.00,
                "bid_volume": 1000,
                "ask_volume": 1500,
                "iv": 25.5,
                "delta": 0.75,
                "timestamp": "2025-11-29T10:30:00Z"
            }
        }


class SubscriptionRequest(BaseModel):
    """WebSocket subscription request"""
    
    guid: str = "someguid"
    method: str = "sub"
    
    class Data(BaseModel):
        mode: str  # full, ltpc, ohlc
        tokenization: str = "pb"
        tokens: List[str]
    
    data: Data


class UnsubscriptionRequest(BaseModel):
    """WebSocket unsubscription request"""
    
    guid: str = "someguid"
    method: str = "unsub"
    
    class Data(BaseModel):
        mode: str = "full"
        tokens: List[str]
    
    data: Data


class WebSocketMessage(BaseModel):
    """Generic WebSocket message"""
    
    type: str  # "tick", "subscription", "error", etc.
    data: dict
    timestamp: datetime = datetime.utcnow()
