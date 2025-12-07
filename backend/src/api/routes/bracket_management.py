"""
Bracket Management Endpoints
Auto-subscribe to bracket options and manage selections
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List
from pydantic import BaseModel

from ...data.bracket_subscription_service import (
    get_bracket_subscription_service,
    initialize_bracket_service
)
from ...websocket.handlers import get_aggregated_handler
from ...config.logging import logger

router = APIRouter(prefix="/api/v1/bracket-management", tags=["bracket-management"])


class BracketInitRequest(BaseModel):
    """Request to initialize bracket subscriptions"""
    symbol_prices: Dict[str, float]  # e.g., {"RELIANCE": 1250, "TCS": 3500}


class BracketInitResponse(BaseModel):
    """Response after initializing brackets"""
    status: str
    brackets_selected: int
    total_options: int
    upstox_symbols: List[str]


class BracketStatsResponse(BaseModel):
    """Bracket service statistics"""
    initialized: bool
    total_symbols: int
    brackets_selected: int
    total_options: int


@router.post("/auto-init")
async def auto_init_brackets_from_websocket() -> BracketInitResponse:
    """
    Auto-initialize bracket options using current prices from WebSocket
    
    This endpoint:
    1. Gets current prices from WebSocket tick data
    2. Selects bracket options (PE above, CE below price) for each symbol
    3. Returns the Upstox symbols for subscription
    
    Returns:
        Selected bracket options and symbols for WebSocket subscription
    
    Example:
        POST /api/v1/bracket-management/auto-init
        Response: {
            "status": "success",
            "brackets_selected": 208,
            "total_options": 416,
            "upstox_symbols": ["NSE_FO|RELIANCE 1300 PE 30 DEC 25", ...]
        }
    """
    try:
        # Get current prices from WebSocket
        handler = get_aggregated_handler()
        if not handler:
            raise HTTPException(
                status_code=503,
                detail="WebSocket handler not initialized"
            )
        
        # Get latest ticks
        stats = handler.get_stats()
        current_prices = {}
        
        if "latest_ticks" in stats:
            for symbol, tick_data in stats["latest_ticks"].items():
                if "ltp" in tick_data:
                    # Extract base symbol (remove NSE_EQ| prefix if present)
                    base_symbol = symbol.replace("NSE_EQ|", "")
                    current_prices[base_symbol] = tick_data["ltp"]
        
        if not current_prices:
            raise HTTPException(
                status_code=400,
                detail="No current prices available from WebSocket"
            )
        
        logger.info(f"📊 Got current prices for {len(current_prices)} symbols")
        
        # Initialize bracket service with current prices
        success = await initialize_bracket_service(current_prices)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize bracket service"
            )
        
        # Get bracket symbols for WebSocket subscription
        service = get_bracket_subscription_service()
        upstox_symbols = service.get_bracket_upstox_symbols()
        stats = service.get_bracket_stats()
        
        return BracketInitResponse(
            status="success",
            brackets_selected=stats["brackets_selected"],
            total_options=stats["total_options"],
            upstox_symbols=upstox_symbols
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing brackets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-init")
async def manual_init_brackets(request: BracketInitRequest) -> BracketInitResponse:
    """
    Manually initialize bracket options with provided prices
    
    Args:
        request: Dict of symbol -> current price mappings
    
    Returns:
        Selected bracket options and symbols
    
    Example:
        POST /api/v1/bracket-management/manual-init
        Body: {
            "symbol_prices": {
                "RELIANCE": 1250,
                "TCS": 3500,
                "INFY": 2800
            }
        }
    """
    try:
        if not request.symbol_prices:
            raise HTTPException(
                status_code=400,
                detail="symbol_prices required"
            )
        
        logger.info(f"🎯 Initializing brackets for {len(request.symbol_prices)} symbols...")
        
        # Initialize bracket service
        success = await initialize_bracket_service(request.symbol_prices)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize bracket service"
            )
        
        # Get bracket symbols for WebSocket subscription
        service = get_bracket_subscription_service()
        upstox_symbols = service.get_bracket_upstox_symbols()
        stats = service.get_bracket_stats()
        
        logger.info(f"✅ Selected {stats['brackets_selected']} bracket options")
        
        return BracketInitResponse(
            status="success",
            brackets_selected=stats["brackets_selected"],
            total_options=stats["total_options"],
            upstox_symbols=upstox_symbols
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing brackets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_bracket_stats() -> BracketStatsResponse:
    """
    Get bracket service statistics
    
    Returns:
        Current bracket selection stats
    """
    try:
        service = get_bracket_subscription_service()
        stats = service.get_bracket_stats()
        
        return BracketStatsResponse(
            initialized=stats["initialized"],
            total_symbols=stats["total_symbols"],
            brackets_selected=stats["brackets_selected"],
            total_options=stats["total_options"]
        )
    
    except Exception as e:
        logger.error(f"Error getting bracket stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upstox-symbols")
async def get_upstox_symbols() -> Dict:
    """
    Get all bracket symbols in Upstox format (for WebSocket subscription)
    
    Returns:
        List of symbols ready for WebSocket subscription
    
    Example:
        GET /api/v1/bracket-management/upstox-symbols
        Response: {
            "count": 416,
            "upstox_symbols": ["NSE_FO|RELIANCE 1300 PE 30 DEC 25", ...]
        }
    """
    try:
        service = get_bracket_subscription_service()
        
        if not service.is_initialized:
            raise HTTPException(
                status_code=400,
                detail="Bracket service not initialized. Call /auto-init or /manual-init first"
            )
        
        upstox_symbols = service.get_bracket_upstox_symbols()
        
        return {
            "count": len(upstox_symbols),
            "upstox_symbols": upstox_symbols
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting upstox symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))
