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

    # Create logs directory if it doesn't exist
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level))
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler - Main trading log
    trading_log_file = log_dir / "trading.log"
    trading_handler = logging.handlers.RotatingFileHandler(
        trading_log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=10
    )
    trading_handler.setLevel(logging.INFO)
    trading_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(trading_handler)

    # File handler - Signals log
    signals_log_file = log_dir / "signals.log"
    signals_handler = logging.handlers.RotatingFileHandler(
        signals_log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=10
    )
    signals_handler.setLevel(logging.DEBUG)
    signals_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    signals_logger = logging.getLogger("signals")
    signals_logger.addHandler(signals_handler)

    # File handler - Errors log
    errors_log_file = log_dir / "errors.log"
    errors_handler = logging.handlers.RotatingFileHandler(
        errors_log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=10
    )
    errors_handler.setLevel(logging.ERROR)
    errors_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(errors_handler)

    return root_logger


# Initialize logger
logger = setup_logging()

# Module-specific loggers
trading_logger = logging.getLogger("trading")
signals_logger = logging.getLogger("signals")
websocket_logger = logging.getLogger("websocket")
api_logger = logging.getLogger("api")
risk_logger = logging.getLogger("risk")
