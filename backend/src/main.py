"""
Main FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config.settings import settings
from .config.logging import logger, setup_logging
from .data.database import init_db
from .websocket.service import initialize_websocket_service, shutdown_websocket_service, get_websocket_service
from .data.options_service_v3 import initialize_options_service_v3
from .data.options_loader import load_options_at_startup

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage app lifecycle - startup and shutdown
    """
    # Startup
    logger.info("🚀 Upstox Trading Bot starting...")
    try:
        init_db()
        logger.info("✅ Database initialized")

        # Initialize options service for options chain data (Database-based V3)
        logger.info("📊 Initializing options chain service...")
        await initialize_options_service_v3()
        logger.info("✅ Options service initialized")

        # Load options at startup (fetch from API and store filtered ATM ± 1)
        logger.info("📋 Loading options at startup...")
        options_count = await load_options_at_startup()
        logger.info(f"✅ Options loaded: {options_count} subscribed options ready")

        # Initialize WebSocket service for real-time market data
        logger.info("📡 Initializing WebSocket service...")
        ws_service = await initialize_websocket_service()
        if ws_service:
            logger.info("✅ WebSocket service initialized")
        else:
            logger.warning("⚠️ WebSocket service failed to initialize")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Upstox Trading Bot shutting down...")
    try:
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


# ========== HEALTH CHECK ==========
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    ws_service = get_websocket_service()
    return {
        "status": "healthy",
        "environment": settings.environment,
        "paper_trading": settings.is_paper_trading,
        "websocket_connected": ws_service.is_healthy() if ws_service else False,
    }


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
