"""
Logging configuration for Upstox Trading Bot
"""

import logging
import logging.handlers
from pathlib import Path
from .settings import settings
from .constants import LOG_FORMAT, LOG_DATE_FORMAT


def setup_logging():
    """Setup logging for the application"""

    # Root logger
    root_logger = logging.getLogger()
    
    # PREVENT DOUBLE LOGGING: If root logger already has handlers, don't add more
    if root_logger.hasHandlers():
        return

    root_logger.setLevel(getattr(logging, settings.log_level))

    # Create logs directory if it doesn't exist
    base_log_dir = Path(settings.log_dir)
    base_log_dir.mkdir(exist_ok=True)

    # Create daily log directory
    from .timezone import ist_now
    today_str = ist_now().strftime('%Y-%m-%d')
    daily_log_dir = base_log_dir / today_str
    daily_log_dir.mkdir(exist_ok=True)

    # Create subdirectories for better organization
    subdirs = ["market_data", "signals", "trading", "system"]
    for subdir in subdirs:
        (daily_log_dir / subdir).mkdir(exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level))
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler - System log (General app events)
    system_log_file = daily_log_dir / "system" / "app.log"
    system_handler = logging.handlers.RotatingFileHandler(
        system_log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=10
    )
    system_handler.setLevel(logging.INFO)
    system_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(system_handler)

    # File handler - Signals log
    signals_logger = logging.getLogger("signals")
    if not signals_logger.handlers:
        signals_log_file = daily_log_dir / "signals" / "detections.log"
        signals_handler = logging.handlers.RotatingFileHandler(
            signals_log_file,
            maxBytes=10_000_000,  # 10MB
            backupCount=10
        )
        signals_handler.setLevel(logging.DEBUG)
        signals_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        signals_logger.addHandler(signals_handler)

    # File handler - Trading log (Orders and P&L)
    trading_logger = logging.getLogger("trading")
    if not trading_logger.handlers:
        trading_log_file = daily_log_dir / "trading" / "orders.log"
        trading_handler = logging.handlers.RotatingFileHandler(
            trading_log_file,
            maxBytes=10_000_000,  # 10MB
            backupCount=10
        )
        trading_handler.setLevel(logging.INFO)
        trading_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        trading_logger.addHandler(trading_handler)

    # File handler - Errors log
    errors_log_file = daily_log_dir / "system" / "errors.log"
    errors_handler = logging.handlers.RotatingFileHandler(
        errors_log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=10
    )
    errors_handler.setLevel(logging.ERROR)
    errors_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(errors_handler)

    # Add Telegram Alert Handler for CRITICAL errors
    if settings.enable_notifications and settings.telegram_bot_token:
        try:
            from ..notifications.telegram import get_telegram_service
            telegram = get_telegram_service(settings)
            
            class TelegramAlertHandler(logging.Handler):
                def emit(self, record):
                    # Prevent infinite loop: don't alert on errors from the telegram module itself
                    if record.name == "src.notifications.telegram" or record.module == "telegram":
                        return

                    # Alert on ERROR and CRITICAL
                    if record.levelno >= logging.ERROR:
                        emoji = "🚨" if record.levelno == logging.CRITICAL else "⚠️"
                        
                        message = f"{emoji} <b>SYSTEM ALERT</b>\n\n" \
                                  f"<b>Level:</b> {record.levelname}\n" \
                                  f"<b>Module:</b> {record.module}\n" \
                                  f"<b>Message:</b> {record.getMessage()}"
                        
                        # Use sync version to avoid async issues in logging
                        telegram.send_message_sync(message)
            
            alert_handler = TelegramAlertHandler()
            alert_handler.setLevel(logging.ERROR)  # Changed from CRITICAL to ERROR
            root_logger.addHandler(alert_handler)
            root_logger.info("✅ Telegram Alert Handler initialized for ERROR+CRITICAL errors")
        except Exception as e:
            root_logger.error(f"❌ Failed to initialize Telegram Alert Handler: {e}")

    return root_logger


# Initialize logger
logger = setup_logging()

# Module-specific loggers
trading_logger = logging.getLogger("trading")
signals_logger = logging.getLogger("signals")
websocket_logger = logging.getLogger("websocket")
api_logger = logging.getLogger("api")
risk_logger = logging.getLogger("risk")
