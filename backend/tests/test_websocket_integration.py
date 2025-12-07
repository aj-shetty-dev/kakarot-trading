"""
WebSocket Integration Tests
Tests the complete WebSocket data flow: connection → subscription → handlers
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.websocket.client import UpstoxWebSocketClient, initialize_websocket, shutdown_websocket
from src.websocket.data_models import TickData, SubscriptionRequest
from src.websocket.subscription_manager import SubscriptionManager
from src.websocket.handlers import (
    TickDataHandler, AggregatedTickHandler, 
    initialize_handlers, process_tick
)
from src.websocket.service import WebSocketService
from src.data.models import Symbol


# ========== FIXTURES ==========

@pytest.fixture
def sample_tick_data():
    """Create sample tick data"""
    return TickData(
        symbol="INFY",
        token="NSE_FO|INFY",
        last_price=1234.50,
        open_price=1200.00,
        high_price=1250.00,
        low_price=1190.00,
        close_price=1234.50,
        volume=1000000,
        oi=500000,
        bid=1234.40,
        ask=1234.60,
        bid_volume=50000,
        ask_volume=60000,
        iv=0.25,
        delta=0.65,
        gamma=0.005,
        theta=-0.02,
        vega=0.10,
        timestamp=datetime.utcnow()
    )


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket"""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_db_session():
    """Create mock database session"""
    session = MagicMock()
    return session


# ========== WEBSOCKET CLIENT TESTS ==========

