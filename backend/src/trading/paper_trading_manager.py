import logging
from typing import Dict, List, Optional
from datetime import datetime
from ..config.timezone import ist_now
from ..signals.ml_pipeline import ml_pipeline

logger = logging.getLogger(__name__)

class PaperTradingManager:
    """
    Manages paper trades:
    - Tracks open positions.
    - Checks for SL/TP hits.
    - Calculates P&L.
    - Generates reports.
    """
    def __init__(self):
        self.active_positions: Dict[str, Dict] = {} # symbol -> position_dict
        self.closed_trades: List[Dict] = []
        self.total_pnl = 0.0
        self.winning_trades = 0
        self.losing_trades = 0

    def open_position(self, symbol: str, side: str, price: float, quantity: int, sl: float, tp: float, reason: str):
        """
        Open a new paper position.
        """
        if symbol in self.active_positions:
            logger.warning(f"⚠️ Already have an open paper position for {symbol}. Ignoring new signal.")
            return

        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': price,
            'quantity': quantity,
            'sl': sl,
            'tp': tp,
            'entry_time': ist_now(),
            'reason': reason,
            'status': 'OPEN'
        }
        self.active_positions[symbol] = position
        
        log_msg = (
            f"📝 PAPER TRADE OPENED ({side})\n"
            f"Symbol: {symbol}\n"
            f"Price: {price:.2f}\n"
            f"Qty: {quantity}\n"
            f"SL: {sl:.2f}\n"
            f"TP: {tp:.2f}\n"
            f"Reason: {reason}"
        )
        logger.info(f"\n{log_msg}\n")
        return log_msg

    def check_exits(self, symbol: str, current_price: float) -> Optional[str]:
        """
        Check if the current price hits SL or TP for an active position.
        Returns a log message if a trade is closed, else None.
        """
        if symbol not in self.active_positions:
            return None

        pos = self.active_positions[symbol]
        side = pos['side']
        sl = pos['sl']
        tp = pos['tp']
        
        exit_reason = None
        
        if side == 'BUY':
            if current_price <= sl:
                exit_reason = 'STOP LOSS'
            elif current_price >= tp:
                exit_reason = 'TAKE PROFIT'
        elif side == 'SELL':
            if current_price >= sl:
                exit_reason = 'STOP LOSS'
            elif current_price <= tp:
                exit_reason = 'TAKE PROFIT'
                
        if exit_reason:
            return self._close_position(symbol, current_price, exit_reason)
            
        return None

    def _close_position(self, symbol: str, exit_price: float, reason: str) -> str:
        """
        Close the position and calculate P&L.
        """
        pos = self.active_positions.pop(symbol)
        entry_price = pos['entry_price']
        quantity = pos['quantity']
        side = pos['side']
        
        pnl = 0.0
        if side == 'BUY':
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
            
        pos['exit_price'] = exit_price
        pos['exit_time'] = ist_now()
        pos['pnl'] = pnl
        pos['status'] = 'CLOSED'
        pos['exit_reason'] = reason
        
        self.closed_trades.append(pos)
        self.total_pnl += pnl
        
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
            
        # Update ML pipeline with outcome
        pnl_pct = (pnl / (entry_price * quantity)) * 100
        ml_pipeline.update_outcome(pos.get('trade_id', symbol), pnl_pct)
            
        log_msg = (
            f"🏁 PAPER TRADE CLOSED ({reason})\n"
            f"Symbol: {symbol}\n"
            f"Exit Price: {exit_price:.2f}\n"
            f"PnL: ₹{pnl:.2f}\n"
            f"Total PnL: ₹{self.total_pnl:.2f}"
        )
        logger.info(f"\n{log_msg}\n")
        return log_msg

    def square_off_all(self) -> List[str]:
        """
        Close all active positions immediately.
        Used at market close.
        """
        messages = []
        symbols = list(self.active_positions.keys())
        
        if not symbols:
            return ["No active paper positions to square off."]
            
        for symbol in symbols:
            # We don't have the latest price here, so we use the last known price 
            # or entry price as fallback. In reality, this is called when a tick arrives.
            # But for a forced square off, we'll use the entry price if no tick is available.
            pos = self.active_positions[symbol]
            current_price = pos.get('last_price', pos['entry_price'])
            msg = self._close_position(symbol, current_price, "MARKET CLOSE SQUARE-OFF")
            messages.append(msg)
            
        return messages
            
        self.total_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
            
        pos['exit_price'] = exit_price
        pos['exit_time'] = ist_now()
        pos['pnl'] = pnl
        pos['exit_reason'] = reason
        pos['status'] = 'CLOSED'
        
        self.closed_trades.append(pos)
        
        log_msg = (
            f"🏁 PAPER TRADE CLOSED ({side})\n"
            f"Symbol: {symbol}\n"
            f"Exit Price: {exit_price:.2f}\n"
            f"PnL: ₹{pnl:.2f}\n"
            f"Reason: {reason}"
        )
        logger.info(f"\n{log_msg}\n")
        return log_msg

    def get_summary(self) -> str:
        """
        Get a summary of paper trading performance.
        """
        total_trades = self.winning_trades + self.losing_trades
        win_rate = (self.winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return (
            f"📊 PAPER TRADING SUMMARY\n"
            f"Total PnL: ₹{self.total_pnl:.2f}\n"
            f"Trades: {total_trades} (W: {self.winning_trades} | L: {self.losing_trades})\n"
            f"Win Rate: {win_rate:.1f}%"
        )

paper_trading_manager = PaperTradingManager()
