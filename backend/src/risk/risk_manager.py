"""
Risk Manager - Validates trades and manages position sizing
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from ..config.settings import settings
from ..config.constants import TradeStatus
from ..data.models import Trade, Symbol
from ..data.database import SessionLocal
from ..config.timezone import ist_now

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Handles risk validation for new trades:
    - Position sizing based on account risk
    - Daily loss limit checks
    - Max concurrent positions
    """

    def __init__(self):
        self.daily_loss_limit = settings.daily_loss_limit * settings.account_size
        logger.info(f"🛡️ RiskManager initialized. Daily Loss Limit: ₹{self.daily_loss_limit}")

    def get_position_size(self, price: float) -> int:
        """
        Calculate quantity based on risk per trade
        """
        # Risk ₹X per trade (e.g., 5% of account)
        risk_amount = settings.account_size * settings.risk_per_trade
        
        # For options, we usually buy in lots. 
        # This is a simplified version. In a real scenario, we'd fetch lot sizes.
        # For now, we use the position_size_percent setting.
        allocation = settings.account_size * settings.position_size_percent
        
        # Cap by max_position_size_inr
        allocation = min(allocation, settings.max_position_size_inr)
        
        quantity = int(allocation / price)
        return max(quantity, 1)

    def validate_trade(self, symbol_id: str, price: float) -> bool:
        """
        Check if a trade is allowed based on risk rules
        """
        db = SessionLocal()
        try:
            # 1. Check max concurrent positions
            active_trades = db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN
            ).count()
            
            if active_trades >= settings.max_concurrent_positions:
                logger.warning(f"🚫 Risk Denied: Max positions ({settings.max_concurrent_positions}) reached.")
                return False

            # 2. Check daily loss limit
            today_start = ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
            trades_today = db.query(Trade).filter(
                Trade.created_at >= today_start
            ).all()
            
            total_pnl = sum(t.pnl for t in trades_today if t.pnl is not None)
            if total_pnl <= -self.daily_loss_limit:
                logger.warning(f"🚫 Risk Denied: Daily loss limit (₹{self.daily_loss_limit}) reached. Total PnL: ₹{total_pnl}")
                return False

            # 3. Check if already in a position for this symbol
            existing = db.query(Trade).filter(
                Trade.symbol_id == symbol_id,
                Trade.status == TradeStatus.OPEN
            ).first()
            
            if existing:
                logger.warning(f"🚫 Risk Denied: Already have an open position for symbol_id {symbol_id}")
                return False

            return True
        except Exception as e:
            logger.error(f"Error in risk validation: {e}")
            return False
        finally:
            db.close()

# Global instance
risk_manager = RiskManager()