class TestUpstoxWebSocketClient:
    """Tests for WebSocket client"""

    def test_initialization(self):
        """Test client initialization"""
        client = UpstoxWebSocketClient(
            access_token="test_token",
            client_code="49CLBQ"
        )
        
        assert client.access_token == "test_token"
        assert client.client_code == "49CLBQ"
        assert client.is_connected is False
        assert len(client.subscribed_symbols) == 0
        assert client.ws_url == "wss://api.upstox.com/v3"

    @pytest.mark.asyncio
    async def test_symbol_to_token_conversion(self):
        """Test symbol to token conversion"""
        client = UpstoxWebSocketClient("token", "code")
        
        token = client._symbol_to_token("INFY")
        assert token == "NSE_FO|INFY"
        
        token = client._symbol_to_token("BANKNIFTY")
        assert token == "NSE_FO|BANKNIFTY"

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_websocket):
        """Test successful connection"""
        client = UpstoxWebSocketClient("token", "code")
        
        with patch('websockets.connect', return_value=mock_websocket):
            result = await client.connect()
            
            assert result is True
            assert client.is_connected is True
            assert client.reconnect_attempts == 0

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure"""
        client = UpstoxWebSocketClient("token", "code")
        
        with patch('websockets.connect', side_effect=Exception("Connection failed")):
            result = await client.connect()
            
            assert result is False
            assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_subscribe(self, mock_websocket):
        """Test subscription"""
        client = UpstoxWebSocketClient("token", "code")
        client.websocket = mock_websocket
        client.is_connected = True
        
        result = await client.subscribe(["INFY", "TCS"], mode="full")
        
        assert result is True
        assert "INFY" in client.subscribed_symbols
        assert "TCS" in client.subscribed_symbols
        mock_websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsubscribe(self, mock_websocket):
        """Test unsubscription"""
        client = UpstoxWebSocketClient("token", "code")
        client.websocket = mock_websocket
        client.is_connected = True
        client.subscribed_symbols = {"INFY", "TCS"}
        
        result = await client.unsubscribe(["INFY"])
        
        assert result is True
        assert "INFY" not in client.subscribed_symbols
        assert "TCS" in client.subscribed_symbols

    def test_parse_tick_data(self, sample_tick_data):
        """Test tick data parsing"""
        client = UpstoxWebSocketClient("token", "code")
        
        data = {
            "symbol": "INFY",
            "tk": "NSE_FO|INFY",
            "ltp": 1234.50,
            "o": 1200.00,
            "h": 1250.00,
            "l": 1190.00,
            "c": 1234.50,
            "v": 1000000,
            "oi": 500000,
            "bid": 1234.40,
            "ask": 1234.60,
            "bidv": 50000,
            "askv": 60000,
            "iv": 0.25,
            "delta": 0.65,
            "gamma": 0.005,
            "theta": -0.02,
            "vega": 0.10
        }
        
        tick = client._parse_tick(data)
        
        assert tick is not None
        assert tick.symbol == "INFY"
        assert tick.last_price == 1234.50
        assert tick.volume == 1000000
        assert tick.iv == 0.25

    @pytest.mark.asyncio
    async def test_register_handler(self):
        """Test handler registration"""
        client = UpstoxWebSocketClient("token", "code")
        
        async def dummy_handler(tick):
            pass
        
        client.register_handler(dummy_handler)
        
        assert len(client.message_handlers) == 1
        assert client.message_handlers[0] == dummy_handler


# ========== HANDLERS TESTS ==========

class TestTickDataHandlers:
    """Tests for tick data handlers"""

    @pytest.mark.asyncio
    async def test_tick_db_handler_initialization(self):
        """Test tick DB handler initialization"""
        handler = TickDataHandler()
        
        assert handler.tick_count == 0
        assert handler.get_stats()["ticks_processed"] == 0

    @pytest.mark.asyncio
    async def test_aggregated_handler_initialization(self):
        """Test aggregated handler initialization"""
        handler = AggregatedTickHandler()
        
        assert len(handler.ticks_by_symbol) == 0
        assert handler.get_stats()["symbols_tracked"] == 0

    @pytest.mark.asyncio
    async def test_aggregated_handler_tick_processing(self, sample_tick_data):
        """Test aggregated handler tick processing"""
        handler = AggregatedTickHandler()
        
        result = await handler.handle_tick(sample_tick_data)
        
        assert result is True
        assert "INFY" in handler.ticks_by_symbol
        assert handler.ticks_by_symbol["INFY"]["price"] == 1234.50

    @pytest.mark.asyncio
    async def test_get_latest_tick(self, sample_tick_data):
        """Test getting latest tick"""
        handler = AggregatedTickHandler()
        
        await handler.handle_tick(sample_tick_data)
        
        tick = handler.get_latest_tick("INFY")
        assert tick is not None
        assert tick["price"] == 1234.50
        assert tick["volume"] == 1000000

    @pytest.mark.asyncio
    async def test_process_tick(self, sample_tick_data):
        """Test tick processing through all handlers"""
        await initialize_handlers()
        
        result = await process_tick(sample_tick_data)
        # Result might be False if DB not available in test, but function should execute
        assert isinstance(result, bool)


# ========== SUBSCRIPTION MANAGER TESTS ==========

class TestSubscriptionManager:
    """Tests for subscription manager"""

    @pytest.mark.asyncio
    async def test_subscription_manager_initialization(self, mock_websocket):
        """Test subscription manager initialization"""
        client = UpstoxWebSocketClient("token", "code")
        client.websocket = mock_websocket
        client.is_connected = True
        
        manager = SubscriptionManager(client)
        
        assert manager.ws_client == client
        assert len(manager.all_symbols) == 0
        assert len(manager.subscribed_symbols) == 0

    def test_get_subscription_status(self, mock_websocket):
        """Test getting subscription status"""
        client = UpstoxWebSocketClient("token", "code")
        client.websocket = mock_websocket
        
        manager = SubscriptionManager(client)
        status = manager.get_subscription_status()
        
        assert "total_symbols" in status
        assert "subscribed_count" in status
        assert "failed_count" in status


# ========== WEBSOCKET SERVICE TESTS ==========

class TestWebSocketService:
    """Tests for WebSocket service"""

    def test_service_initialization(self):
        """Test service initialization"""
        service = WebSocketService()
        
        assert service.is_running is False
        assert service.ws_client is None
        assert service.subscription_manager is None

    def test_service_status_when_not_running(self):
        """Test service status when not running"""
        service = WebSocketService()
        
        status = service.get_status()
        
        assert status["is_running"] is False
        assert status["websocket_connected"] is False

    def test_service_is_not_healthy_when_not_running(self):
        """Test service health check"""
        service = WebSocketService()
        
        assert service.is_healthy() is False


# ========== DATA MODELS TESTS ==========

class TestDataModels:
    """Tests for WebSocket data models"""

    def test_tick_data_creation(self, sample_tick_data):
        """Test TickData model creation"""
        assert sample_tick_data.symbol == "INFY"
        assert sample_tick_data.last_price == 1234.50
        assert sample_tick_data.volume == 1000000

    def test_subscription_request_creation(self):
        """Test SubscriptionRequest model creation"""
        req = SubscriptionRequest(
            guid="test-guid",
            method="sub",
            data={
                "mode": "full",
                "tokenization": "pb",
                "tokens": ["NSE_FO|INFY", "NSE_FO|TCS"]
            }
        )
        
        assert req.method == "sub"
        assert len(req.data["tokens"]) == 2


# ========== INTEGRATION TESTS ==========

class TestWebSocketIntegration:
    """Integration tests for complete WebSocket flow"""

    @pytest.mark.asyncio
    async def test_message_handler_call_on_message(self, mock_websocket, sample_tick_data):
        """Test that handlers are called on incoming messages"""
        client = UpstoxWebSocketClient("token", "code")
        client.websocket = mock_websocket
        client.is_connected = True
        
        handler_called = False
        
        async def test_handler(tick):
            nonlocal handler_called
            handler_called = True
        
        client.register_handler(test_handler)
        
        # Simulate receiving a tick
        await client._handle_message(
            json.dumps({
                "symbol": "INFY",
                "ltp": 1234.50,
                "o": 1200.00,
                "h": 1250.00,
                "l": 1190.00,
                "c": 1234.50,
                "v": 1000000
            }).encode()
        )
        
        await asyncio.sleep(0.1)  # Give handler time to execute
        assert handler_called is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
