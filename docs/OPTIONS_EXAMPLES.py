"""
Options Chain - Practical Working Examples
Real code you can use immediately
"""

# ==============================================================================
# EXAMPLE 1: Initialize the service at app startup
# ==============================================================================

# File: backend/src/main.py

from fastapi import FastAPI
from src.data.options_service import initialize_options_service
from src.api.routes import options as options_routes
from src.config.logging import logger

app = FastAPI()

# Include options routes
app.include_router(options_routes.router)


@app.on_event("startup")
async def startup_event():
    """Initialize services at startup"""
    logger.info("🚀 Starting up...")
    
    # Initialize options chain service
    logger.info("Initializing options chain service...")
    success = await initialize_options_service()
    if success:
        logger.info("✅ Options service ready")
    else:
        logger.warning("⚠️  Options service failed to initialize")


# ==============================================================================
# EXAMPLE 2: Query options in your trading logic
# ==============================================================================

from src.data.options_service import get_options_service
from src.websocket.client import websocket_client

async def setup_options_subscription(base_symbol: str, price: float):
    """Subscribe to ATM options for a symbol"""
    
    service = get_options_service()
    
    # Get ATM chain (±3 strikes)
    atm_options = service.get_atm_chain(
        base_symbol=base_symbol,
        current_price=price,
        num_strikes=3
    )
    
    logger.info(f"Found {len(atm_options)} ATM options for {base_symbol}")
    
    # Convert to WebSocket format
    ws_symbols = [f"NSE_FO|{opt['tradingsymbol']}" for opt in atm_options]
    
    # Subscribe
    success = await websocket_client.subscribe(ws_symbols, mode="full")
    
    if success:
        logger.info(f"✅ Subscribed to {len(ws_symbols)} options")
        # Return list of subscribed trading symbols for reference
        return [opt['tradingsymbol'] for opt in atm_options]
    else:
        logger.error("Failed to subscribe to options")
        return []


# ==============================================================================
# EXAMPLE 3: Show options chain to user (REST API)
# ==============================================================================

# Usage:
# curl http://localhost:8000/api/v1/options/chain/RELIANCE
# curl http://localhost:8000/api/v1/options/chain/RELIANCE?expiry=2025-12-25

# Python example:
import httpx

async def fetch_options_for_display():
    """Fetch options chain and format for display"""
    
    async with httpx.AsyncClient() as client:
        # Get specific expiry
        response = await client.get(
            "http://localhost:8000/api/v1/options/chain/RELIANCE",
            params={"expiry": "2025-12-25"}
        )
        
        data = response.json()
        
        # Format as table
        print(f"\n{data['symbol']} Options Chain ({data['expiry']})")
        print("=" * 50)
        print(f"{'Strike':<10} {'Call':<20} {'Put':<20}")
        print("-" * 50)
        
        # Group by strike
        by_strike = {}
        for option in data['options']:
            strike = option['strike']
            if strike not in by_strike:
                by_strike[strike] = {}
            by_strike[strike][option['type']] = option
        
        # Display
        for strike in sorted(by_strike.keys()):
            call = by_strike[strike].get('CE', {})
            put = by_strike[strike].get('PE', {})
            
            call_sym = call.get('tradingsymbol', '')
            put_sym = put.get('tradingsymbol', '')
            
            print(f"{strike:<10.0f} {call_sym:<20} {put_sym:<20}")


# ==============================================================================
# EXAMPLE 4: Find the best strike to trade
# ==============================================================================

async def find_liquid_strikes(
    base_symbol: str,
    current_price: float,
    num_strikes: int = 5
):
    """Find liquid strikes nearest to current price"""
    
    service = get_options_service()
    
    # Get ATM chain
    chain = service.get_atm_chain(base_symbol, current_price, num_strikes=num_strikes)
    
    if not chain:
        logger.error(f"No options found for {base_symbol}")
        return []
    
    # Group by strike and type
    result = []
    current_strike = None
    
    for option in chain:
        strike = option['strike']
        
        if strike != current_strike:
            if current_strike is not None:
                result.append("\n")
            current_strike = strike
            distance = ((strike - current_price) / current_price) * 100
            marker = " <-- ATM" if abs(distance) < 0.5 else ""
            result.append(f"Strike: {strike:.0f} ({distance:+.2f}%){marker}")
        
        result.append(f"  {option['type']}: {option['tradingsymbol']}")
    
    for line in result:
        print(line)
    
    return chain


# ==============================================================================
# EXAMPLE 5: Get all available expiries for planning
# ==============================================================================

async def show_available_expirations(base_symbol: str):
    """Show all available expiry dates with option counts"""
    
    service = get_options_service()
    
    # Get all expiries for this symbol
    expiries = service.get_available_expiries(base_symbol)
    
    print(f"\n{base_symbol} - Available Expirations:")
    print("=" * 60)
    print(f"{'Expiry Date':<15} {'Strike Prices':<15} {'Total Options':<15}")
    print("-" * 60)
    
    for expiry in expiries:
        # Count options for this expiry
        chain = service.get_chain_for_symbol(base_symbol, expiry=expiry)
        strikes = service.get_available_strikes(base_symbol, expiry=expiry)
        
        from datetime import datetime
        exp_date = datetime.strptime(expiry, "%Y-%m-%d")
        days_to_exp = (exp_date.date() - datetime.now().date()).days
        
        print(f"{expiry:<15} {len(strikes):<15} {len(chain):<15} ({days_to_exp} days)")


