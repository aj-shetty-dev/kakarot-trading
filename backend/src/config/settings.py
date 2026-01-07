"""
Configuration settings for Upstox Trading Bot
Loads from environment variables or .env file
"""

import json
from pydantic_settings import BaseSettings
from typing import Optional, Any, Dict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables and config file"""

    # ========== UPSTOX API CREDENTIALS ==========
    upstox_api_key: str
    upstox_api_secret: str
    upstox_access_token: str
    upstox_client_code: Optional[str] = None

    # ========== ACCOUNT & RISK ==========
    account_size: float = 100_000  # ₹1,00,000
    risk_per_trade: float = 0.05  # 5%
    daily_loss_limit: float = 0.02  # 2% per day
    daily_profit_target: float = 0.05  # 5% per day
    max_concurrent_positions: int = 3
    max_trades_per_day: int = 15

    # ========== POSITION SIZING ==========
    position_size_percent: float = 0.30  # 30% of account
    average_option_premium: float = 25_000  # ₹25k
    max_position_size_inr: float = 30_000  # ₹30k cap

    # ========== PROFIT & LOSS MANAGEMENT ==========
    take_profit_percent: float = 0.04  # 4%
    trailing_stop_percent: float = 0.02  # 2%
    stop_loss_percent: float = 0.05  # 5%

    # ========== BROKERAGE & CHARGES (Upstox) ==========
    brokerage_per_order: float = 20.0  # ₹20 per order
    stt_percent_sell: float = 0.0005  # 0.05% on sell side
    txn_charges_percent: float = 0.00053  # ~0.053% (NSE)
    gst_percent: float = 0.18  # 18% on (Brokerage + Txn)
    sebi_charges_percent: float = 0.000001  # 0.0001%
    stamp_duty_percent_buy: float = 0.00003  # 0.003% on buy side

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

    # ========== SCALPING STRATEGY ==========
    scalping_enabled: bool = True
    scalping_timeframe: str = "1m"
    scalping_take_profit_percent: float = 0.015
    scalping_stop_loss_percent: float = 0.007
    scalping_capital_allocation: float = 10000.0
    
    # Strategy Parameters
    ema_fast: int = 9
    ema_slow: int = 21
    ema_trend: int = 50
    rsi_period: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    atr_multiplier_sl: float = 1.5
    atr_multiplier_tp: float = 2.0
    adx_period: int = 14
    adx_threshold: float = 20.0
    volume_ma_period: int = 20
    volume_spike_multiplier: float = 2.0

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

    # ========== MARKET HOURS (IST) ==========
    market_open_time: str = "09:00"
    market_close_time: str = "16:00"
    auto_start_stop: bool = True

    # ========== NOTIFICATIONS ==========
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    enable_notifications: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **data):
        # Load from config.json if it exists
        config_path = Path(__file__).parent.parent.parent / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config_data = json.load(f)
                    # Merge config_data into data
                    # config.json takes precedence over .env for user-editable settings
                    for key, value in config_data.items():
                        data[key] = value
            except Exception as e:
                print(f"Warning: Could not load config.json: {e}")

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
