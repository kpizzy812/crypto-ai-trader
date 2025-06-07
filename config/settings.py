from pydantic_settings import BaseSettings
from typing import Dict, List, Optional
import os


class Settings(BaseSettings):
    # Общие настройки
    app_name: str = "Crypto AI Trader"
    debug: bool = False
    log_level: str = "INFO"

    # API настройки
    openai_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None

    # База данных
    database_url: str = "sqlite:///./crypto_trader.db"
    redis_url: str = "redis://localhost:6379"

    # Биржи
    bybit_api_key: Optional[str] = None
    bybit_api_secret: Optional[str] = None
    bybit_testnet: bool = True

    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    binance_testnet: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()