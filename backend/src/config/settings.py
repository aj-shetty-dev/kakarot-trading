"""
Configuration settings for Upstox Trading Bot
Loads from environment variables or .env file
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # ========== UPSTOX API CREDENTIALS ==========
    upstox_api_key: str
    upstox_api_secret: str
    upstox_access_token: str
    upstox_client_code: Optional[str] = None

    # ========== ACCOUNT & RISK ==========
    account_size: float = 100_000  # ₹1,00,000
    risk_per_trade: float = 0.05  # 5%
    daily_loss_limit: float = 0.02  # 2% per day
    max_concurrent_positions: int = 3

    # ========== POSITION SIZING ==========
    position_size_percent: float = 0.30  # 30% of account
    average_option_premium: float = 25_000  # ₹25k
    max_position_size_inr: float = 30_000  # ₹30k cap

    # ========== PROFIT & LOSS MANAGEMENT ==========
    take_profit_percent: float = 0.04  # 4%
    trailing_stop_percent: float = 0.02  # 2%
    stop_loss_percent: float = 0.05  # 5%

    # ========== RATE LIMITING ==========
    rate_limit_orders_per_minute: int = 10
    max_order_gap_seconds: int = 30

    # ========== TRADING MODE ==========
    paper_trading_mode: bool = True
    paper_trading_days: int = 14

    # ========== SIGNAL DETECTION ==========
    spike_threshold: float = 2.0  # Standard deviations
    volume_multiplier: float = 2.5
    min_signal_strength: float = 0.6

    # ========== DATABASE ==========
    database_url: str = "sqlite:///./upstox_trading.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ========== LOGGING ==========
    log_level: str = "INFO"
    log_dir: str = "logs/"

    # ========== ENVIRONMENT ==========
    environment: str = "development"
    debug: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **data):
        super().__init__(**data)
        # Create log directory if it doesn't exist
        Path(self.log_dir).mkdir(exist_ok=True)

    @property
    def is_paper_trading(self) -> bool:
        """Check if system is in paper trading mode"""
        return self.paper_trading_mode

    @property
    def max_position_value(self) -> float:
        """Calculate max position value in rupees"""
        return min(
            self.account_size * self.position_size_percent,
            self.max_position_size_inr
        )

    @property
    def max_loss_per_trade(self) -> float:
        """Calculate max loss per trade in rupees"""
        return self.account_size * self.risk_per_trade

    @property
    def daily_loss_threshold(self) -> float:
        """Calculate daily loss threshold in rupees"""
        return self.account_size * self.daily_loss_limit


# Create a singleton instance
settings = Settings()
