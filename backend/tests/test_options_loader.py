import pytest
import json
import gzip
from unittest.mock import MagicMock, AsyncMock, patch
from src.data.options_loader import OptionsLoaderService

@pytest.mark.asyncio
async def test_fetch_all_option_contracts_from_master():
    # 1. Setup Mock Data
    mock_instruments = [
        {
            "segment": "NSE_FO",
            "instrument_type": "CE",
            "underlying_symbol": "RELIANCE",
            "trading_symbol": "RELIANCE26JAN2500CE",
            "instrument_key": "NSE_FO|12345",
            "strike_price": 2500.0,
            "expiry": 1737849600000, # ms timestamp
            "lot_size": 250
        },
        {
            "segment": "NSE_EQ", # Should be filtered out
            "instrument_type": "EQUITY",
            "underlying_symbol": "RELIANCE",
            "trading_symbol": "RELIANCE-EQ"
        }
    ]
    
    compressed_content = gzip.compress(json.dumps(mock_instruments).encode('utf-8'))
    
    # 2. Mock httpx
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = compressed_content
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        service = OptionsLoaderService()
        result = await service.fetch_all_option_contracts_from_master()
        
        # 3. Verify
        assert "RELIANCE" in result
        assert len(result["RELIANCE"]) == 1
        assert result["RELIANCE"][0]["trading_symbol"] == "RELIANCE26JAN2500CE"
        assert result["RELIANCE"][0]["instrument_type"] == "CE"

@pytest.mark.asyncio
async def test_fetch_all_option_contracts_retry_logic():
    # Mock failure then success
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.content = gzip.compress(json.dumps([]).encode('utf-8'))
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_response_fail, mock_response_success]
        
        with patch('asyncio.sleep', new_callable=AsyncMock): # Skip backoff delay
            service = OptionsLoaderService()
            result = await service.fetch_all_option_contracts_from_master()
            
            assert mock_get.call_count == 2
            assert result == {} # Empty list in mock success
