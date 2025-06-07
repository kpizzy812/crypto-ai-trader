# risk/risk_manager.py
"""
Комплексный риск-менеджмент
"""
from typing import Dict, Optional, List
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger
from core.portfolio import Portfolio, Position
from config.trading_config import RiskConfig


@dataclass
class RiskMetrics:
    """Метрики риска"""
    current_drawdown: Decimal
    max_drawdown: Decimal
    daily_loss: Decimal
    position_risk: Decimal
    sharpe_ratio: float
    risk_score: int  # 0-100, где 100 - максимальный риск


class RiskManager:
    """Управление рисками"""

    def __init__(self, risk_config: RiskConfig, portfolio: Portfolio):
        self.config = risk_config
        self.portfolio = portfolio
        self.daily_losses: List[Decimal] = []
        self.peak_balance = portfolio.initial_balance
        self.daily_start_balance = portfolio.initial_balance
        self.last_reset = datetime.utcnow()

    async def check_position_risk(self, symbol: str, side: str,
                                  entry_price: Decimal, quantity: Decimal) -> bool:
        """Проверка риска перед открытием позиции"""
        # Размер позиции относительно портфеля
        position_value = entry_price * quantity
        portfolio_stats = await self.portfolio.get_portfolio_stats()
        total_value = portfolio_stats['total_value']

        position_percent = (position_value / total_value) * 100

        if position_percent > self.config.max_position_size_percent:
            logger.warning(
                f"Позиция {symbol} превышает максимальный размер: {position_percent:.2f}% > {self.config.max_position_size_percent}%")
            return False

        # Проверка дневного лимита потерь
        if await self._check_daily_loss_limit():
            logger.warning("Достигнут дневной лимит потерь")
            return False

        # Проверка общей просадки
        if await self._check_drawdown_limit():
            logger.warning("Достигнут лимит просадки")
            return False

        return True

    async def calculate_position_size(self, balance: Decimal, risk_amount: Decimal,
                                      stop_distance: Decimal) -> Decimal:
        """Расчет размера позиции по риску"""
        if stop_distance <= 0:
            return Decimal("0")

        # Размер позиции = Риск в $ / Расстояние до стопа
        position_size = risk_amount / stop_distance

        # Ограничение максимальным размером
        max_position_value = balance * (self.config.max_position_size_percent / 100)

        return min(position_size, max_position_value)

    async def get_risk_metrics(self) -> RiskMetrics:
        """Получение текущих метрик риска"""
        portfolio_stats = await self.portfolio.get_portfolio_stats()
        current_balance = portfolio_stats['total_value']

        # Текущая просадка
        current_drawdown = Decimal("0")
        if current_balance < self.peak_balance:
            current_drawdown = ((self.peak_balance - current_balance) / self.peak_balance) * 100
        else:
            self.peak_balance = current_balance

        # Дневные потери
        daily_loss = ((self.daily_start_balance - current_balance) / self.daily_start_balance) * 100
        if daily_loss < 0:
            daily_loss = Decimal("0")

        # Риск по позициям
        position_risk = await self._calculate_position_risk()

        # Общий риск-скор
        risk_score = self._calculate_risk_score(current_drawdown, daily_loss, position_risk)

        return RiskMetrics(
            current_drawdown=current_drawdown,
            max_drawdown=max(current_drawdown, getattr(self, 'max_drawdown', Decimal("0"))),
            daily_loss=daily_loss,
            position_risk=position_risk,
            sharpe_ratio=0.0,  # TODO: Implement Sharpe ratio calculation
            risk_score=risk_score
        )

    async def _check_daily_loss_limit(self) -> bool:
        """Проверка дневного лимита потерь"""
        # Сброс счетчика в начале нового дня
        if datetime.utcnow().date() > self.last_reset.date():
            portfolio_stats = await self.portfolio.get_portfolio_stats()
            self.daily_start_balance = portfolio_stats['total_value']
            self.last_reset = datetime.utcnow()

        portfolio_stats = await self.portfolio.get_portfolio_stats()
        current_balance = portfolio_stats['total_value']

        daily_loss_percent = ((self.daily_start_balance - current_balance) / self.daily_start_balance) * 100

        return daily_loss_percent >= self.config.max_daily_loss_percent

    async def _check_drawdown_limit(self) -> bool:
        """Проверка лимита просадки"""
        metrics = await self.get_risk_metrics()
        return metrics.current_drawdown >= self.config.max_drawdown_percent

    async def _calculate_position_risk(self) -> Decimal:
        """Расчет риска по открытым позициям"""
        total_risk = Decimal("0")

        for position in self.portfolio.positions.values():
            if position.stop_loss:
                # Риск = количество * расстояние до стопа
                if position.side == 'long':
                    risk = position.quantity * (position.entry_price - position.stop_loss)
                else:
                    risk = position.quantity * (position.stop_loss - position.entry_price)

                total_risk += max(risk, Decimal("0"))

        portfolio_stats = await self.portfolio.get_portfolio_stats()
        total_value = portfolio_stats['total_value']

        return (total_risk / total_value) * 100 if total_value > 0 else Decimal("0")

    def _calculate_risk_score(self, drawdown: Decimal, daily_loss: Decimal,
                              position_risk: Decimal) -> int:
        """Расчет общего риск-скора"""
        # Веса для разных компонентов риска
        drawdown_weight = 0.4
        daily_loss_weight = 0.3
        position_risk_weight = 0.3

        # Нормализация значений (0-100)
        drawdown_score = min(float(drawdown / self.config.max_drawdown_percent) * 100, 100)
        daily_loss_score = min(float(daily_loss / self.config.max_daily_loss_percent) * 100, 100)
        position_risk_score = min(float(position_risk / 10) * 100, 100)  # 10% как максимум

        # Взвешенный расчет
        risk_score = (
                drawdown_score * drawdown_weight +
                daily_loss_score * daily_loss_weight +
                position_risk_score * position_risk_weight
        )

        return int(min(risk_score, 100))