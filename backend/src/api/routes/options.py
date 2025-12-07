"""
Options Chain API Endpoints
REST API for querying options chains
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Optional, Union
from pydantic import BaseModel, field_validator

from ...data.options_service_v3 import get_options_service_v3
from ...config.logging import logger

router = APIRouter(prefix="/api/v1/options", tags=["options"])


# Response Models
class OptionContractResponse(BaseModel):
    """Single option contract"""
    tradingsymbol: str
    exchange_token: Optional[str] = None
    type: str  # "CE" or "PE"
    strike: float
    expiry: Union[str, int]  # Can be timestamp (int) or date string
    lot_size: int
    tick_size: float = 0.05
    segment: str = "NFO"
    
    @field_validator('expiry', mode='before')
    @classmethod
    def convert_expiry(cls, v):
        """Convert expiry to string if it's a number"""
        if isinstance(v, (int, float)):
            return str(int(v))
        return v


class OptionsChainResponse(BaseModel):
    """Options chain response"""
    symbol: str
    count: int
    expiry: Optional[Union[str, int]] = None
    options: List[OptionContractResponse]


class StrikesResponse(BaseModel):
    """Available strikes response"""
    symbol: str
    expiry: Optional[Union[str, int]] = None
    strikes: List[float]
    count: int


class ExpiriesResponse(BaseModel):
    """Available expiries response"""
    symbol: Optional[str] = None
    expiries: List[Union[str, int]]
    count: int
    
    @field_validator('expiries', mode='before')
    @classmethod
    def convert_expiries(cls, v):
        """Convert expiries to strings if they're numbers"""
        if isinstance(v, list):
            return [str(int(exp)) if isinstance(exp, (int, float)) else exp for exp in v]
        return v


class StatsResponse(BaseModel):
    """Service statistics"""
    initialized: bool
    last_updated: Optional[str]
    total_base_symbols: int
    total_option_contracts: int
    total_expiries: int


# Endpoints

@router.get("/chain/{symbol}", response_model=OptionsChainResponse)
async def get_options_chain(
    symbol: str,
    expiry: str = Query(None, description="Optional expiry date (YYYY-MM-DD)"),
    strike: float = Query(None, description="Optional strike price filter")
):
    """
    Get options chain for a symbol
    
    Args:
        symbol: Base symbol (e.g., RELIANCE, TCS, INFY)
        expiry: Optional expiry date (YYYY-MM-DD)
        strike: Optional strike price filter
    
    Returns:
        List of all available options for the symbol
    
    Example:
        GET /api/v1/options/chain/RELIANCE
        GET /api/v1/options/chain/RELIANCE?expiry=2025-12-25
        GET /api/v1/options/chain/RELIANCE?strike=1800
    """
    try:
        service = get_options_service_v3()
        
        if not service.is_initialized:
            raise HTTPException(
                status_code=503,
                detail="Options service not initialized. Please try again later."
            )
        
        # Get all options for the symbol
        options = service.get_chain_for_symbol(symbol, expiry=expiry)
        
        # Filter by strike if provided
        if strike is not None and options:
            options = [opt for opt in options if opt.get('strike') == strike]
        
        if not options:
            raise HTTPException(
                status_code=404,
                detail=f"No options found for {symbol}" +
                       (f" with expiry {expiry}" if expiry else "") +
                       (f" and strike {strike}" if strike else "")
            )
        
        # Convert to response model
        contracts = []
        for opt in options:
            contracts.append(OptionContractResponse(
                tradingsymbol=opt.get('tradingsymbol', ''),
                exchange_token=opt.get('exchange_token', ''),
                type=opt.get('type', ''),
                strike=float(opt.get('strike', 0)),
                expiry=opt.get('expiry', ''),
                lot_size=int(opt.get('lot_size', 1)),
            ))
        
        return OptionsChainResponse(
            symbol=symbol,
            expiry=expiry,
            count=len(contracts),
            options=contracts
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching options chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strikes/{symbol}", response_model=StrikesResponse)
async def get_available_strikes(
    symbol: str,
    expiry: str = Query(None, description="Optional expiry date filter")
):
    """
    Get all available strike prices for a symbol
    
    Args:
        symbol: Base symbol
        expiry: Optional expiry filter
    
    Returns:
        Sorted list of available strike prices
    
    Example:
        GET /api/v1/options/strikes/RELIANCE
        GET /api/v1/options/strikes/RELIANCE?expiry=2025-12-25
    """
    try:
        service = get_options_service_v3()
        
        if not service.is_initialized:
            raise HTTPException(status_code=503, detail="Service not initialized")
        
        strikes = service.get_available_strikes(symbol, expiry=expiry)
        
        if not strikes:
            raise HTTPException(
                status_code=404,
                detail=f"No strikes found for {symbol}"
            )
        
        return StrikesResponse(
            symbol=symbol,
            expiry=expiry,
            strikes=sorted(strikes),
            count=len(strikes)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching strikes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expiries", response_model=ExpiriesResponse)
async def get_available_expiries(
    symbol: str = Query(None, description="Optional symbol filter")
):
    """
    Get all available expiry dates
    
    Args:
        symbol: Optional symbol filter
    
    Returns:
        Sorted list of expiry dates (ISO format)
    
    Example:
        GET /api/v1/options/expiries
        GET /api/v1/options/expiries?symbol=RELIANCE
    """
    try:
        service = get_options_service_v3()
        
        if not service.is_initialized:
            raise HTTPException(status_code=503, detail="Service not initialized")
        
        expiries = service.get_available_expiries(symbol)
        
        if not expiries:
            raise HTTPException(
                status_code=404,
                detail=f"No expiries found" + (f" for {symbol}" if symbol else "")
            )
        
        # Convert expiries to strings and sort
        expiries_list = sorted([str(exp) if not isinstance(exp, str) else exp for exp in expiries])
        
        return ExpiriesResponse(
            symbol=symbol,
            expiries=expiries_list,
            count=len(expiries_list)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching expiries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_service_stats():
    """
    Get options service statistics
    
    Returns:
        Service initialization status and statistics
    
    Example:
        GET /api/v1/options/stats
    """
    try:
        service = get_options_service_v3()
        stats = service.get_stats()
        
        return StatsResponse(
            initialized=stats.get('initialized', False),
            last_updated=stats.get('last_updated'),
            total_base_symbols=stats.get('total_symbols', 0),
            total_option_contracts=stats.get('total_options', 0),
            total_expiries=stats.get('total_expiries', 0)
        )
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
