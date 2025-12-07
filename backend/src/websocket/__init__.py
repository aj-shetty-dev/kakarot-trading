"""
WebSocket module for real-time data streaming from Upstox V3 API
"""

from .client import (
    UpstoxWebSocketClient,
    initialize_websocket,
    shutdown_websocket,
    get_websocket_client
)
from .data_models import TickData, SubscriptionRequest, UnsubscriptionRequest
from .subscription_manager import (
    SubscriptionManager,
    initialize_subscription_manager,
    get_subscription_manager
)
from .handlers import (
    TickDataHandler,
    AggregatedTickHandler,
    initialize_handlers,
    process_tick,
    get_tick_handlers
)

__all__ = [
    "UpstoxWebSocketClient",
    "TickData",
    "SubscriptionManager",
    "TickDataHandler",
    "initialize_websocket",
    "shutdown_websocket",
    "get_websocket_client",
    "initialize_subscription_manager",
    "get_subscription_manager",
    "initialize_handlers",
    "process_tick",
    "get_tick_handlers"
]
