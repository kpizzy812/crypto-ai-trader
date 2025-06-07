from pydantic import BaseModel
from typing import Dict, List
from decimal import Decimal

class RiskConfig(BaseModel):
    max_position_size_percent: float = 2.0  # % от депозита на сделку
    max_daily_loss_percent: float = 5.0     # % максимальной дневной просадки
    max_drawdown_percent: float = 15.0      # % максимальной общей просадки
    stop_loss_percent: float = 2.0          # % стоп-лосс
    take_profit_percent: float = 4.0        # % тейк-профит

class TradingPair(BaseModel):
    symbol: str
    min_quantity: Decimal
    tick_size: Decimal
    enabled: bool = True

class TradingConfig(BaseModel):
    # Торгуемые пары
    trading_pairs: List[TradingPair] = [
        TradingPair(symbol="BTCUSDT", min_quantity=Decimal("0.001"), tick_size=Decimal("0.1")),
        TradingPair(symbol="ETHUSDT", min_quantity=Decimal("0.01"), tick_size=Decimal("0.01")),
        TradingPair(symbol="SOLUSDT", min_quantity=Decimal("0.1"), tick_size=Decimal("0.001")),
    ]

    # Таймфреймы для анализа
    timeframes: List[str] = ["5m", "15m", "1h", "4h"]
    primary_timeframe: str = "15m"

    # Риск-менеджмент
    risk: RiskConfig = RiskConfig()

    # Индикаторы
    technical_indicators: Dict[str, Dict] = {
        "rsi": {"period": 14, "overbought": 70, "oversold": 30},
        "ema_fast": {"period": 9},
        "ema_slow": {"period": 21},
        "volume_sma": {"period": 20}
    }