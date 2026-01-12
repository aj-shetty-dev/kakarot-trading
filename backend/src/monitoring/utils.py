import time
from collections import defaultdict
import logging

class RateLimitedLogger:
    """
    Utility to prevent spamming the same log message too frequently
    """
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.last_logged = defaultdict(float)

    def warning(self, msg: str, interval: int = 300):
        """Log warning only if 'interval' seconds have passed since last similar message"""
        # Use message prefix for grouping (e.g., "Risk Denied: Daily profit target")
        key = msg.split(":")[0] + ":" + msg.split(":")[1] if ":" in msg else msg
        now = time.time()
        
        if now - self.last_logged[key] >= interval:
            self.logger.warning(msg)
            self.last_logged[key] = now

    def info(self, msg: str, interval: int = 300):
        now = time.time()
        if now - self.last_logged[msg] >= interval:
            self.logger.info(msg)
            self.last_logged[msg] = now
