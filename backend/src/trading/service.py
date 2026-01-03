"""
Trading Service - Orchestrates trade execution and management
"""

import logging
import asyncio
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
        # We only care about 1m candles for now
        if timeframe != '1m':
            return

        try:
            current_price = candle['close']
            
            # 1. Check Exits for existing paper trades
            exit_msg = paper_trading_manager.check_exits(symbol, current_price)
            if exit_msg:
                # Send Telegram for exit
                if self.telegram:
                    asyncio.create_task(self.telegram.send_message(f"🏁 <b>PAPER TRADE CLOSED</b>\n<pre>{exit_msg}</pre>"))
            
            # 2. Check Entries
            # Get history
            df = candle_manager.get_candles(symbol, timeframe)
            
            if len(df) < 22: # Not enough data
                return
                
            # Calculate indicators
            df = IndicatorCalculator.calculate_indicators(df)
            
            # Check signal
            signal_data = ScalpingStrategy.check_signal(df)
            
            if signal_data:
                logger.info(f"🚀 SCALPING SIGNAL for {symbol}: {signal_data['side']} | {signal_data['reason']}")
                
                # Log features for ML training
                features = df.iloc[-1].to_dict()
                # Remove non-numeric or redundant columns for ML
                features = {k: v for k, v in features.items() if isinstance(v, (int, float))}
                
                ml_pipeline.log_features(
                    symbol=symbol,
                    features=features,
                    signal_type=signal_data['side']
                )
                
                # Handle signal asynchronously
                asyncio.create_task(self.handle_scalping_signal(symbol, signal_data, current_price))
                
        except Exception as e:
            logger.error(f"Error in TradingService.on_candle_close: {e}")

    async def handle_scalping_signal(self, symbol: str, signal_data: Dict, price: float):
        """
        Handle a scalping signal (Paper Trading for now)
        """
        if not settings.scalping_enabled:
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
            reason=reason
        )
        
        if log_msg and self.telegram:
            await self.telegram.send_message(f"🧪 <b>PAPER TRADE OPENED</b>\n<pre>{log_msg}</pre>")

    async def handle_signal(self, signal: Signal):
        """
        Process a new signal and execute trade if valid
        """
        # 1. Risk Validation
        if not risk_manager.validate_trade(signal.symbol_id, signal.price_at_signal):
            return

        # 2. Calculate Position Size
        quantity = risk_manager.get_position_size(signal.price_at_signal)
        
        # 3. Determine Side (For now, we only do BUY for scalping)
        # In a real scenario, we'd check if it's a CE or PE signal
        side = OrderSide.BUY
        
        # 4. Place Order
        db = SessionLocal()
        try:
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
                # 5. Create Trade Record
                # Calculate SL/TP
                sl_price = signal.price_at_signal * (1 - settings.stop_loss_percent)
                tp_price = signal.price_at_signal * (1 + settings.take_profit_percent)
                
                trade = Trade(
                    signal_id=signal.id,
                    symbol_id=signal.symbol_id,
                    order_side=side,
                    status=TradeStatus.OPEN,
                    quantity=quantity,
                    entry_price=signal.price_at_signal,
                    current_price=signal.price_at_signal,
                    stop_loss_price=sl_price,
                    take_profit_price=tp_price,
                    trailing_stop_price=sl_price,
                    upstox_order_id=order_id,
                    entry_time=ist_now()
                )
                
                db.add(trade)
                
                # Update signal status
                signal.status = SignalStatus.EXECUTED
                db.merge(signal)
                
                db.commit()
                
                logger.info(f"💰 TRADE OPENED: {symbol.symbol} | Qty: {quantity} | Entry: {trade.entry_price} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")
                
                await self.telegram.send_message(
                    f"💰 <b>Trade Opened</b>\n"
                    f"Symbol: <code>{symbol.symbol}</code>\n"
                    f"Qty: <code>{quantity}</code>\n"
                    f"Entry: <code>{trade.entry_price}</code>\n"
                    f"SL: <code>{sl_price:.2f}</code> | TP: <code>{tp_price:.2f}</code>"
                )
        except Exception as e:
            logger.error(f"Error executing trade for signal {signal.id}: {e}")
            db.rollback()
        finally:
            db.close()

    async def monitor_positions(self):
        """
        Background task to monitor open positions and manage SL/TP
        """
        while True:
            db = SessionLocal()
            try:
                open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
                
                for trade in open_trades:
                    # In a real scenario, we'd get the latest price from a cache or WebSocket
                    # For now, we'll assume current_price is updated by the WebSocket handler
                    
                    # 1. Check Take Profit
                    if trade.current_price >= trade.take_profit_price:
                        await self.close_trade(trade, TradeStatus.TAKE_PROFIT, db)
                        
                    # 2. Check Stop Loss
                    elif trade.current_price <= trade.trailing_stop_price:
                        await self.close_trade(trade, TradeStatus.STOPPED_OUT, db)
                        
                    # 3. Update Trailing Stop
                    else:
                        # If price moves up, move trailing stop up
                        new_trailing_sl = trade.current_price * (1 - settings.trailing_stop_percent)
                        if new_trailing_sl > trade.trailing_stop_price:
                            trade.trailing_stop_price = new_trailing_sl
                            db.commit()
                            
            except Exception as e:
                logger.error(f"Error in position monitoring: {e}")
            finally:
                db.close()
                
            await asyncio.sleep(1) # Check every second

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
            
            # Calculate PnL
            if trade.order_side == OrderSide.BUY:
                trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
            else:
                trade.pnl = (trade.entry_price - trade.exit_price) * trade.quantity
                
            trade.pnl_percent = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
            
            db.commit()
            
            logger.info(f"🏁 TRADE CLOSED: {symbol.symbol} | Reason: {reason} | PnL: ₹{trade.pnl:.2f} ({trade.pnl_percent:.2f}%)")
            
            await self.telegram.send_message(
                f"🏁 <b>Trade Closed</b>\n"
                f"Symbol: <code>{symbol.symbol}</code>\n"
                f"Reason: <code>{reason}</code>\n"
                f"PnL: <b>₹{trade.pnl:.2f}</b> ({trade.pnl_percent:.2f}%)"
            )

    async def square_off_all(self):
        """
        Square off all open positions (Live and Paper)
        """
        logger.info("🚨 SQUARING OFF ALL POSITIONS...")
        
        # 1. Square off Paper Trades
        paper_msgs = paper_trading_manager.square_off_all()
        for msg in paper_msgs:
            if self.telegram:
                await self.telegram.send_message(f"🏁 <b>PAPER SQUARE-OFF</b>\n<pre>{msg}</pre>")
        
        # 2. Square off Live Trades
        db = SessionLocal()
        try:
            open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
            for trade in open_trades:
                await self.close_trade(trade, TradeStatus.SQUARED_OFF, db)
        except Exception as e:
            logger.error(f"Error during live square-off: {e}")
        finally:
            db.close()

# Global instance
trading_service = TradingService()
