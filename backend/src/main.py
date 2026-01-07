"""
Main FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from .config.settings import settings
from .config.logging import logger, setup_logging
from .data.database import init_db
from .websocket.service import initialize_websocket_service, shutdown_websocket_service, get_websocket_service
from .data.options_service_v3 import initialize_options_service_v3
from .data.options_loader import load_options_at_startup
from .trading.session_manager import session_manager
from .trading.service import trading_service
from .notifications.telegram import get_telegram_service

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage app lifecycle - startup and shutdown
    """
    # Startup
    logger.info("🚀 Upstox Trading Bot starting...")
    
    # Send Telegram notification
    telegram = get_telegram_service(settings)
    from .config.auth_utils import get_token_expiry
    from .config.timezone import ist_now
    token_info = get_token_expiry(settings.upstox_access_token)
    
    token_status = "✅ Valid" if not token_info.get("expired") else "🚨 EXPIRED"
    time_left = token_info.get("time_left", "N/A")
    
    # Determine market status for startup message
    now = ist_now()
    open_h, open_m = map(int, settings.market_open_time.split(":"))
    close_h, close_m = map(int, settings.market_close_time.split(":"))
    market_open = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    market_close = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    
    if now.weekday() >= 5:
        market_status = "📅 Weekend (Closed)"
    elif now < market_open:
        market_status = f"💤 Closed (Opens at {settings.market_open_time})"
    elif now >= market_close:
        market_status = f"🔕 Closed (Closed at {settings.market_close_time})"
    else:
        market_status = "🔔 Open (Trading Active)"

    await telegram.send_message(
        f"🚀 <b>Upstox Trading Bot Starting</b>\n"
        f"Environment: <code>{settings.environment}</code>\n"
        f"Mode: <code>{'Paper Trading' if settings.paper_trading_mode else 'LIVE'}</code>\n"
        f"Market: <b>{market_status}</b>\n"
        f"Token: {token_status} ({time_left} left)"
    )

    try:
        init_db()
        logger.info("✅ Database initialized")

        # Initialize options service for options chain data (Database-based V3)
        logger.info("📊 Initializing options chain service...")
        await initialize_options_service_v3()
        logger.info("✅ Options service initialized")

        # Start position monitoring task (Always run to handle open positions)
        asyncio.create_task(trading_service.monitor_positions())
        logger.info("📈 Position monitoring started")

        # Start Market Session Manager (handles 9-3 schedule)
        if settings.auto_start_stop:
            logger.info("🕒 Starting Market Session Manager...")
            await session_manager.start_monitoring()
        else:
            # Manual mode: start everything now
            logger.info("📋 Manual mode: Loading options and starting WebSocket...")
            options_count = await load_options_at_startup()
            logger.info(f"✅ Options loaded: {options_count} subscribed options ready")
            
            ws_service = await initialize_websocket_service()
            if ws_service:
                logger.info("✅ WebSocket service initialized")
            else:
                logger.warning("⚠️ WebSocket service failed to initialize")
                await telegram.send_message("⚠️ <b>Warning:</b> WebSocket service failed to initialize during startup.")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        await telegram.send_message(f"❌ <b>CRITICAL: Startup Failed!</b>\nError: <code>{str(e)}</code>")
        raise

    yield

    # Shutdown
    logger.info("🛑 Upstox Trading Bot shutting down...")
    await telegram.send_message("🛑 <b>Upstox Trading Bot Shutting Down</b>")
    try:
        if settings.auto_start_stop:
            await session_manager.stop_monitoring()
            
        await shutdown_websocket_service()
        logger.info("✅ WebSocket service shutdown complete")
    except Exception as e:
        logger.error(f"Error during WebSocket shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Upstox Trading Bot API",
    description="Algorithmic trading system for Upstox with AI-powered signal detection",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== ROUTE REGISTRATION ==========
# Register options routes
from .api.routes import options as options_routes
app.include_router(options_routes.router)

# Register bracket routes
from .api.routes import brackets as brackets_routes
app.include_router(brackets_routes.router)

# Register bracket management routes
from .api.routes import bracket_management
app.include_router(bracket_management.router)

# Register verification routes
from .api.routes import verification
app.include_router(verification.router)

# Register monitoring routes
from .api.routes import monitoring
app.include_router(monitoring.router)


# ========== HEALTH CHECK ==========
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    Checks DB, Redis, and Upstox API connectivity
    """
    from .data.database import engine
    from sqlalchemy import text
    from .config.timezone import ist_now
    import httpx
    
    ws_service = get_websocket_service()
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "upstox_api": "unknown",
        "websocket": "connected" if ws_service and ws_service.is_healthy() else "disconnected",
        "timestamp": ist_now().isoformat()
    }
    
    # Check Database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
        
    # Check Upstox API (simple ping to public endpoint)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Use a public endpoint or one that doesn't require heavy auth for a ping
            response = await client.get("https://api.upstox.com/v2/market-quote/quotes", params={"symbol": "NSE_EQ|INE002A01018"})
            if response.status_code in [200, 401]: # 401 is fine, means API is up but we need auth
                health_status["upstox_api"] = "reachable"
            else:
                health_status["upstox_api"] = f"error: HTTP {response.status_code}"
    except Exception as e:
        health_status["upstox_api"] = f"error: {str(e)}"
        
    return health_status


@app.get("/")
async def root():
    """Root endpoint"""
    ws_service = get_websocket_service()
    return {
        "message": "Upstox Trading Bot API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running",
        "websocket_service": "active" if ws_service and ws_service.is_healthy() else "inactive"
    }


# ========== WEBSOCKET STATUS ENDPOINTS ==========

@app.get("/api/v1/websocket/status")
async def get_websocket_status():
    """Get WebSocket connection status"""
    ws_service = get_websocket_service()
    if not ws_service:
        return {"error": "WebSocket service not initialized"}, 503

    return ws_service.get_status()


@app.get("/api/v1/websocket/subscriptions")
async def get_subscriptions():
    """Get subscription details"""
    ws_service = get_websocket_service()
    if not ws_service or not ws_service.subscription_manager:
        return {"error": "WebSocket service not initialized"}, 503

    return {
        "status": ws_service.subscription_manager.get_subscription_status(),
        "subscribed_symbols": ws_service.subscription_manager.ws_client.get_subscribed_symbols()
    }


@app.get("/api/v1/websocket/latest-ticks")
async def get_latest_ticks():
    """Get latest tick data for all subscribed symbols"""
    from .websocket.handlers import get_aggregated_handler

    handler = get_aggregated_handler()
    if not handler:
        return {"error": "Handlers not initialized"}, 503

    return handler.get_stats()


# ========== PLACEHOLDER ROUTES (TO BE IMPLEMENTED) ===========

@app.get("/api/v1/symbols")
async def get_symbols():
    """Get list of tradeable symbols"""
    return {"message": "Symbols endpoint - to be implemented"}


@app.get("/api/v1/signals")
async def get_signals():
    """Get recent signals"""
    return {"message": "Signals endpoint - to be implemented"}


@app.get("/api/v1/trades")
async def get_trades():
    """Get trade history"""
    return {"message": "Trades endpoint - to be implemented"}


@app.get("/api/v1/positions")
async def get_positions():
    """Get current positions"""
    return {"message": "Positions endpoint - to be implemented"}


@app.get("/api/v1/account")
async def get_account():
    """Get account information"""
    return {"message": "Account endpoint - to be implemented"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower()
    )