# ==============================================================================
# EXAMPLE 6: Use in spike detection (finding call spreads)
# ==============================================================================

async def setup_call_spread(
    base_symbol: str,
    long_strike: float,
    short_strike: float,
    expiry: str
):
    """Set up a call spread (buy lower strike, sell higher strike)"""
    
    service = get_options_service()
    
    # Get specific contracts
    long_symbol = service.get_chain_for_symbol(
        base_symbol, 
        expiry=expiry, 
        strike=long_strike
    )
    
    short_symbol = service.get_chain_for_symbol(
        base_symbol,
        expiry=expiry,
        strike=short_strike
    )
    
    # Filter for calls only
    long_call = [o for o in long_symbol if o['type'] == 'CE'][0]
    short_call = [o for o in short_symbol if o['type'] == 'CE'][0]
    
    logger.info(f"Call Spread Setup:")
    logger.info(f"  Long:  {long_call['tradingsymbol']} @ {long_strike}")
    logger.info(f"  Short: {short_call['tradingsymbol']} @ {short_strike}")
    logger.info(f"  Max Profit: {(short_strike - long_strike) * 100}")  # 100 per contract
    
    # Subscribe to both
    ws_symbols = [
        f"NSE_FO|{long_call['tradingsymbol']}",
        f"NSE_FO|{short_call['tradingsymbol']}"
    ]
    
    await websocket_client.subscribe(ws_symbols, mode="full")
    
    return {
        "long_call": long_call,
        "short_call": short_call,
        "ws_symbols": ws_symbols
    }


# ==============================================================================
# EXAMPLE 7: Check service status
# ==============================================================================

import json

async def show_service_status():
    """Display options service status and statistics"""
    
    import httpx
    
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/v1/options/stats")
        stats = response.json()
    
    print("\n📊 Options Service Status")
    print("=" * 60)
    print(f"✅ Initialized: {stats['initialized']}")
    print(f"📅 Last Updated: {stats['last_updated']}")
    print(f"📈 Base Symbols: {stats['total_base_symbols']}")
    print(f"📋 Total Contracts: {stats['total_option_contracts']}")
    print(f"🗓️  Available Expiries: {stats['total_expiries']}")
    print("\nNext Expiries:")
    for expiry in stats['available_expiries'][:3]:
        print(f"  - {expiry}")


# ==============================================================================
# EXAMPLE 8: Stream live options data
# ==============================================================================

async def stream_options_data(base_symbol: str, expiry: str):
    """Stream live tick data for options"""
    
    service = get_options_service()
    
    # Get all options for expiry
    chain = service.get_chain_for_symbol(base_symbol, expiry=expiry)
    
    # Subscribe to all of them
    ws_symbols = [f"NSE_FO|{opt['tradingsymbol']}" for opt in chain]
    
    await websocket_client.subscribe(ws_symbols, mode="full")
    
    logger.info(f"Streaming {len(ws_symbols)} options for {base_symbol} ({expiry})")
    
    # Listen for updates (in your message handler)
    # When ticks arrive, they'll include IV and Greeks data


# ==============================================================================
# EXAMPLE 9: Integration with FastAPI endpoint
# ==============================================================================

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ATMSubscriptionRequest(BaseModel):
    symbol: str
    price: float
    num_strikes: int = 3
    subscribe_websocket: bool = True

@router.post("/trading/setup-atm-options")
async def setup_atm_options(request: ATMSubscriptionRequest):
    """
    Set up ATM options trading for a symbol
    
    POST /trading/setup-atm-options
    {
        "symbol": "RELIANCE",
        "price": 1800.0,
        "num_strikes": 3,
        "subscribe_websocket": true
    }
    """
    
    service = get_options_service()
    
    # Get ATM chain
    chain = service.get_atm_chain(
        request.symbol,
        request.price,
        num_strikes=request.num_strikes
    )
    
    if not chain:
        return {"error": "No options found"}
    
    # Optionally subscribe
    if request.subscribe_websocket:
        ws_symbols = [f"NSE_FO|{opt['tradingsymbol']}" for opt in chain]
        await websocket_client.subscribe(ws_symbols, mode="full")
    
    return {
        "symbol": request.symbol,
        "count": len(chain),
        "options": [
            {
                "symbol": opt['tradingsymbol'],
                "type": opt['type'],
                "strike": opt['strike'],
                "expiry": opt['expiry']
            }
            for opt in chain
        ]
    }


# ==============================================================================
# USAGE EXAMPLES - Copy & Paste Ready
# ==============================================================================

"""
# 1. Initialize at startup (in main.py)
await initialize_options_service()

# 2. Get full chain via API
curl http://localhost:8000/api/v1/options/chain/RELIANCE

# 3. Get ATM chain via API
curl "http://localhost:8000/api/v1/options/atm/RELIANCE?price=1800&num_strikes=5"

# 4. Get strikes via API
curl http://localhost:8000/api/v1/options/strikes/RELIANCE

# 5. Get expiries via API
curl "http://localhost:8000/api/v1/options/expiries?symbol=RELIANCE"

# 6. Get service status
curl http://localhost:8000/api/v1/options/stats

# 7. Set up ATM subscription via endpoint
curl -X POST http://localhost:8000/trading/setup-atm-options \
  -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE","price":1800,"num_strikes":3}'
"""
