import pytest
from unittest.mock import MagicMock, patch
from src.risk.risk_manager import RiskManager
from src.config.settings import Settings
from src.config.constants import TradeStatus

@pytest.fixture
def mock_settings():
    s = Settings(
        upstox_api_key="test",
        upstox_api_secret="test",
        upstox_access_token="test",
        account_size=100000,
        risk_per_trade=0.05,
        position_size_percent=0.1,
        max_position_size_inr=15000,
        max_concurrent_positions=3,
        daily_loss_limit=0.02
    )
    return s

def test_position_sizing(mock_settings):
    with patch('src.risk.risk_manager.settings', mock_settings):
        rm = RiskManager()
        # Allocation = 100,000 * 0.1 = 10,000
        # Price = 100 -> Quantity = 100
        assert rm.get_position_size(100.0) == 100
        
        # Allocation = 100,000 * 0.1 = 10,000
        # Price = 2000 -> Quantity = 5
        assert rm.get_position_size(2000.0) == 5

def test_position_sizing_cap(mock_settings):
    mock_settings.max_position_size_inr = 5000
    with patch('src.risk.risk_manager.settings', mock_settings):
        rm = RiskManager()
        # Allocation = min(10,000, 5,000) = 5,000
        # Price = 100 -> Quantity = 50
        assert rm.get_position_size(100.0) == 50

@patch('src.risk.risk_manager.SessionLocal')
def test_validate_trade_max_positions(mock_session_local, mock_settings):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    # Mock 3 active trades
    mock_db.query().filter().count.return_value = 3
    
    with patch('src.risk.risk_manager.settings', mock_settings):
        rm = RiskManager()
        assert rm.validate_trade("some-uuid", 100.0) is False

@patch('src.risk.risk_manager.SessionLocal')
def test_validate_trade_already_open(mock_session_local, mock_settings):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    # Mock 0 active trades total
    mock_db.query().filter().count.return_value = 0
    # Mock 0 daily pnl
    mock_db.query().filter().all.return_value = []
    # Mock existing trade for this symbol
    mock_db.query().filter().filter().first.return_value = MagicMock()
    
    with patch('src.risk.risk_manager.settings', mock_settings):
        rm = RiskManager()
        assert rm.validate_trade("some-uuid", 100.0) is False
