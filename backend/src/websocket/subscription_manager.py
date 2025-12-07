"""
WebSocket Subscription Manager
Manages symbol subscriptions and maintains state
"""

import asyncio
from typing import List, Set, Optional

from ..config.settings import settings
from ..config.logging import websocket_logger as logger
from ..data.fno_fetcher import get_fno_symbols
from ..data.models import SubscribedOption
from ..data.database import SessionLocal
from .client import UpstoxWebSocketClient


class SubscriptionManager:
    """Manages WebSocket symbol subscriptions"""

    def __init__(self, ws_client: UpstoxWebSocketClient):
        """
        Initialize subscription manager
        
        Args:
            ws_client: UpstoxWebSocketClient instance
        """
        self.ws_client = ws_client
        self.all_symbols: Set[str] = set()
        self.subscribed_symbols: Set[str] = set()
        self.failed_subscriptions: Set[str] = set()
        self.subscription_batch_size = 50  # Subscribe in batches

    async def load_fno_universe(self) -> Set[str]:
        """
        Load FNO universe - loads INSTRUMENT KEYS from SubscribedOption table
        These are the proper format for Upstox V3 WebSocket: NSE_FO|12345
        
        Returns:
            Set of instrument keys (e.g., NSE_FO|60965, NSE_FO|60966)
        """
        try:
            logger.info("🔄 Loading instrument keys from SubscribedOption table...")
            
            # Get subscribed options from database
            db = SessionLocal()
            try:
                options = db.query(SubscribedOption).all()
                
                # Extract INSTRUMENT KEYS (not option_symbol!) - this is the correct format
                # Upstox V3 WebSocket expects: NSE_FO|60965 format
                instrument_keys = [opt.instrument_key for opt in options if opt.instrument_key]
                self.all_symbols = set(instrument_keys)
                
                logger.info(f"✅ Loaded {len(self.all_symbols)} option contracts from database")
                logger.info(f"   Format: instrument_key (e.g., NSE_FO|60965)")
                logger.info(f"   Sample keys: {list(self.all_symbols)[:3]}")
                
                return self.all_symbols
                
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error loading option symbols from database: {e}")
            
            # Fallback: Load base FNO symbols from API if database is empty
            logger.warning("⚠️  Fallback: Loading base FNO symbols from API...")
            try:
                symbols_list = await get_fno_symbols()
                self.all_symbols = set(symbols_list)
                logger.info(f"✅ Fallback: Loaded {len(self.all_symbols)} base FNO symbols from API")
                return self.all_symbols
            except Exception as api_error:
                logger.error(f"Fallback also failed: {api_error}")
                return set()

    async def subscribe_to_universe(self) -> bool:
        """
        Subscribe to all option contracts in the FNO universe
        
        Returns:
            bool: True if all subscriptions successful
        """
        if not self.all_symbols:
            logger.error("Option universe is empty. Load it first.")
            return False

        logger.info(f"🔄 Subscribing to {len(self.all_symbols)} option contracts (ATM ± 1)...")
        
        # Subscribe in batches to avoid overwhelming the API
        symbols_list = list(self.all_symbols)
        total_batches = (len(symbols_list) + self.subscription_batch_size - 1) // self.subscription_batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * self.subscription_batch_size
            end_idx = min(start_idx + self.subscription_batch_size, len(symbols_list))
            
            batch = symbols_list[start_idx:end_idx]
            
            logger.info(f"📦 Subscribing batch {batch_num + 1}/{total_batches} ({len(batch)} option contracts)...")
            
            success = await self.ws_client.subscribe(batch, mode="full")
            
            if success:
                self.subscribed_symbols.update(batch)
            else:
                self.failed_subscriptions.update(batch)
                logger.warning(f"Failed to subscribe to batch {batch_num + 1}")
            
            # Small delay between batches
            await asyncio.sleep(0.5)

        logger.info(f"✅ Subscription complete. Subscribed: {len(self.subscribed_symbols)}, "
                   f"Failed: {len(self.failed_subscriptions)}")
        
        return len(self.failed_subscriptions) == 0

    async def subscribe_to_symbols(self, symbols: List[str]) -> bool:
        """
        Subscribe to specific symbols
        
        Args:
            symbols: List of symbols to subscribe
        
        Returns:
            bool: True if subscription successful
        """
        logger.info(f"Subscribing to: {symbols}")
        
        success = await self.ws_client.subscribe(symbols, mode="full")
        
        if success:
            self.subscribed_symbols.update(symbols)
            return True
        else:
            self.failed_subscriptions.update(symbols)
            return False

    async def unsubscribe_from_symbols(self, symbols: List[str]) -> bool:
        """
        Unsubscribe from specific symbols
        
        Args:
            symbols: List of symbols to unsubscribe
        
        Returns:
            bool: True if unsubscription successful
        """
        logger.info(f"Unsubscribing from: {symbols}")
        
        success = await self.ws_client.unsubscribe(symbols)
        
        if success:
            for symbol in symbols:
                self.subscribed_symbols.discard(symbol)
            return True
        else:
            return False

    async def retry_failed_subscriptions(self) -> bool:
        """
        Retry failed subscriptions
        
        Returns:
            bool: True if all retries successful
        """
        if not self.failed_subscriptions:
            logger.info("No failed subscriptions to retry")
            return True

        failed_list = list(self.failed_subscriptions)
        logger.info(f"🔄 Retrying {len(failed_list)} failed subscriptions...")
        
        success = await self.ws_client.subscribe(failed_list, mode="full")
        
        if success:
            self.subscribed_symbols.update(failed_list)
            self.failed_subscriptions.clear()
            logger.info("✅ All failed subscriptions retried successfully")
            return True
        else:
            logger.warning(f"Some subscriptions still failing: {failed_list}")
            return False

    def get_subscription_status(self) -> dict:
        """Get current subscription status"""
        return {
            "total_symbols": len(self.all_symbols),
            "subscribed": len(self.subscribed_symbols),
            "failed": len(self.failed_subscriptions),
            "subscription_rate": f"{(len(self.subscribed_symbols) / max(len(self.all_symbols), 1)) * 100:.1f}%"
        }

    def is_symbol_subscribed(self, symbol: str) -> bool:
        """Check if symbol is subscribed"""
        return symbol in self.subscribed_symbols


# Global subscription manager instance
subscription_manager: Optional[SubscriptionManager] = None


async def initialize_subscription_manager(ws_client: UpstoxWebSocketClient) -> SubscriptionManager:
    """Initialize global subscription manager and fetch FNO universe"""
    global subscription_manager
    
    try:
        subscription_manager = SubscriptionManager(ws_client)
        
        # Load FNO universe from Upstox API (live)
        await subscription_manager.load_fno_universe()
        
        logger.info("✅ Subscription manager initialized with live FNO universe")
        return subscription_manager
        
    except Exception as e:
        logger.error(f"Error initializing subscription manager: {e}")
        return None


def get_subscription_manager() -> Optional[SubscriptionManager]:
    """Get global subscription manager instance"""
    return subscription_manager
