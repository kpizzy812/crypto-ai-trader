# trading/strategies/base_strategy.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd
from loguru import logger


class BaseStrategy(ABC):
    """Базовый класс для торговых стратегий"""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.active = False
        self.positions = {}

    @abstractmethod
    async def analyze(self, market_data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Анализ рынка и генерация сигналов"""
        pass

    @abstractmethod
    async def should_enter(self, analysis: Dict[str, Any]) -> bool:
        """Проверка условий входа в позицию"""
        pass

    @abstractmethod
    async def should_exit(self, analysis: Dict[str, Any], position: Dict[str, Any]) -> bool:
        """Проверка условий выхода из позиции"""
        pass

    def get_position_size(self, account_balance: float, risk_percent: float = 2.0) -> float:
        """Расчет размера позиции"""
        return account_balance * (risk_percent / 100)

    def calculate_stop_loss(self, entry_price: float, direction: str, percent: float = 2.0) -> float:
        """Расчет стоп-лосса"""
        if direction.upper() == "BUY":
            return entry_price * (1 - percent / 100)
        else:
            return entry_price * (1 + percent / 100)

    def calculate_take_profit(self, entry_price: float, direction: str, percent: float = 4.0) -> float:
        """Расчет тейк-профита"""
        if direction.upper() == "BUY":
            return entry_price * (1 + percent / 100)
        else:
            return entry_price * (1 - percent / 100)