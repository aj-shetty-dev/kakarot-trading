"""
Bracket Options API Endpoints
API for selecting and managing bracketing options (PE above, CE below price)
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Union
from pydantic import BaseModel

from ...data.bracket_selector import get_bracket_selector
from ...config.logging import logger

router = APIRouter(prefix="/api/v1/brackets", tags=["brackets"])


# Response Models
class OptionDetail(BaseModel):
    """Option contract detail"""
    tradingsymbol: str
    exchange_token: int
    type: str
    strike: float
    expiry: Union[str, int]
    lot_size: int
    tick_size: float
    segment: str


class BracketSelection(BaseModel):
    """Selected bracket options (PE above, CE below price)"""
    symbol: str
    price: float
    expiry: Union[str, int]
    pe: OptionDetail  # Put option (above price)
    ce: OptionDetail  # Call option (below price)


class BracketResponse(BaseModel):
    """Response for bracket selection"""
    symbol: str
    price: float
    expiry: Union[str, int]
    pe: OptionDetail
    ce: OptionDetail
    upstox_symbols: List[str]  # For WebSocket subscription


class AllBracketsResponse(BaseModel):
    """Response for all bracket options"""
    count: int
    total_symbols: int
    brackets: List[BracketResponse]
    all_upstox_symbols: List[str]


# Endpoints

@router.post("/select/{symbol}")
async def select_bracket(
    symbol: str,
    price: float = Query(..., description="Current LTP/price of the symbol"),
    expiry: Optional[str] = Query(None, description="Optional expiry (uses nearest if not provided)")
) -> BracketResponse:
    """
    Select bracketing PE and CE options for a symbol at a given price
    
    PE (Put): Closest strike ABOVE the current price
    CE (Call): Closest strike BELOW the current price
    
    Args:
        symbol: Base symbol (e.g., RELIANCE, TCS)
        price: Current LTP/market price
        expiry: Optional expiry date (uses nearest if not provided)
    
    Returns:
        Selected PE and CE options
    
    Example:
        POST /api/v1/brackets/select/RELIANCE?price=1250
        Response: {
            "symbol": "RELIANCE",
            "price": 1250.0,
            "pe": {"tradingsymbol": "RELIANCE 1300 PE 30 DEC 25", ...},
            "ce": {"tradingsymbol": "RELIANCE 1200 CE 30 DEC 25", ...},
            "upstox_symbols": ["NSE_FO|RELIANCE 1300 PE 30 DEC 25", ...]
        }
    """
    try:
        selector = get_bracket_selector()
        
        bracket = selector.select_bracket_options(symbol, price, expiry)
        
        if not bracket:
            raise HTTPException(
                status_code=404,
                detail=f"Could not find bracket options for {symbol} at price {price}"
            )
        
        # Get Upstox format symbols for WebSocket
        upstox_symbols = [
            f"NSE_FO|{bracket['pe']['tradingsymbol']}",
            f"NSE_FO|{bracket['ce']['tradingsymbol']}"
        ]
        
        return BracketResponse(
            symbol=bracket["symbol"],
            price=bracket["price"],
            expiry=bracket["expiry"],
            pe=OptionDetail(**bracket["pe"]),
            ce=OptionDetail(**bracket["ce"]),
            upstox_symbols=upstox_symbols
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting bracket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def get_all_brackets() -> AllBracketsResponse:
    """
    Get all currently selected bracket options
    
    Returns:
        All bracket selections stored in memory
    """
    try:
        selector = get_bracket_selector()
        
        brackets = selector.get_bracket_symbols()
        upstox_symbols = selector.get_bracket_upstox_symbols()
        
        bracket_responses = [
            BracketResponse(
                symbol=b["symbol"],
                price=b["price"],
                expiry=b["expiry"],
                pe=OptionDetail(**b["pe"]),
                ce=OptionDetail(**b["ce"]),
                upstox_symbols=[
                    f"NSE_FO|{b['pe']['tradingsymbol']}",
                    f"NSE_FO|{b['ce']['tradingsymbol']}"
                ]
            )
            for b in brackets
        ]
        
        return AllBracketsResponse(
            count=len(bracket_responses),
            total_symbols=len(bracket_responses),
            brackets=bracket_responses,
            all_upstox_symbols=upstox_symbols
        )
    
    except Exception as e:
        logger.error(f"Error getting all brackets: {e}")
        raise HTTPException(status_code=500, detail=str(e))
