"""
WebSocket Service - Main orchestrator for real-time data
Coordinates WebSocket client, subscriptions, and handlers
"""

import asyncio
from typing import Optional

from ..config.logging import websocket_logger as logger
from .client import UpstoxWebSocketClient, initialize_websocket, shutdown_websocket, get_websocket_client
from .subscription_manager import SubscriptionManager, initialize_subscription_manager, get_subscription_manager
from .handlers import initialize_handlers, process_tick


class WebSocketService:
    """Main service for WebSocket data streaming"""

    def __init__(self):
        """Initialize WebSocket service"""
        self.ws_client: Optional[UpstoxWebSocketClient] = None
        self.subscription_manager: Optional[SubscriptionManager] = None
        self.is_running = False
        self.listen_task: Optional[asyncio.Task] = None

    async def start(self) -> bool:
        """
        Start WebSocket service
        
        Returns:
            bool: True if started successfully
        """
        try:
            logger.info("🚀 Starting WebSocket Service...")

            # Initialize WebSocket client
            self.ws_client = await initialize_websocket()
            if not self.ws_client:
                logger.error("Failed to initialize WebSocket client")
                return False

            # Initialize subscription manager
            self.subscription_manager = await initialize_subscription_manager(self.ws_client)
            if not self.subscription_manager:
                logger.error("Failed to initialize subscription manager")
                return False

            # Initialize message handlers
            await initialize_handlers()

            # Register tick handler with WebSocket client
            self.ws_client.register_handler(process_tick)

            # Subscribe to all FNO symbols
            logger.info("📡 Fetching and subscribing to live FNO universe...")
            if self.subscription_manager.all_symbols:
                if await self.subscription_manager.subscribe_to_universe():
                    logger.info(f"✅ Subscribed to {len(self.subscription_manager.all_symbols)} FNO symbols (live from API)")
                else:
                    logger.warning("Some subscriptions failed, will retry...")
            else:
                logger.warning("⚠️ No FNO symbols found from API to subscribe")

            # Start listening for messages
            if self.ws_client and self.ws_client.is_connected:
                self.listen_task = asyncio.create_task(self.ws_client.listen())
                self.is_running = True
                logger.info("✅ WebSocket Service started successfully")
                return True
            else:
                logger.error("WebSocket not connected after initialization")
                return False

        except Exception as e:
            logger.error(f"❌ Error starting WebSocket service: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def stop(self) -> None:
        """Stop WebSocket service"""
        try:
            logger.info("🛑 Stopping WebSocket Service...")

            if self.listen_task:
                self.listen_task.cancel()
                try:
                    await self.listen_task
                except asyncio.CancelledError:
                    pass

            await shutdown_websocket()

            self.is_running = False
            logger.info("✅ WebSocket Service stopped")

        except Exception as e:
            logger.error(f"Error stopping WebSocket service: {e}")

    async def subscribe_symbol(self, symbol: str) -> bool:
        """
        Subscribe to a specific symbol
        
        Args:
            symbol: Symbol to subscribe
        
        Returns:
            bool: True if successful
        """
        if not self.subscription_manager:
            logger.error("Subscription manager not initialized")
            return False

        return await self.subscription_manager.subscribe_to_symbols([symbol])

    async def unsubscribe_symbol(self, symbol: str) -> bool:
        """
        Unsubscribe from a specific symbol
        
        Args:
            symbol: Symbol to unsubscribe
        
        Returns:
            bool: True if successful
        """
        if not self.subscription_manager:
            logger.error("Subscription manager not initialized")
            return False

        return await self.subscription_manager.unsubscribe_from_symbols([symbol])

    def get_status(self) -> dict:
        """
        Get current service status
        
        Returns:
            dict: Service status information
        """
        status = {
            "is_running": self.is_running,
            "websocket_connected": self.ws_client.is_connected if self.ws_client else False,
            "subscriptions": None,
            "subscribed_symbols": []
        }

        if self.subscription_manager:
            status["subscriptions"] = self.subscription_manager.get_subscription_status()
            status["subscribed_symbols"] = self.subscription_manager.ws_client.get_subscribed_symbols()

        return status

    def is_healthy(self) -> bool:
        """Check if service is healthy"""
        return self.is_running and self.ws_client and self.ws_client.is_connected


# Global WebSocket service instance
websocket_service: Optional[WebSocketService] = None


async def initialize_websocket_service() -> WebSocketService:
    """Initialize global WebSocket service"""
    global websocket_service

    try:
        websocket_service = WebSocketService()
        if await websocket_service.start():
            return websocket_service
        else:
            logger.error("Failed to start WebSocket service")
            return None

    except Exception as e:
        logger.error(f"Error initializing WebSocket service: {e}")
        return None


async def shutdown_websocket_service() -> None:
    """Shutdown global WebSocket service"""
    global websocket_service

    if websocket_service:
        await websocket_service.stop()
        websocket_service = None


def get_websocket_service() -> Optional[WebSocketService]:
    """Get global WebSocket service instance"""
    return websocket_service
