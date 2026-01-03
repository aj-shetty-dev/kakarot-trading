"""
Order Manager - Handles Upstox API order placement and management
"""

import logging
import httpx
import asyncio
import time
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from ..config.settings import settings
from ..config.constants import OrderType, OrderSide, OrderStatus, TradeStatus
from ..data.models import Trade, Signal
from ..data.database import SessionLocal
from ..config.timezone import ist_now

logger = logging.getLogger(__name__)

class OrderManager:
    """
    Handles order execution via Upstox API
    """

    def __init__(self):
        self.base_url = "https://api.upstox.com/v2"
        self.headers = {
            "Authorization": f"Bearer {settings.upstox_access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Rate limiting
        self.order_timestamps = []
        self.rate_limit = settings.rate_limit_orders_per_minute

    def _check_rate_limit(self) -> bool:
        """
        Check if we are within the rate limit
        """
        now = time.time()
        # Remove timestamps older than 60 seconds
        self.order_timestamps = [t for t in self.order_timestamps if now - t < 60]
        
        if len(self.order_timestamps) >= self.rate_limit:
            logger.warning(f"⚠️ Rate limit reached: {self.rate_limit} orders/min. Blocking order.")
            return False
            
        self.order_timestamps.append(now)
        return True

    def _is_market_open(self) -> bool:
        """
        Check if market is currently open
        """
        now = ist_now()
        if now.weekday() >= 5: # Weekend
            return False
            
        open_h, open_m = map(int, settings.market_open_time.split(":"))
        close_h, close_m = map(int, settings.market_close_time.split(":"))
        
        market_open = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        market_close = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
        
        return market_open <= now < market_close

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        price: float = 0.0,
        trigger_price: float = 0.0
    ) -> Optional[str]:
        """
        Place an order on Upstox
        """
        # 1. Check Market Hours
        if not self._is_market_open():
            logger.error(f"❌ Order Denied: Market is CLOSED ({ist_now().strftime('%H:%M:%S')})")
            return None

        # 2. Check Rate Limit
        if not self._check_rate_limit():
            return None

        url = f"{self.base_url}/order/place"
        
        # Upstox API payload
        payload = {
            "quantity": quantity,
            "product": "I",  # Intraday
            "validity": "DAY",
            "price": price,
            "tag": "upstox-bot",
            "instrument_token": symbol,
            "order_type": order_type.value,
            "transaction_type": side.value,
            "disclosed_quantity": 0,
            "trigger_price": trigger_price,
            "is_amo": False
        }

        if settings.paper_trading_mode:
            logger.info(f"📝 [PAPER TRADING] Order Placed: {side} {quantity} {symbol} @ {price if price > 0 else 'MARKET'}")
            return f"paper_order_{ist_now().timestamp()}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers)
                data = response.json()
                
                if response.status_code == 200 and data.get("status") == "success":
                    order_id = data["data"]["order_id"]
                    logger.info(f"✅ Order Placed Successfully: {order_id}")
                    return order_id
                else:
                    logger.error(f"❌ Order Placement Failed: {data}")
                    return None
        except Exception as e:
            logger.error(f"❌ Exception during order placement: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order
        """
        if settings.paper_trading_mode:
            return True
            
        url = f"{self.base_url}/order/cancel"
        params = {"order_id": order_id}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(url, params=params, headers=self.headers)
                data = response.json()
                return response.status_code == 200 and data.get("status") == "success"
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

# Global instance
order_manager = OrderManager()
