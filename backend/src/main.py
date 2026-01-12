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
from .notifications.telegram import get_telegram_service

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage app lifecycle - startup and shutdown
    """
    # Startup
    logger.info("🚀 Kakarot Trading Bot starting...")
    
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
        market_status = "🔔 Open (Active)"

    await telegram.send_message(
        f"🚀 <b>Tick Collection Service Starting</b>\n"
        f"Environment: <code>{settings.environment}</code>\n"
        f"Market: <b>{market_status}</b>\n"
        f"Token: {token_status} ({time_left} left)"
    )

    try:
        init_db()
        logger.info("✅ Database initialized")

        # Start WebSocket Service (includes subscription management)
        ws_service = await initialize_websocket_service()
        if ws_service:
            logger.info("✅ WebSocket service initialized for data collection")
        else:
            logger.warning("⚠️ WebSocket service failed to initialize")
            await telegram.send_message("⚠️ <b>Warning:</b> WebSocket service failed to initialize.")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        await telegram.send_message(f"❌ <b>CRITICAL: Startup Failed!</b>\nError: <code>{str(e)}</code>")
        raise

    yield

    # Shutdown
    logger.info("🛑 Kakarot Trading Bot shutting down...")
    await telegram.send_message("🛑 <b>Kakarot Trading Bot Shutting Down</b>")
    try:
        await shutdown_websocket_service()
        logger.info("✅ WebSocket service shutdown complete")
    except Exception as e:
        logger.error(f"Error during WebSocket shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Kakarot Trading Bot API",
    description="Tick collection and automated data management system",
    version="1.0.0",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower()
    )
