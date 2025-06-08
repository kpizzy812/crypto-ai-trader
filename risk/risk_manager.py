# risk/risk_manager.py - ОСНОВНОЙ ФАЙЛ
"""
Основной риск-менеджер (упрощенная версия)
"""
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger
from core.portfolio import Portfolio
from config.trading_config import RiskConfig
from .metrics import RiskMetrics, PerformanceMetrics
from .calculators import RiskCalculator
from .monitors import RiskMonitor


class RiskManager:
    """Главный риск-менеджер"""

    def __init__(self, risk_config: RiskConfig, portfolio: Portfolio):
        self.config = risk_config
        self.portfolio = portfolio

        # Инициализация компонентов
        self.calculator = RiskCalculator(risk_config)
        self.monitor = RiskMonitor(risk_config, portfolio)

        # Пиковые значения
        self.peak_balance = portfolio.initial_balance
        self.daily_start_balance = portfolio.initial_balance
        self.last_reset = datetime.utcnow()
        self.max_historical_drawdown = Decimal("0")

    async def check_position_risk(self, symbol: str, side: str,
                                  entry_price: Decimal, quantity: Decimal) -> bool:
        """Основная проверка риска позиции"""
        try:
            # 1. Размер позиции
            position_value = entry_price * quantity
            portfolio_stats = await self.portfolio.get_portfolio_stats()
            total_value = portfolio_stats['total_value']

            position_percent = (position_value / total_value) * 100

            if position_percent > self.config.max_position_size_percent:
                logger.warning(f"Позиция {symbol} превышает максимальный размер: {position_percent:.2f}%")
                return False

            # 2. Дневной лимит
            if await self._check_daily_loss_limit():
                logger.warning("Достигнут дневной лимит потерь")
                return False

            # 3. Общая просадка
            if await self._check_drawdown_limit():
                logger.warning("Достигнут лимит просадки")
                return False

            # 4. Корреляция позиций
            if await self._check_position_correlation(symbol, side):
                logger.warning(f"Высокая корреляция с существующими позициями: {symbol}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки риска: {e}")
            return False

    async def calculate_position_size(self, balance: Decimal, risk_amount: Decimal,
                                      stop_distance: Decimal) -> Decimal:
        """Расчет размера позиции"""
        return await self.calculator.calculate_position_size(
            balance, risk_amount, stop_distance
        )

    async def get_risk_metrics(self) -> RiskMetrics:
        """Получение метрик риска"""
        try:
            portfolio_stats = await self.portfolio.get_portfolio_stats()
            current_balance = portfolio_stats['total_value']

            # Базовые расчеты
            current_drawdown = await self._calculate_current_drawdown(current_balance)
            daily_loss = await self._calculate_daily_loss(current_balance)
            position_risk = await self._calculate_position_risk()

            # Комплексные метрики
            sharpe_ratio = await self.calculator.calculate_sharpe_ratio(self.monitor.daily_returns)
            sortino_ratio = await self.calculator.calculate_sortino_ratio(self.monitor.daily_returns)
            var_95 = await self.calculator.calculate_value_at_risk(
                current_balance, self.monitor.daily_returns
            )

            risk_score = self._calculate_risk_score(current_drawdown, daily_loss, position_risk)

            return RiskMetrics(
                current_drawdown=current_drawdown,
                max_drawdown=max(current_drawdown, self.max_historical_drawdown),
                daily_loss=daily_loss,
                position_risk=position_risk,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=0.0,  # Упрощаем
                value_at_risk=var_95,
                risk_score=risk_score
            )

        except Exception as e:
            logger.error(f"❌ Ошибка расчета метрик риска: {e}")
            return self._get_default_risk_metrics()

    async def should_stop_trading(self) -> tuple[bool, str]:
        """Проверка необходимости остановки торговли"""
        try:
            risk_metrics = await self.get_risk_metrics()

            # Критические условия
            if risk_metrics.current_drawdown >= Decimal(str(self.config.max_drawdown_percent)):
                return True, f"Превышена максимальная просадка: {risk_metrics.current_drawdown:.2f}%"

            if risk_metrics.daily_loss >= Decimal(str(self.config.max_daily_loss_percent)):
                return True, f"Превышен дневной лимит потерь: {risk_metrics.daily_loss:.2f}%"

            if risk_metrics.risk_score >= 90:
                return True, f"Критический уровень риска: {risk_metrics.risk_score}/100"

            return False, "Риски в пределах нормы"

        except Exception as e:
            logger.error(f"❌ Ошибка проверки остановки: {e}")
            return True, "Ошибка анализа рисков - остановка из предосторожности"

    async def emergency_stop(self, reason: str = "Emergency risk limit breached"):
        """Экстренная остановка торговли"""
        try:
            logger.critical(f"🚨 ЭКСТРЕННАЯ ОСТАНОВКА: {reason}")

            # Публикуем критическое событие
            if hasattr(self.portfolio, 'event_bus'):
                await self.portfolio.event_bus.publish({
                    'type': 'EMERGENCY_STOP',
                    'data': {
                        'reason': reason,
                        'timestamp': datetime.utcnow().isoformat(),
                        'current_positions': len(self.portfolio.positions),
                        'total_value': float((await self.portfolio.get_portfolio_stats())['total_value'])
                    }
                })

            logger.warning("⚠️ Требуется ручное закрытие позиций через Position Manager")

        except Exception as e:
            logger.error(f"❌ Ошибка экстренной остановки: {e}")

    # Приватные методы
    async def _calculate_current_drawdown(self, current_balance: Decimal) -> Decimal:
        """Расчет текущей просадки"""
        if current_balance < self.peak_balance:
            drawdown = ((self.peak_balance - current_balance) / self.peak_balance) * 100
            self.max_historical_drawdown = max(self.max_historical_drawdown, drawdown)
            return drawdown
        return Decimal("0")

    async def _calculate_daily_loss(self, current_balance: Decimal) -> Decimal:
        """Расчет дневных потерь"""
        # Сброс в начале дня
        if datetime.utcnow().date() > self.last_reset.date():
            self.daily_start_balance = current_balance
            self.last_reset = datetime.utcnow()

        if current_balance < self.daily_start_balance:
            return ((self.daily_start_balance - current_balance) / self.daily_start_balance) * 100
        return Decimal("0")

    async def _calculate_position_risk(self) -> Decimal:
        """Расчет риска по позициям"""
        total_risk = Decimal("0")

        for position in self.portfolio.positions.values():
            if position.stop_loss:
                if position.side == 'long':
                    risk = position.quantity * (position.entry_price - position.stop_loss)
                else:
                    risk = position.quantity * (position.stop_loss - position.entry_price)
                total_risk += max(risk, Decimal("0"))

        portfolio_stats = await self.portfolio.get_portfolio_stats()
        total_value = portfolio_stats['total_value']

        return (total_risk / total_value) * 100 if total_value > 0 else Decimal("0")

    async def _check_daily_loss_limit(self) -> bool:
        """Проверка дневного лимита"""
        portfolio_stats = await self.portfolio.get_portfolio_stats()
        daily_loss = await self._calculate_daily_loss(portfolio_stats['total_value'])
        return daily_loss >= Decimal(str(self.config.max_daily_loss_percent))

    async def _check_drawdown_limit(self) -> bool:
        """Проверка лимита просадки"""
        portfolio_stats = await self.portfolio.get_portfolio_stats()
        current_drawdown = await self._calculate_current_drawdown(portfolio_stats['total_value'])
        return current_drawdown >= Decimal(str(self.config.max_drawdown_percent))

    async def _check_position_correlation(self, symbol: str, side: str) -> bool:
        """Проверка корреляции позиций"""
        same_direction_count = sum(
            1 for pos in self.portfolio.positions.values()
            if pos.side == side.lower()
        )
        return same_direction_count >= 3

    def _calculate_risk_score(self, drawdown: Decimal, daily_loss: Decimal,
                              position_risk: Decimal) -> int:
        """Расчет общего риск-скора"""
        try:
            # Простой расчет
            score = float(drawdown) * 0.4 + float(daily_loss) * 0.3 + float(position_risk) * 0.3
            return int(min(max(score, 0), 100))
        except Exception:
            return 50

    def _get_default_risk_metrics(self) -> RiskMetrics:
        """Метрики по умолчанию"""
        return RiskMetrics(
            current_drawdown=Decimal("0"),
            max_drawdown=Decimal("0"),
            daily_loss=Decimal("0"),
            position_risk=Decimal("0"),
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            value_at_risk=Decimal("0"),
            risk_score=50
        )