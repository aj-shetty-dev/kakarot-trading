import httpx
import logging
import asyncio
import json
from pathlib import Path
from typing import Optional
from ..config.settings import Settings

logger = logging.getLogger(__name__)

class TelegramNotificationService:
    def __init__(self, settings: Settings):
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = settings.enable_notifications and self.token and self.chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        self.base_url = f"{self.api_url}/sendMessage" if self.api_url else None

    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured Telegram chat"""
        if not self.enabled:
            logger.debug("Telegram notifications are disabled or not configured.")
            return False

        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode
                }
                response = await client.post(self.base_url, json=payload, timeout=10.0)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_message_sync(self, message: str, parse_mode: str = "HTML") -> bool:
        """Synchronous version of send_message for non-async contexts"""
        if not self.enabled:
            return False
            
        try:
            import requests
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(self.base_url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message (sync): {e}")
            return False

# Global instance
_service: Optional[TelegramNotificationService] = None

def get_telegram_service(settings: Optional[Settings] = None, refresh: bool = False) -> TelegramNotificationService:
    global _service
    if _service is None or refresh:
        if settings is None:
            settings = Settings()
        _service = TelegramNotificationService(settings)
    return _service
