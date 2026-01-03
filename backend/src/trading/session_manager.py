"""
Market Session Manager
Handles automatic start/stop of trading services based on market hours (IST)
"""

import asyncio
import json
from datetime import datetime, time, timedelta
from typing import Optional

from ..config.logging import logger
from ..config.settings import settings
from ..config.timezone import ist_now, IST_TZ
from ..config.auth_utils import get_token_expiry
from ..notifications.telegram import get_telegram_service
from ..websocket.service import initialize_websocket_service, shutdown_websocket_service, get_websocket_service
from ..websocket.client import initialize_websocket, shutdown_websocket
from ..data.options_loader import load_options_at_startup
from ..data.database import SessionLocal
from ..data.models import TradingSession

class MarketSessionManager:
    """Manages the trading session lifecycle"""

    def __init__(self):
        self.is_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self.last_start_time: Optional[datetime] = None
        self.last_stop_time: Optional[datetime] = None
        self.startup_time = ist_now()
        self.current_session_id: Optional[str] = None
        self.last_token_alert_hour: Optional[int] = None
        self.report_sent_today = False

    async def start_monitoring(self):
        """Start the background monitoring task"""
        if self.monitor_task and not self.monitor_task.done():
            logger.warning("Session monitor is already running")
            return

        self._stop_event.clear()
        
        # Check if we need to send a report from a previous session that crashed or wasn't closed
        await self._check_eod_report_needed()
        
        self.monitor_task = asyncio.create_task(self._run_monitor())
        logger.info("🕒 Market Session Manager started")

    async def _check_eod_report_needed(self):
        """Check if market is closed and we haven't sent a report today"""
        import os
        now = ist_now()
        close_h, close_m = map(int, settings.market_close_time.split(":"))
        market_close = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
        
        # If it's past market close on a weekday
        if now >= market_close and now.weekday() < 5:
            today_str = now.strftime('%Y-%m-%d')
            report_path = os.path.join(settings.log_dir, today_str, "eod_report.json")
            
            # Always try to load and send the summary on startup if market is closed
            report = None
            if os.path.exists(report_path):
                try:
                    with open(report_path, 'r') as f:
                        report = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading existing EOD report: {e}")

            if not report:
                logger.info(f"📊 Market is closed and no EOD report found for {today_str}. Generating now...")
                try:
                    from ..reports.end_of_day_report import generate_end_of_day_report
                    report = generate_end_of_day_report()
                except Exception as e:
                    logger.error(f"Error generating catch-up EOD report: {e}")

            # Send the summary if we have a report
            if report and "trading" in report:
                perf = report["trading"]
                telegram = get_telegram_service(settings)
                await telegram.send_message(
                    f"📊 <b>Daily Performance Summary</b>\n"
                    f"Total Trades: <code>{perf['total_trades']}</code>\n"
                    f"Win Rate: <code>{perf['win_rate']:.1f}%</code>\n"
                    f"Total PnL: <b>₹{perf['total_pnl']:,.2f}</b>"
                )
                self.report_sent_today = True
            else:
                self.report_sent_today = True

    async def stop_monitoring(self):
        """Stop the background monitoring task"""
        self._stop_event.set()
        
        # If session is active, stop it properly before exiting
        if self.is_active:
            logger.info("🛑 Stopping active session during monitor shutdown...")
            await self._stop_trading_session()
            
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Market Session Manager stopped")

    async def _run_monitor(self):
        """Main loop to check market hours and manage services"""
        while not self._stop_event.is_set():
            try:
                now = ist_now()
                
                # Check if it's a weekend (5=Saturday, 6=Sunday)
                if now.weekday() >= 5:
                    if self.is_active:
                        logger.info("📅 Weekend detected. Shutting down services...")
                        await self._stop_trading_session()
                    
                    # Sleep longer on weekends
                    await asyncio.sleep(3600) 
                    continue

                # Parse market hours
                open_h, open_m = map(int, settings.market_open_time.split(":"))
                close_h, close_m = map(int, settings.market_close_time.split(":"))
                
                market_open = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
                market_close = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
                
                # Square-off time (15 mins before close)
                square_off_time = market_close - timedelta(minutes=15)

                # Reset report flag at start of day
                if now.hour == 0 and now.minute == 0:
                    self.report_sent_today = False

                if market_open <= now < market_close:
                    if not self.is_active:
                        logger.info(f"🔔 Market is OPEN ({settings.market_open_time}). Starting trading session...")
                        await self._start_trading_session()
                    
                    # Check for auto square-off
                    if now >= square_off_time and self.is_active:
                        logger.info("🕒 Square-off time reached (15 mins before close). Closing all positions...")
                        from .service import trading_service
                        await trading_service.square_off_all()
                        # We keep the session active until market_close to continue monitoring/logging
                else:
                    if self.is_active:
                        logger.info(f"🔕 Market is CLOSED ({settings.market_close_time}). Stopping trading session...")
                        await self._stop_trading_session()
                        self.report_sent_today = True
                    
                    # Catch-up: if market is closed and we haven't sent a report, do it now
                    if now >= market_close and not self.report_sent_today and now.weekday() < 5:
                        await self._check_eod_report_needed()
                    
                    # If it's before market open, log how long until open
                    if now < market_open:
                        diff = market_open - now
                        if diff.total_seconds() > 300: # Only log if more than 5 mins away
                            logger.info(f"💤 Market opens in {diff}. Waiting...")
                            # Sleep for 5 minutes or until market opens
                            sleep_time = min(300, diff.total_seconds())
                            await asyncio.sleep(sleep_time)
                            continue

                # Check token expiry periodically
                await self._check_token_expiry()

                # Regular check every 60 seconds
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in Session Manager loop: {e}")
                telegram = get_telegram_service(settings)
                await telegram.send_message(f"⚠️ <b>Warning:</b> Error in Session Manager loop: <code>{str(e)}</code>")
                await asyncio.sleep(60)

    async def _start_trading_session(self):
        """Initialize and start all trading services"""
        try:
            # 1. Load/Refresh options (LTP might have changed)
            logger.info("📋 Refreshing options for the new session...")
            await load_options_at_startup()
            
            # 2. Start WebSocket
            logger.info("📡 Starting WebSocket service...")
            ws_service = await initialize_websocket_service()
            
            if ws_service:
                self.is_active = True
                self.last_start_time = ist_now()
                
                # Persist session to DB
                try:
                    db = SessionLocal()
                    new_session = TradingSession(
                        start_time=self.last_start_time,
                        mode="Paper" if settings.paper_trading_mode else "Live",
                        status="ACTIVE"
                    )
                    db.add(new_session)
                    db.commit()
                    self.current_session_id = str(new_session.id)
                    db.close()
                except Exception as db_err:
                    logger.warning(f"Could not persist session start to DB: {db_err}")
                
                logger.info("✅ Trading session is now ACTIVE")
                
                # Send Telegram notification
                telegram = get_telegram_service(settings)
                await telegram.send_message(
                    "🔔 <b>Trading Session Started</b>\n"
                    f"Mode: {'Paper' if settings.paper_trading_mode else 'LIVE'}\n"
                    f"Time: {self.last_start_time.strftime('%H:%M:%S')}"
                )
            else:
                logger.error("❌ Failed to start WebSocket service for session")
                
        except Exception as e:
            logger.error(f"Error starting trading session: {e}")

    async def _stop_trading_session(self):
        """Shutdown all trading services"""
        try:
            logger.info("🛑 Shutting down trading session...")
            await shutdown_websocket_service()
            self.is_active = False
            self.last_stop_time = ist_now()
            
            # Send Telegram notification
            telegram = get_telegram_service(settings)
            await telegram.send_message(
                "🔕 <b>Trading Session Stopped</b>\n"
                f"Time: {self.last_stop_time.strftime('%H:%M:%S')}"
            )
            
            # Update session in DB
            if self.current_session_id:
                try:
                    db = SessionLocal()
                    session_record = db.query(TradingSession).filter(TradingSession.id == self.current_session_id).first()
                    if session_record:
                        session_record.end_time = self.last_stop_time
                        session_record.status = "COMPLETED"
                        db.commit()
                    db.close()
                    self.current_session_id = None
                except Exception as db_err:
                    logger.warning(f"Could not update session end in DB: {db_err}")
            
            logger.info("✅ Trading session is now INACTIVE")
            
            # Generate End of Day Report
            try:
                from ..reports.end_of_day_report import generate_end_of_day_report
                logger.info("📊 Generating End of Day Report...")
                report = generate_end_of_day_report()
                
                # Send summary to Telegram
                if report and "trading" in report:
                    perf = report["trading"]
                    await telegram.send_message(
                        f"📊 <b>Daily Performance Summary</b>\n"
                        f"Total Trades: <code>{perf['total_trades']}</code>\n"
                        f"Win Rate: <code>{perf['win_rate']:.1f}%</code>\n"
                        f"Total PnL: <b>₹{perf['total_pnl']:,.2f}</b>"
                    )
            except Exception as report_err:
                logger.error(f"Error generating EOD report: {report_err}")
                
        except Exception as e:
            logger.error(f"Error stopping trading session: {e}")

    async def restart_active_session(self):
        """Restart services if session is active or if it's market hours (e.g., after token update)"""
        now = ist_now()
        open_h, open_m = map(int, settings.market_open_time.split(":"))
        close_h, close_m = map(int, settings.market_close_time.split(":"))
        
        market_open = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        market_close = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
        
        is_market_hours = market_open <= now < market_close and now.weekday() < 5

        if self.is_active:
            logger.info("🔄 Restarting active trading session (settings updated)...")
            await self._stop_trading_session()
            await asyncio.sleep(2) # Brief pause
            await self._start_trading_session()
        elif is_market_hours:
            logger.info("🔄 Market is open but session was inactive. Starting session now with new settings...")
            await self._start_trading_session()
        else:
            logger.info("ℹ️ Settings updated, but market is closed. No immediate restart needed.")
            
            # Send confirmation to Telegram
            telegram = get_telegram_service(settings)
            await telegram.send_message(
                "✅ <b>Settings Updated</b>\n"
                "The application settings have been updated successfully. "
                "Verifying connection..."
            )
            
            # Verify token by connecting briefly
            try:
                ws = await initialize_websocket()
                if ws:
                    # The connect() method already sent the "WebSocket Connected" message
                    await shutdown_websocket()
                    logger.info("✅ Token verified successfully via temporary connection")
                    await telegram.send_message(
                        "✅ <b>Token Verified!</b>\n"
                        "The new token is valid. The bot will automatically start trading at 09:15 IST on the next market day."
                    )
                else:
                    # The connect() method already sent an error message if it was a 401
                    logger.error("❌ Token verification failed")
            except Exception as e:
                logger.error(f"Error during token verification: {e}")

    def get_status(self) -> dict:
        """Get current session status for monitoring"""
        now = ist_now()
        
        # Calculate next open
        open_h, open_m = map(int, settings.market_open_time.split(":"))
        market_open = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        
        if now >= market_open.replace(hour=open_h, minute=open_m): # Simplified
             # If already past today's open, next open is tomorrow
             pass # Logic for dashboard to handle

        return {
            "is_active": self.is_active,
            "last_start_time": self.last_start_time.isoformat() if self.last_start_time else None,
            "last_stop_time": self.last_stop_time.isoformat() if self.last_stop_time else None,
            "startup_time": self.startup_time.isoformat(),
            "market_hours": f"{settings.market_open_time} - {settings.market_close_time}",
            "auto_start_stop": settings.auto_start_stop
        }

    async def _check_token_expiry(self):
        """Check token expiry and send alerts if needed"""
        token_info = get_token_expiry(settings.upstox_access_token)
        hours_left = token_info.get("hours_left", 0)
        is_expired = token_info.get("expired", False)
        
        telegram = get_telegram_service(settings)
        
        if is_expired:
            if self.last_token_alert_hour != -1:
                await telegram.send_message(
                    "🚨 <b>CRITICAL: Upstox Token Expired!</b>\n"
                    "Trading is disabled. Please update the token immediately."
                )
                self.last_token_alert_hour = -1
        elif hours_left <= 12:
            # Alert at 12h, 6h, and then every hour when less than 3 hours left
            should_alert = False
            if hours_left in [12, 6]:
                should_alert = self.last_token_alert_hour != hours_left
            elif hours_left <= 3:
                should_alert = self.last_token_alert_hour != hours_left
                
            if should_alert:
                icon = "⚠️" if hours_left > 3 else "🚨"
                await telegram.send_message(
                    f"{icon} <b>Upstox Token Expiring Soon!</b>\n"
                    f"Time left: <code>{token_info.get('time_left')}</code>\n"
                    f"Expiry: <code>{token_info.get('expiry')}</code>"
                )
                self.last_token_alert_hour = hours_left

# Global instance
session_manager = MarketSessionManager()

async def get_session_manager():
    return session_manager
