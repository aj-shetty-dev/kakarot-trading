import pytest
from unittest.mock import MagicMock, patch
from src.signals.ml_pipeline import MLDataPipeline

@patch('src.signals.ml_pipeline.SessionLocal')
def test_log_features(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    # Mock symbol lookup
    mock_symbol = MagicMock()
    mock_symbol.id = "some-uuid"
    mock_db.query().filter().first.return_value = mock_symbol
    
    pipeline = MLDataPipeline()
    features = {"rsi": 65.0, "adx": 25.0}
    
    log_id = pipeline.log_features("RELIANCE", features, "BUY")
    
    assert mock_db.add.called
    assert mock_db.commit.called

@patch('src.signals.ml_pipeline.SessionLocal')
def test_update_outcome(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    # Mock log entry lookup
    mock_log = MagicMock()
    mock_db.query().filter().first.return_value = mock_log
    
    pipeline = MLDataPipeline()
    pipeline.update_outcome("trade-123", 0.02)
    
    assert mock_log.pnl_percent == 0.02
    assert mock_log.label == 1
    assert mock_db.commit.called
