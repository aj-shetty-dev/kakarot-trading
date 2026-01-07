import logging
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from ..config.timezone import ist_now
from ..signals.ml_pipeline import ml_pipeline
from ..config.settings import settings
from ..data.database import SessionLocal
from ..data.models import Trade, Symbol
from ..config.constants import TradeStatus, OrderSide, OrderType

logger = logging.getLogger(__name__)

class PaperTradingManager:
    """
    Manages paper trades:
    - Tracks open positions.
    - Checks for SL/TP hits.
    - Calculates P&L.
    - Generates reports.
    - Persists trades to DB for EOD reporting.
    """
    def __init__(self):
        self.active_positions: Dict[str, Dict] = {} # symbol -> position_dict
        self.closed_trades: List[Dict] = []
        self.total_pnl = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        self._load_active_positions()

    def _load_active_positions(self):
        """Reload active paper trades from DB on startup (only TODAY's trades)"""
        db = SessionLocal()
        try:
            # Only load trades from TODAY (not stale from previous days)
            today_start = ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Check both "PAPER" and "SCALPING" types
            active_trades = db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN,
                Trade.trade_type.in_(["PAPER", "SCALPING"]),
                Trade.entry_time >= today_start  # Only TODAY's trades
            ).all()
            
            for trade in active_trades:
                # Find symbol name
                symbol = db.query(Symbol).filter(Symbol.id == trade.symbol_id).first()
                symbol_name = symbol.symbol if symbol else "UNKNOWN"
                
                self.active_positions[symbol_name] = {
                    'id': str(trade.id),
                    'entry_price': trade.entry_price,
                    'quantity': trade.quantity,
                    'side': trade.order_side,
                    'sl': trade.stop_loss_price,
                    'tp': trade.take_profit_price,
                    'entry_time': trade.entry_time
                }
            
            if active_trades:
                logger.info(f"💾 Loaded {len(active_trades)} active paper trades from today")
            else:
                logger.info(f"✅ No stale trades from previous runs")
        except Exception as e:
            logger.error(f"Error loading active paper trades: {e}")
        finally:
            db.close()

    def open_position(self, symbol: str, side: str, price: float, quantity: int, sl: float, tp: float, reason: str):
        """
        Open a new paper position and persist to DB.
        """
        if symbol in self.active_positions:
            logger.warning(f"⚠️ Already have an open paper position for {symbol}. Ignoring new signal.")
            return

        trade_id = uuid.uuid4()
        
        # Persist to DB
        db = SessionLocal()
        try:
            # Find symbol_id (handle underlying, option symbol, or instrument_key)
            symbol_obj = db.query(Symbol).filter(Symbol.symbol == symbol).first()
            
            if not symbol_obj:
                # Check if it's an option symbol or instrument_key
                from ..data.models import SubscribedOption
                opt = db.query(SubscribedOption).filter(
                    (SubscribedOption.symbol == symbol) | 
                    (SubscribedOption.option_symbol == symbol) |
                    (SubscribedOption.instrument_key == symbol)
                ).first()
                
                if opt:
                    # Link to the underlying symbol (e.g., NIFTY)
                    symbol_obj = db.query(Symbol).filter(Symbol.symbol == opt.symbol).first()
                
            if not symbol_obj:
                logger.error(f"❌ Symbol {symbol} not found in database. Cannot persist paper trade.")
                return

            new_trade = Trade(
                id=trade_id,
                symbol_id=symbol_obj.id,
                signal_id=None, # Scalping trades might not have a formal signal record yet
                order_side=OrderSide.BUY if side == 'BUY' else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity,
                entry_price=price,
                stop_loss_price=sl,
                take_profit_price=tp,
                status=TradeStatus.OPEN,
                trade_type="SCALPING",
                notes=f"{reason} | Symbol: {symbol}",
                trade_metadata={"instrument_key": symbol},
                entry_time=ist_now()
            )
            db.add(new_trade)
            db.commit()
            logger.info(f"💾 Paper trade {trade_id} persisted to DB")
        except Exception as e:
            logger.error(f"❌ Error persisting paper trade to DB: {e}")
            db.rollback()
        finally:
            db.close()

        position = {
            'id': trade_id,
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

    def _calculate_charges(self, entry_price: float, exit_price: float, quantity: int) -> float:
        """
        Calculate Upstox brokerage and taxes for a round-trip trade.
        """
        # 1. Brokerage (₹20 buy + ₹20 sell)
        brokerage = settings.brokerage_per_order * 2
        
        # 2. STT (0.05% on Sell side premium)
        sell_value = exit_price * quantity
        stt = sell_value * settings.stt_percent_sell
        
        # 3. Transaction Charges (NSE: 0.053% on total premium)
        total_turnover = (entry_price + exit_price) * quantity
        txn_charges = total_turnover * settings.txn_charges_percent
        
        # 4. GST (18% on Brokerage + Txn Charges)
        gst = (brokerage + txn_charges) * settings.gst_percent
        
        # 5. SEBI Charges (0.0001% on turnover)
        sebi = total_turnover * settings.sebi_charges_percent
        
        # 6. Stamp Duty (0.003% on Buy side)
        buy_value = entry_price * quantity
        stamp = buy_value * settings.stamp_duty_percent_buy
        
        total_charges = brokerage + stt + txn_charges + gst + sebi + stamp
        return total_charges

    def _close_position(self, symbol: str, exit_price: float, reason: str) -> str:
        """
        Close the position, calculate P&L, and update DB.
        """
        pos = self.active_positions.pop(symbol)
        trade_id = pos.get('id')
        entry_price = pos['entry_price']
        quantity = pos['quantity']
        side = pos['side']
        
        # Gross PnL
        gross_pnl = 0.0
        if side == 'BUY':
            gross_pnl = (exit_price - entry_price) * quantity
        else:
            gross_pnl = (entry_price - exit_price) * quantity
            
        # Calculate Charges
        charges = self._calculate_charges(entry_price, exit_price, quantity)
        net_pnl = gross_pnl - charges
        
        # Update DB
        if trade_id:
            db = SessionLocal()
            try:
                trade = db.query(Trade).filter(Trade.id == trade_id).first()
                if trade:
                    trade.exit_price = exit_price
                    trade.exit_time = ist_now()
                    trade.pnl = net_pnl
                    trade.commission = charges
                    trade.status = TradeStatus.CLOSED
                    trade.notes = f"{trade.notes} | Closed: {reason}"
                    db.commit()
                    logger.info(f"💾 Paper trade {trade_id} updated in DB")
            except Exception as e:
                logger.error(f"❌ Error updating paper trade in DB: {e}")
                db.rollback()
            finally:
                db.close()

        pos['exit_price'] = exit_price
        pos['exit_time'] = ist_now()
        pos['gross_pnl'] = gross_pnl
        pos['charges'] = charges
        pos['pnl'] = net_pnl
        pos['status'] = 'CLOSED'
        pos['exit_reason'] = reason
        
        self.closed_trades.append(pos)
        self.total_pnl += net_pnl
        
        if net_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
            
        # Update ML pipeline with outcome
        pnl_pct = (net_pnl / (entry_price * quantity)) * 100
        ml_pipeline.update_outcome(trade_id or symbol, pnl_pct)
            
        log_msg = (
            f"🏁 PAPER TRADE CLOSED ({reason})\n"
            f"Symbol: {symbol}\n"
            f"Exit Price: {exit_price:.2f}\n"
            f"Gross PnL: ₹{gross_pnl:.2f}\n"
            f"Charges: ₹{charges:.2f}\n"
            f"Net PnL: ₹{net_pnl:.2f}\n"
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

    def get_summary(self) -> str:
        """
        Get a summary of paper trading performance.
        If in-memory list is empty, try to load from DB for today.
        """
        closed_trades = self.closed_trades
        winning_trades = self.winning_trades
        losing_trades = self.losing_trades
        total_pnl = self.total_pnl

        # If empty (e.g. after restart), load from DB
        if not closed_trades:
            db = SessionLocal()
            try:
                from datetime import time
                today_start = datetime.combine(ist_now().date(), time.min)
                
                # Include both PAPER and SCALPING types, and all completed statuses
                COMPLETED_STATUSES = [
                    TradeStatus.CLOSED, 
                    TradeStatus.STOPPED_OUT, 
                    TradeStatus.TAKE_PROFIT, 
                    TradeStatus.TRAILING_SL
                ]
                
                db_trades = db.query(Trade).filter(
                    Trade.trade_type.in_(["PAPER", "SCALPING"]),
                    (Trade.created_at >= today_start) | (Trade.exit_time >= today_start),
                    Trade.status.in_(COMPLETED_STATUSES)
                ).all()
                
                if db_trades:
                    winning_trades = len([t for t in db_trades if (t.pnl or 0) > 0])
                    losing_trades = len(db_trades) - winning_trades
                    total_pnl = sum(t.pnl or 0 for t in db_trades)
                    # Create dummy closed_trades for calculation
                    closed_trades = [{"pnl": t.pnl, "commission": t.commission} for t in db_trades]
            except Exception as e:
                logger.error(f"Error loading paper trades from DB: {e}")
            finally:
                db.close()

        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_charges = sum(t.get('charges', t.get('commission', 0)) for t in closed_trades)
        total_gross = total_pnl + total_charges
        
        return (
            f"📊 PAPER TRADING SUMMARY\n"
            f"Gross PnL: ₹{total_gross:.2f}\n"
            f"Charges: ₹{total_charges:.2f}\n"
            f"Net PnL: ₹{total_pnl:.2f}\n"
            f"Trades: {total_trades} (W: {winning_trades} | L: {losing_trades})\n"
            f"Win Rate: {win_rate:.1f}%"
        )

paper_trading_manager = PaperTradingManager()
