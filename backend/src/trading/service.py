"""
Trading Service - Orchestrates trade execution and management
"""

import logging
import asyncio
import uuid
import pandas as pd
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ..config.logging import logger
from ..config.settings import settings
from ..config.constants import OrderSide, OrderType, TradeStatus, SignalStatus
from ..data.models import Trade, Signal, Symbol
from ..data.database import SessionLocal
from ..risk.risk_manager import risk_manager
from ..trading.order_manager import order_manager
from ..config.timezone import ist_now
from ..notifications.telegram import get_telegram_service
from .candle_manager import candle_manager
from .indicators import IndicatorCalculator
from .strategy import ScalpingStrategy
from .paper_trading_manager import paper_trading_manager
from ..signals.ml_pipeline import ml_pipeline

class TradingService:
    """
    Manages the lifecycle of trades:
    - Entry based on signals
    - Risk validation
    - SL/TP management
    - Trailing stops
    """

    def __init__(self):
        self.telegram = get_telegram_service(settings)
        # Register for candle updates
        candle_manager.register_callback(self.on_candle_close)
        logger.info("🚀 TradingService initialized")

    def on_candle_close(self, symbol: str, timeframe: str, candle: Dict):
        """
        Callback when a candle closes.
        """
        if timeframe != '1m':
            return

        # Handle exits and price updates synchronously (fast)
        current_price = candle['close']
        
        # 1. Update current_price for open trades
        self._update_trade_price(symbol, current_price)
        
        # 2. Check Exits (fast)
        exit_msg = paper_trading_manager.check_exits(symbol, current_price)
        if exit_msg and self.telegram:
            asyncio.create_task(self.telegram.send_message(f"🏁 <b>PAPER TRADE CLOSED</b>\n<pre>{exit_msg}</pre>"))
            
        # 3. Check Entries (slow, offload to background)
        # Use cached symbol ID
        from .candle_manager import candle_manager
        symbol_id = candle_manager.symbol_id_cache.get(symbol)
        
        # Get history (must be done here to get a snapshot)
        df = candle_manager.get_candles(symbol, timeframe)
        
        min_required = max(settings.ema_trend, settings.volume_ma_period, 50) + 1
        if len(df) >= min_required:
            asyncio.create_task(self.process_strategy(symbol, df, current_price, symbol_id))

    def _update_trade_price(self, symbol: str, price: float):
        """Update price for open trades in DB"""
        db = SessionLocal()
        try:
            # symbol passed here is the instrument_key
            # We want to update all open trades that match this instrument_key
            
            # Filter in Python if there are few trades, or use JSON query
            open_trades = db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN
            ).all()
            
            updated = False
            for trade in open_trades:
                trade_inst_key = None
                if trade.trade_metadata:
                    trade_inst_key = trade.trade_metadata.get('instrument_key')
                
                if trade_inst_key == symbol:
                    trade.current_price = price
                    
                    # Also update P&L percent for live tracking
                    if trade.entry_price and trade.entry_price > 0:
                        if trade.order_side == OrderSide.BUY:
                            trade.pnl_percent = ((price - trade.entry_price) / trade.entry_price) * 100
                        else: # SELL
                            trade.pnl_percent = ((trade.entry_price - price) / trade.entry_price) * 100
                            
                    updated = True
            
            if updated:
                db.commit()
        except Exception as e:
            logger.error(f"Error updating trade prices for {symbol}: {e}")
            db.rollback()
        finally:
            db.close()

    async def process_strategy(self, symbol: str, df: pd.DataFrame, price: float, symbol_id: Optional[str] = None):
        """
        Asynchronously process strategy indicators and check for signals
        """
        try:
            # Calculate indicators (CPU heavy)
            df = IndicatorCalculator.calculate_indicators(df)
            
            # Check signal
            signal_data = ScalpingStrategy.check_signal(df)
            
            if signal_data:
                logger.info(f"🚀 SCALPING SIGNAL for {symbol}: {signal_data['side']} | {signal_data['reason']}")
                
                # Handle signal
                await self.handle_scalping_signal(symbol, signal_data, price, symbol_id)
                
                # Log features for ML training
                try:
                    features = df.iloc[-1].to_dict()
                    features = {k: v for k, v in features.items() if isinstance(v, (int, float))}
                    ml_pipeline.log_features(
                        symbol=symbol,
                        features=features,
                        signal_type=signal_data['side']
                    )
                except Exception as ml_e:
                    logger.error(f"Error logging ML features: {ml_e}")
                    
        except Exception as e:
            logger.error(f"Error processing strategy for {symbol}: {e}")

    async def handle_scalping_signal(self, symbol: str, signal_data: Dict, price: float, symbol_id: Optional[str] = None):
        """
        Handle a scalping signal (Paper Trading for now)
        """
        if not settings.scalping_enabled:
            return

        # Risk Validation
        if symbol_id and not risk_manager.validate_trade(symbol_id, price):
            return

        side = signal_data['side']
        reason = signal_data['reason']
        atr = signal_data.get('atr', 0)
        
        # Calculate SL/TP
        # Use ATR for dynamic SL/TP if available, else fallback to fixed percent
        if atr > 0:
            # Typical scalping: SL = multiplier * ATR
            sl_dist = atr * settings.atr_multiplier_sl
            tp_dist = atr * settings.atr_multiplier_tp
            
            if side == 'BUY':
                sl_price = price - sl_dist
                tp_price = price + tp_dist
            else: # SELL
                sl_price = price + sl_dist
                tp_price = price - tp_dist
        else:
            sl_pct = settings.scalping_stop_loss_percent
            tp_pct = settings.scalping_take_profit_percent
            
            if side == 'BUY':
                sl_price = price * (1 - sl_pct)
                tp_price = price * (1 + tp_pct)
            else: # SELL
                sl_price = price * (1 + sl_pct)
                tp_price = price * (1 - tp_pct)
            
        # Calculate Quantity
        capital = settings.scalping_capital_allocation
        quantity = int(capital / price)
        
        if quantity <= 0:
            logger.warning(f"⚠️ Insufficient capital for scalping {symbol} at {price}")
            return

        # Open Paper Trade via Manager
        log_msg = paper_trading_manager.open_position(
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            sl=sl_price,
            tp=tp_price,
            reason=f"{reason}"
        )
        
        if log_msg and self.telegram:
            await self.telegram.send_message(f"🧪 <b>PAPER TRADE OPENED</b>\n<pre>{log_msg}</pre>")

    async def handle_signal(self, signal_id: uuid.UUID):
        """
        Process a new signal and execute trade if valid
        """
        db = SessionLocal()
        try:
            # Re-fetch signal to avoid DetachedInstanceError in async task
            signal = db.query(Signal).filter(Signal.id == signal_id).first()
            if not signal:
                logger.warning(f"⚠️ Signal {signal_id} not found in handle_signal")
                return

            # 1. Risk Validation
            if not risk_manager.validate_trade(signal.symbol_id, signal.price_at_signal):
                return

            # 2. Calculate Position Size
            quantity = risk_manager.get_position_size(signal.price_at_signal)
            
            # 3. Determine Side (For now, we only do BUY for scalping)
            # In a real scenario, we'd check if it's a CE or PE signal
            side = OrderSide.BUY
            
            # Get symbol details for instrument token
            symbol = db.query(Symbol).filter(Symbol.id == signal.symbol_id).first()
            if not symbol or not symbol.instrument_token:
                logger.error(f"❌ Symbol {signal.symbol_id} not found or missing instrument_token")
                return

            order_id = await order_manager.place_order(
                symbol=symbol.instrument_token,
                side=side,
                quantity=quantity,
                order_type=OrderType.MARKET
            )

            if order_id:
                # 4. Create Trade Record
                # Calculate SL/TP
                sl_price = signal.price_at_signal * (1 - settings.stop_loss_percent)
                tp_price = signal.price_at_signal * (1 + settings.take_profit_percent)
                
                # Get instrument key from signal metadata
                instrument_key = signal.signal_metadata.get('instrument_key', symbol.instrument_token)

                trade = Trade(
                    signal_id=signal.id,
                    symbol_id=signal.symbol_id,
                    order_side=side,
                    status=TradeStatus.OPEN,
                    trade_type="PAPER" if settings.paper_trading_mode else "LIVE",
                    trade_metadata={"instrument_key": instrument_key},
                    quantity=quantity,
                    entry_price=signal.price_at_signal,
                    current_price=signal.price_at_signal,
                    stop_loss_price=sl_price,
                    trailing_stop_price=sl_price,
                    take_profit_price=tp_price,
                    upstox_order_id=order_id,
                    entry_time=ist_now()
                )
                db.add(trade)
                
                # Update signal status
                signal.status = SignalStatus.EXECUTED
                db.add(signal) # Use add/commit for re-attached signal
                
                db.commit()
                
                logger.info(f"💰 LIVE TRADE OPENED: {symbol.symbol} | Qty: {quantity} | Entry: {trade.entry_price} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")

                if self.telegram:
                    await self.telegram.send_message(
                        f"🚀 <b>LIVE TRADE OPENED</b>\n"
                        f"Symbol: {symbol.symbol}\n"
                        f"Price: {signal.price_at_signal}\n"
                        f"Qty: {quantity}\n"
                        f"SL: {sl_price:.2f} | TP: {tp_price:.2f}"
                    )
        except Exception as e:
            logger.error(f"Error in handle_signal: {e}")
            db.rollback()
        finally:
            db.close()

    async def monitor_positions(self):
        """
        Background task to monitor open positions and manage SL/TP for LIVE and PAPER trades.
        (Scalping paper trades are handled separately in on_candle_close).
        
        Features:
        - Uses live WebSocket prices when available
        - Falls back to cached prices if WebSocket is down
        - Logs warnings when using stale data
        """
        from ..websocket.client import get_websocket_client
        
        while True:
            db = SessionLocal()
            try:
                open_trades = db.query(Trade).filter(
                    Trade.status == TradeStatus.OPEN,
                    Trade.trade_type.in_(["LIVE", "PAPER"])
                ).all()
                
                ws_client = get_websocket_client()
                
                for trade in open_trades:
                    # Get current price from WebSocket or use cached fallback
                    current_price = trade.current_price
                    price_age = None
                    using_fallback = False
                    
                    # Try to get fresh price from cache if WebSocket is active
                    if ws_client and ws_client.is_connected:
                        cached_price = ws_client.get_cached_price(trade.symbol)
                        if cached_price:
                            current_price = cached_price
                            price_age = ws_client.get_price_freshness(trade.symbol)
                    else:
                        # WebSocket is down, use cached price if available
                        if ws_client:
                            cached_price = ws_client.get_cached_price(trade.symbol)
                            if cached_price:
                                current_price = cached_price
                                price_age = ws_client.get_price_freshness(trade.symbol)
                                using_fallback = True
                                
                                # Warn if price is getting stale
                                if price_age > 30:  # 30 seconds
                                    logger.warning(
                                        f"[FALLBACK] Using stale price for {trade.symbol}: "
                                        f"₹{current_price} ({price_age:.0f}s old)"
                                    )
                    
                    # Skip if critical prices are missing
                    # Use stop_loss_price as fallback for trailing_stop_price
                    sl_threshold = trade.trailing_stop_price or trade.stop_loss_price
                    
                    if not current_price or not trade.take_profit_price or not sl_threshold:
                        continue
                    
                    # Update current price in database
                    if current_price != trade.current_price:
                        trade.current_price = current_price
                        db.commit()
                    
                    # 1. Check Take Profit
                    if current_price >= trade.take_profit_price:
                        logger.info(
                            f"✅ [TP] {trade.symbol}: Price ₹{current_price} >= TP ₹{trade.take_profit_price} "
                            f"{'(FALLBACK)' if using_fallback else ''}"
                        )
                        await self.close_trade(trade, TradeStatus.TAKE_PROFIT, db)
                        
                    # 2. Check Stop Loss
                    elif current_price <= sl_threshold:
                        logger.warning(
                            f"❌ [SL] {trade.symbol}: Price ₹{current_price} <= SL ₹{sl_threshold} "
                            f"{'(FALLBACK)' if using_fallback else ''}"
                        )
                        await self.close_trade(trade, TradeStatus.STOPPED_OUT, db)
                        
                    # 3. Update Trailing Stop
                    else:
                        # If price moves up, move trailing stop up
                        # Only update if current price is above entry
                        if current_price > trade.entry_price:
                            new_trailing_sl = current_price * (1 - settings.trailing_stop_percent)
                            # Ensure we have a trailing_stop_price to compare against
                            current_trailing = trade.trailing_stop_price or trade.stop_loss_price
                            if current_trailing is not None and new_trailing_sl > current_trailing:
                                trade.trailing_stop_price = new_trailing_sl
                                db.commit()
                            
            except Exception as e:
                logger.error(f"Error in position monitoring: {e}")
            finally:
                db.close()
                
            await asyncio.sleep(1) # Check every second

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

    async def close_trade(self, trade: Trade, reason: TradeStatus, db: Session):
        """
        Close an open trade
        """
        symbol = db.query(Symbol).filter(Symbol.id == trade.symbol_id).first()
        
        # Place exit order (SELL if we were BUY)
        exit_side = OrderSide.SELL if trade.order_side == OrderSide.BUY else OrderSide.BUY
        
        order_id = await order_manager.place_order(
            symbol=symbol.instrument_token,
            side=exit_side,
            quantity=trade.quantity,
            order_type=OrderType.MARKET
        )
        
        if order_id:
            trade.status = reason
            trade.exit_price = trade.current_price
            trade.exit_time = ist_now()
            trade.upstox_exit_order_id = order_id
            
            # Calculate Gross PnL
            gross_pnl = 0.0
            if trade.order_side == OrderSide.BUY:
                gross_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
            else:
                gross_pnl = (trade.entry_price - trade.exit_price) * trade.quantity
                
            # Calculate Charges
            charges = self._calculate_charges(trade.entry_price, trade.exit_price, trade.quantity)
            trade.commission = charges
            trade.pnl = gross_pnl - charges
            trade.pnl_percent = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
            
            db.commit()
            
            logger.info(f"🏁 TRADE CLOSED: {symbol.symbol} | Reason: {reason} | Net PnL: ₹{trade.pnl:.2f} ({trade.pnl_percent:.2f}%)")
            
            await self.telegram.send_message(
                f"🏁 <b>Trade Closed</b>\n"
                f"Symbol: <code>{symbol.symbol}</code>\n"
                f"Reason: <code>{reason}</code>\n"
                f"Gross PnL: <code>₹{gross_pnl:.2f}</code>\n"
                f"Charges: <code>₹{charges:.2f}</code>\n"
                f"Net PnL: <b>₹{trade.pnl:.2f}</b> ({trade.pnl_percent:.2f}%)"
            )

    async def square_off_all(self):
        """
        Square off all open positions (Live and Paper)
        """
        logger.info("🚨 SQUARING OFF ALL POSITIONS...")
        
        # 1. Square off Paper Trades
        try:
            paper_msgs = paper_trading_manager.square_off_all()
            for msg in paper_msgs:
                logger.info(f"Paper Square-off: {msg}")
                if self.telegram:
                    try:
                        await self.telegram.send_message(f"🏁 <b>PAPER SQUARE-OFF</b>\n<pre>{msg}</pre>")
                    except Exception as tel_err:
                        logger.error(f"Telegram error during paper square-off: {tel_err}")
        except Exception as e:
            logger.error(f"Error during paper square-off: {e}")
        
        # 2. Square off Live Trades
        db = SessionLocal()
        try:
            open_trades = db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN,
                Trade.trade_type == "LIVE"
            ).all()
            if not open_trades:
                logger.info("No open live trades to square off.")
                return

            for trade in open_trades:
                try:
                    await self.close_trade(trade, TradeStatus.CLOSED, db)
                except Exception as trade_err:
                    logger.error(f"Error closing trade {trade.id}: {trade_err}")
        except Exception as e:
            logger.error(f"Error during live square-off: {e}")
        finally:
            db.close()

# Global instance
trading_service = TradingService()
