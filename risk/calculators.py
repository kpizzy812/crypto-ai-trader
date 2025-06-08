# risk/calculators.py
"""
Калькуляторы для риск-менеджмента
"""
import numpy as np
from typing import List
from decimal import Decimal
from loguru import logger
from config.trading_config import RiskConfig


class RiskCalculator:
    """Калькулятор рисков"""

    def __init__(self, risk_config: RiskConfig):
        self.config = risk_config

    async def calculate_position_size(self, balance: Decimal, risk_amount: Decimal,
                                      stop_distance: Decimal) -> Decimal:
        """Расчет размера позиции"""
        try:
            if stop_distance <= 0:
                return Decimal("0")

            # Базовый размер по риску
            base_size = risk_amount / stop_distance

            # Ограничение максимальным размером
            max_position_value = balance * (Decimal(str(self.config.max_position_size_percent)) / 100)
            max_size = max_position_value / stop_distance

            return min(base_size, max_size)

        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            return Decimal("0")

    async def calculate_kelly_fraction(self, trade_history: List) -> float:
        """Расчет Kelly Criterion"""
        try:
            if len(trade_history) < 10:
                return 0.25  # Консервативный размер

            returns = [t.get('return_percent', 0) / 100 for t in trade_history]

            win_rate = len([r for r in returns if r > 0]) / len(returns)
            avg_win = np.mean([r for r in returns if r > 0]) if any(r > 0 for r in returns) else 0
            avg_loss = abs(np.mean([r for r in returns if r < 0])) if any(r < 0 for r in returns) else 0.01

            if avg_loss == 0:
                return 0.25

            # Kelly formula
            b = avg_win / avg_loss
            kelly_fraction = (b * win_rate - (1 - win_rate)) / b

            return max(0.1, min(0.5, kelly_fraction))

        except Exception as e:
            logger.error(f"❌ Ошибка Kelly Criterion: {e}")
            return 0.25

    async def calculate_sharpe_ratio(self, daily_returns: List[float],
                                     risk_free_rate: float = 0.02) -> float:
        """Расчет коэффициента Шарпа"""
        try:
            if len(daily_returns) < 30:
                return 0.0

            returns_array = np.array(daily_returns)
            annual_return = np.mean(returns_array) * 252
            annual_volatility = np.std(returns_array) * np.sqrt(252)

            if annual_volatility == 0:
                return 0.0

            return float((annual_return - risk_free_rate) / annual_volatility)

        except Exception as e:
            logger.error(f"❌ Ошибка Sharpe ratio: {e}")
            return 0.0

    async def calculate_sortino_ratio(self, daily_returns: List[float],
                                      target_return: float = 0.0) -> float:
        """Расчет коэффициента Sortino"""
        try:
            if len(daily_returns) < 30:
                return 0.0

            returns_array = np.array(daily_returns)
            downside_returns = returns_array[returns_array < target_return / 252]

            if len(downside_returns) == 0:
                return float('inf')

            annual_return = np.mean(returns_array) * 252
            downside_deviation = np.sqrt(np.mean(downside_returns ** 2)) * np.sqrt(252)

            if downside_deviation == 0:
                return float('inf')

            return float((annual_return - target_return) / downside_deviation)

        except Exception as e:
            logger.error(f"❌ Ошибка Sortino ratio: {e}")
            return 0.0

    async def calculate_value_at_risk(self, current_balance: Decimal,
                                      daily_returns: List[float],
                                      confidence_level: float = 0.05) -> Decimal:
        """Расчет Value at Risk"""
        try:
            if len(daily_returns) < 30:
                return Decimal("0")

            returns_array = np.array(daily_returns)
            var_return = np.percentile(returns_array, confidence_level * 100)

            var_amount = current_balance * Decimal(str(abs(var_return)))
            return var_amount

        except Exception as e:
            logger.error(f"❌ Ошибка VaR: {e}")
            return Decimal("0")

    def calculate_maximum_adverse_excursion(self, trades: List) -> Dict:
        """Расчет максимального неблагоприятного отклонения"""
        try:
            mae_values = []
            for trade in trades:
                if 'mae' in trade:
                    mae_values.append(trade['mae'])

            if not mae_values:
                return {'average': 0, 'maximum': 0, 'percentile_95': 0}

            return {
                'average': np.mean(mae_values),
                'maximum': np.max(mae_values),
                'percentile_95': np.percentile(mae_values, 95)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка MAE: {e}")
            return {'average': 0, 'maximum': 0, 'percentile_95': 0}

    def calculate_correlation_risk(self, positions: List, market_data: Dict) -> float:
        """Расчет корреляционного риска"""
        try:
            if len(positions) < 2:
                return 0.0

            # Упрощенный расчет корреляции
            symbols = [pos['symbol'] for pos in positions]

            # Если много позиций в одном направлении - высокий риск
            long_positions = sum(1 for pos in positions if pos['side'] == 'long')
            short_positions = sum(1 for pos in positions if pos['side'] == 'short')

            total_positions = len(positions)
            directional_concentration = max(long_positions, short_positions) / total_positions

            # Корреляция выше 0.8 считается высокой
            return min(directional_concentration, 1.0)

        except Exception as e:
            logger.error(f"❌ Ошибка корреляционного риска: {e}")
            return 0.5