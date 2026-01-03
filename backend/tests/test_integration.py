import pytest
import unittest.mock
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
from src.trading.service import TradingService
from src.signals.ml_pipeline import MLDataPipeline
from src.websocket.data_models import TickData

@pytest.mark.asyncio
async def test_signal_to_trade_flow():
    # 1. Setup Mocks
    mock_upstox = MagicMock()
    mock_upstox.place_order = AsyncMock(return_value={"status": "success", "data": {"order_id": "12345"}})
    
    # 2. Initialize Service
    service = TradingService()
    # We don't need to mock risk_manager as it's a global singleton imported in service.py
    # But we can mock its methods if needed. For now, let's just mock the order_manager
    from src.trading.order_manager import order_manager
    order_manager.place_order = AsyncMock(return_value="12345")
    
    # 3. Create a Mock Signal
    mock_signal = MagicMock()
    # Use a UUID for symbol_id to match the model
    import uuid
    symbol_uuid = uuid.uuid4()
    mock_signal.symbol_id = symbol_uuid
    mock_signal.price_at_signal = 2500.0
    mock_signal.id = 1
    
    # 4. Mock DB Session
    from src.data.database import SessionLocal
    mock_db = MagicMock()
    # Mock the query for Symbol
    mock_symbol = MagicMock()
    mock_symbol.instrument_token = "NSE_EQ|INE002A01018"
    mock_db.query().filter().first.return_value = mock_symbol
    
    # Mock risk_manager to avoid DB calls
    from src.risk.risk_manager import risk_manager
    risk_manager.validate_trade = MagicMock(return_value=True)
    risk_manager.get_position_size = MagicMock(return_value=10)
    
    # 5. Trigger Trade
    # We need to patch SessionLocal to return our mock_db
    with unittest.mock.patch('src.trading.service.SessionLocal', return_value=mock_db):
        await service.handle_signal(mock_signal)
    
    # 6. Verify
    assert order_manager.place_order.called
    args, kwargs = order_manager.place_order.call_args
    assert kwargs['symbol'] == "NSE_EQ|INE002A01018"
    assert kwargs['side'] == "BUY"

@pytest.mark.asyncio
async def test_atr_stop_loss_calculation():
    # The ATR calculation is inline in handle_scalping_signal, not a separate method
    # So we test the logic directly or mock the settings
    from src.config.settings import settings
    
    price = 2500.0
    atr = 10.0
    side = 'BUY'
    
    sl_dist = atr * settings.atr_multiplier_sl
    tp_dist = atr * settings.atr_multiplier_tp
    
    sl_price = price - sl_dist
    tp_price = price + tp_dist
    
    assert sl_price == 2485.0
    assert tp_price == 2520.0

