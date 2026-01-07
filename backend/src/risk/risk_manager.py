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

    def _get_current_equity(self, db: Session) -> float:
        """Calculate current total equity (Initial + All-time PnL)"""
        # Calculate total P&L from all completed trades
        from ..config.constants import TradeStatus
        COMPLETED_STATUSES = [
            TradeStatus.CLOSED, 
            TradeStatus.STOPPED_OUT, 
            TradeStatus.TAKE_PROFIT, 
            TradeStatus.TRAILING_SL
        ]
        total_pnl = db.query(Trade.pnl).filter(
            Trade.status.in_(COMPLETED_STATUSES)
        ).all()
        cumulative_pnl = sum(p[0] for p in total_pnl if p[0] is not None)
        return settings.account_size + cumulative_pnl

    def __init__(self):
        # Initial settings based on starting account size
        self.daily_loss_limit = settings.daily_loss_limit * settings.account_size
        self.daily_profit_target = settings.daily_profit_target * settings.account_size
        logger.info(f"🛡️ RiskManager initialized. Daily Loss Limit: ₹{self.daily_loss_limit} | Profit Target: ₹{self.daily_profit_target}")

    def get_position_size(self, price: float) -> int:
        """
        Calculate quantity based on risk per trade using CURRENT equity
        """
        db = SessionLocal()
        try:
            equity = self._get_current_equity(db)
            
            # Risk % of CURRENT equity
            risk_amount = equity * settings.risk_per_trade
            
            # Allocation based on CURRENT equity
            allocation = equity * settings.position_size_percent
            
            # Cap by max_position_size_inr
            allocation = min(allocation, settings.max_position_size_inr)
            
            quantity = int(allocation / price)
            return max(quantity, 1)
        finally:
            db.close()

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
            
            # Dynamic limits based on starting equity of the day
            current_equity = self._get_current_equity(db)
            daily_loss_limit = current_equity * settings.daily_loss_limit
            daily_profit_target = current_equity * settings.daily_profit_target
            
            # Check Loss Limit
            if total_pnl <= -daily_loss_limit:
                logger.warning(f"🚫 Risk Denied: Daily loss limit (₹{daily_loss_limit:,.2f}) reached. Total PnL: ₹{total_pnl:,.2f}")
                return False
                
            # Check Profit Target (Optional: Stop trading if target reached)
            if total_pnl >= daily_profit_target:
                logger.warning(f"🚫 Risk Denied: Daily profit target (₹{daily_profit_target:,.2f}) reached. Total PnL: ₹{total_pnl:,.2f}")
                return False

            # 3. Check daily trade limit
            if len(trades_today) >= settings.max_trades_per_day:
                logger.warning(f"🚫 Risk Denied: Daily trade limit ({settings.max_trades_per_day}) reached.")
                return False

            # 4. Check if already in a position for this symbol
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
