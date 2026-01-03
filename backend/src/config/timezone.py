"""IST timezone helpers for the Upstox trading bot."""
import os
import time
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

os.environ.setdefault('TZ', 'Asia/Kolkata')
try:
    time.tzset()
except AttributeError:
    pass

IST_TZ = ZoneInfo('Asia/Kolkata') if ZoneInfo is not None else timezone(timedelta(hours=5, minutes=30))


def ist_now() -> datetime:
    """Return the current IST datetime (timezone-aware)."""
    return datetime.now(IST_TZ)


def ist_today() -> datetime.date:
    """Return today's date in IST."""
    return ist_now().date()


def ist_timestamp() -> float:
    """Return the current IST timestamp."""
    return ist_now().timestamp()


def ist_isoformat() -> str:
    """Return the current IST datetime in ISO format."""
    return ist_now().isoformat()
