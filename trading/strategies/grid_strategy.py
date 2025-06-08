# trading/strategies/grid_strategy.py - ДОПОЛНИТЕЛЬНАЯ СТРАТЕГИЯ
"""
Стратегия торговли по сетке
"""
from typing import Dict, Any, List
import pandas as pd
from decimal import Decimal
from loguru import logger
from trading.strategies.base_strategy import BaseStrategy


class GridStrategy(BaseStrategy):
    """Стратегия торговли по сетке"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("Grid", config)

        # Параметры сетки
        self.grid_levels = config.get('grid_levels', 10)
        self.grid_distance_percent = config.get('grid_distance_percent', 1.0)
        self.base_order_size = config.get('base_order_size', 100)

        # Активные ордера
        self.grid_orders: List[Dict] = []

    async def analyze(self, market_data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Анализ для грид стратегии"""

        if len(market_data) < 20:
            return {
                'symbol': symbol,
                'strategy': self.name,
                'action': 'HOLD',
                'reason': 'Недостаточно данных'
            }

        current_price = float(market_data['close'].iloc[-1])

        # Расчет уровней сетки
        grid_levels = self._calculate_grid_levels(current_price)

        return {
            'symbol': symbol,
            'strategy': self.name,
            'current_price': current_price,
            'grid_levels': grid_levels,
            'action': 'SETUP_GRID',
            'grid_distance': self.grid_distance_percent,
            'base_size': self.base_order_size
        }

    def _calculate_grid_levels(self, current_price: float) -> Dict:
        """Расчет уровней сетки"""

        step = current_price * (self.grid_distance_percent / 100)

        buy_levels = []
        sell_levels = []

        for i in range(1, self.grid_levels // 2 + 1):
            buy_levels.append(current_price - (step * i))
            sell_levels.append(current_price + (step * i))

        return {
            'buy_levels': buy_levels,
            'sell_levels': sell_levels,
            'step_size': step
        }

    async def should_enter(self, analysis: Dict[str, Any]) -> bool:
        """Проверка условий входа (настройка сетки)"""
        return analysis.get('action') == 'SETUP_GRID'

    async def should_exit(self, analysis: Dict[str, Any], position: Dict[str, Any]) -> bool:
        """Грид стратегия не выходит из позиций традиционно"""
        return False