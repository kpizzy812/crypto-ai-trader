# risk/risk_manager.py - ПОЛНАЯ ВЕРСИЯ
"""
Комплексный риск-менеджмент с полным функционалом
"""
from typing import Dict, Optional, List
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd
import numpy as np
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
    sortino_ratio: float
    calmar_ratio: float
    value_at_risk: Decimal  # VaR 95%
    risk_score: int  # 0-100, где 100 - максимальный риск


@dataclass
class PerformanceMetrics:
    """Метрики производительности"""
    total_return: float
    annualized_return: float
    volatility: float
    max_consecutive_losses: int
    win_rate: float
    profit_factor: float
    average_trade_duration: timedelta


class RiskManager:
    """Управление рисками - ПОЛНАЯ ВЕРСИЯ"""

    def __init__(self, risk_config: RiskConfig, portfolio: Portfolio):
        self.config = risk_config
        self.portfolio = portfolio

        # История для расчетов
        self.daily_returns: List[float] = []
        self.daily_balances: List[tuple] = []  # (date, balance)
        self.trade_history: List[Dict] = []

        # Пиковые значения
        self.peak_balance = portfolio.initial_balance
        self.daily_start_balance = portfolio.initial_balance
        self.last_reset = datetime.utcnow()
        self.max_historical_drawdown = Decimal("0")

    async def check_position_risk(self, symbol: str, side: str,
                                  entry_price: Decimal, quantity: Decimal) -> bool:
        """Проверка риска перед открытием позиции"""
        try:
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

            # Проверка корреляции позиций
            if await self._check_position_correlation(symbol, side):
                logger.warning(f"Высокая корреляция с существующими позициями: {symbol}")
                return False

            # Проверка концентрации риска
            if await self._check_concentration_risk(symbol, position_value):
                logger.warning(f"Превышена концентрация риска для {symbol}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки риска позиции: {e}")
            return False

    async def calculate_position_size(self, balance: Decimal, risk_amount: Decimal,
                                      stop_distance: Decimal, symbol: str = None) -> Decimal:
        """Расчет размера позиции по методу Kelly Criterion и риску"""
        try:
            if stop_distance <= 0:
                return Decimal("0")

            # Базовый размер по риску
            base_size = risk_amount / stop_distance

            # Корректировка по Kelly Criterion (если есть история)
            kelly_multiplier = await self._calculate_kelly_fraction(symbol)
            adjusted_size = base_size * Decimal(str(kelly_multiplier))

            # Ограничение максимальным размером
            max_position_value = balance * (Decimal(str(self.config.max_position_size_percent)) / 100)
            max_size = max_position_value / stop_distance

            # Корректировка на волатильность рынка
            volatility_adjustment = await self._get_volatility_adjustment()
            final_size = min(adjusted_size, max_size) * Decimal(str(volatility_adjustment))

            return max(final_size, Decimal("0"))

        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            return Decimal("0")

    async def _calculate_kelly_fraction(self, symbol: str = None) -> float:
        """Расчет Kelly Criterion для определения оптимального размера позиции"""
        try:
            if len(self.trade_history) < 10:
                return 0.25  # Консервативный размер для начала

            # Фильтруем историю по символу если указан
            relevant_trades = self.trade_history
            if symbol:
                relevant_trades = [t for t in self.trade_history if t.get('symbol') == symbol]

            if len(relevant_trades) < 5:
                return 0.25

            # Расчет параметров Kelly
            returns = [t['return_percent'] / 100 for t in relevant_trades]

            win_rate = len([r for r in returns if r > 0]) / len(returns)
            avg_win = np.mean([r for r in returns if r > 0]) if any(r > 0 for r in returns) else 0
            avg_loss = abs(np.mean([r for r in returns if r < 0])) if any(r < 0 for r in returns) else 0.01

            if avg_loss == 0:
                return 0.25

            # Kelly formula: f = (bp - q) / b
            # где b = avg_win/avg_loss, p = win_rate, q = 1 - win_rate
            b = avg_win / avg_loss
            kelly_fraction = (b * win_rate - (1 - win_rate)) / b

            # Ограничиваем Kelly в разумных пределах
            return max(0.1, min(0.5, kelly_fraction))

        except Exception as e:
            logger.error(f"❌ Ошибка расчета Kelly Criterion: {e}")
            return 0.25

    async def _get_volatility_adjustment(self) -> float:
        """Корректировка размера позиции на волатильность рынка"""
        try:
            if len(self.daily_returns) < 10:
                return 1.0

            # Расчет волатильности за последние дни
            recent_returns = self.daily_returns[-20:] if len(self.daily_returns) >= 20 else self.daily_returns
            volatility = np.std(recent_returns)

            # Корректировка: при высокой волатильности уменьшаем размер
            if volatility > 0.03:  # 3% дневная волатильность
                return 0.7  # Уменьшаем на 30%
            elif volatility > 0.02:  # 2% дневная волатильность
                return 0.85  # Уменьшаем на 15%
            elif volatility < 0.01:  # Низкая волатильность
                return 1.2  # Увеличиваем на 20%
            else:
                return 1.0

        except Exception as e:
            logger.error(f"❌ Ошибка расчета корректировки волатильности: {e}")
            return 1.0

    async def get_risk_metrics(self) -> RiskMetrics:
        """Получение расширенных метрик риска"""
        try:
            portfolio_stats = await self.portfolio.get_portfolio_stats()
            current_balance = portfolio_stats['total_value']

            # Обновляем историю
            await self._update_performance_history(current_balance)

            # Текущая просадка
            current_drawdown = await self._calculate_current_drawdown(current_balance)

            # Дневные потери
            daily_loss = await self._calculate_daily_loss(current_balance)

            # Риск по позициям
            position_risk = await self._calculate_position_risk()

            # Финансовые коэффициенты
            sharpe_ratio = await self._calculate_sharpe_ratio()
            sortino_ratio = await self._calculate_sortino_ratio()
            calmar_ratio = await self._calculate_calmar_ratio()

            # Value at Risk (95%)
            var_95 = await self._calculate_value_at_risk(0.05)

            # Общий риск-скор
            risk_score = self._calculate_risk_score(current_drawdown, daily_loss, position_risk)

            return RiskMetrics(
                current_drawdown=current_drawdown,
                max_drawdown=max(current_drawdown, self.max_historical_drawdown),
                daily_loss=daily_loss,
                position_risk=position_risk,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                value_at_risk=var_95,
                risk_score=risk_score
            )

        except Exception as e:
            logger.error(f"❌ Ошибка расчета метрик риска: {e}")
            return self._get_default_risk_metrics()

    async def _update_performance_history(self, current_balance: Decimal):
        """Обновление истории производительности"""
        try:
            today = datetime.utcnow().date()

            # Добавляем дневной баланс
            if not self.daily_balances or self.daily_balances[-1][0] != today:
                self.daily_balances.append((today, float(current_balance)))

                # Рассчитываем дневной возврат
                if len(self.daily_balances) > 1:
                    prev_balance = self.daily_balances[-2][1]
                    daily_return = (float(current_balance) - prev_balance) / prev_balance
                    self.daily_returns.append(daily_return)

                # Ограничиваем историю (максимум 252 дня = 1 год)
                if len(self.daily_balances) > 252:
                    self.daily_balances = self.daily_balances[-252:]
                    self.daily_returns = self.daily_returns[-251:]

            # Обновляем пиковый баланс
            if current_balance > self.peak_balance:
                self.peak_balance = current_balance

        except Exception as e:
            logger.error(f"❌ Ошибка обновления истории: {e}")

    async def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Расчет коэффициента Шарпа"""
        try:
            if len(self.daily_returns) < 30:
                return 0.0

            returns_array = np.array(self.daily_returns)

            # Годовые метрики
            annual_return = np.mean(returns_array) * 252
            annual_volatility = np.std(returns_array) * np.sqrt(252)

            if annual_volatility == 0:
                return 0.0

            sharpe = (annual_return - risk_free_rate) / annual_volatility
            return float(sharpe)

        except Exception as e:
            logger.error(f"❌ Ошибка расчета Sharpe ratio: {e}")
            return 0.0

    async def _calculate_sortino_ratio(self, target_return: float = 0.0) -> float:
        """Расчет коэффициента Sortino"""
        try:
            if len(self.daily_returns) < 30:
                return 0.0

            returns_array = np.array(self.daily_returns)

            # Только отрицательные возвраты для расчета downside deviation
            downside_returns = returns_array[returns_array < target_return / 252]

            if len(downside_returns) == 0:
                return float('inf')

            # Годовые метрики
            annual_return = np.mean(returns_array) * 252
            downside_deviation = np.sqrt(np.mean(downside_returns ** 2)) * np.sqrt(252)

            if downside_deviation == 0:
                return float('inf')

            sortino = (annual_return - target_return) / downside_deviation
            return float(sortino)

        except Exception as e:
            logger.error(f"❌ Ошибка расчета Sortino ratio: {e}")
            return 0.0

    async def _calculate_calmar_ratio(self) -> float:
        """Расчет коэффициента Calmar"""
        try:
            if len(self.daily_returns) < 30:
                return 0.0

            annual_return = np.mean(self.daily_returns) * 252
            max_drawdown = float(self.max_historical_drawdown) / 100  # В долях

            if max_drawdown == 0:
                return float('inf')

            calmar = annual_return / max_drawdown
            return float(calmar)

        except Exception as e:
            logger.error(f"❌ Ошибка расчета Calmar ratio: {e}")
            return 0.0

    async def _calculate_value_at_risk(self, confidence_level: float = 0.05) -> Decimal:
        """Расчет Value at Risk (VaR)"""
        try:
            if len(self.daily_returns) < 30:
                return Decimal("0")

            # Используем исторический метод
            returns_array = np.array(self.daily_returns)
            var_return = np.percentile(returns_array, confidence_level * 100)

            portfolio_stats = await self.portfolio.get_portfolio_stats()
            current_value = portfolio_stats['total_value']

            var_amount = current_value * Decimal(str(abs(var_return)))
            return var_amount

        except Exception as e:
            logger.error(f"❌ Ошибка расчета VaR: {e}")
            return Decimal("0")

    async def _check_position_correlation(self, symbol: str, side: str) -> bool:
        """Проверка корреляции с существующими позициями"""
        try:
            # Простая проверка: не более 3 позиций в одном направлении
            same_direction_count = 0

            for position in self.portfolio.positions.values():
                if position.side == side.lower():
                    same_direction_count += 1

            return same_direction_count >= 3

        except Exception as e:
            logger.error(f"❌ Ошибка проверки корреляции: {e}")
            return False

    async def _check_concentration_risk(self, symbol: str, position_value: Decimal) -> bool:
        """Проверка концентрации риска"""
        try:
            portfolio_stats = await self.portfolio.get_portfolio_stats()
            total_value = portfolio_stats['total_value']

            # Проверяем концентрацию по символу
            symbol_exposure = Decimal("0")
            for position in self.portfolio.positions.values():
                if position.symbol == symbol:
                    symbol_exposure += position.entry_price * position.quantity

            total_symbol_exposure = symbol_exposure + position_value
            concentration = (total_symbol_exposure / total_value) * 100

            # Максимальное количество убыточных сделок подряд
            max_consecutive_losses = 0
            current_losses = 0

            for trade in trades:
                if trade['pnl'] < 0:
                    current_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, current_losses)
                else:
                    current_losses = 0

            # Средняя длительность сделок
            durations = [t['duration'] for t in trades if t.get('duration')]
            avg_duration = sum(durations, timedelta()) / len(durations) if durations else timedelta()

            # Годовая доходность
            if len(self.daily_returns) > 0:
                annualized_return = np.mean(self.daily_returns) * 252
                volatility = np.std(self.daily_returns) * np.sqrt(252)
            else:
                annualized_return = 0.0
                volatility = 0.0

            return PerformanceMetrics(
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                max_consecutive_losses=max_consecutive_losses,
                win_rate=win_rate,
                profit_factor=profit_factor,
                average_trade_duration=avg_duration
            )

        except Exception as e:
            logger.error(f"❌ Ошибка расчета метрик производительности: {e}")
            return self._get_default_performance_metrics()

    def _get_default_performance_metrics(self) -> PerformanceMetrics:
        """Метрики по умолчанию"""
        return PerformanceMetrics(
            total_return=0.0,
            annualized_return=0.0,
            volatility=0.0,
            max_consecutive_losses=0,
            win_rate=0.0,
            profit_factor=0.0,
            average_trade_duration=timedelta()
        )

    async def _calculate_current_drawdown(self, current_balance: Decimal) -> Decimal:
        """Расчет текущей просадки"""
        if current_balance < self.peak_balance:
            drawdown = ((self.peak_balance - current_balance) / self.peak_balance) * 100
            self.max_historical_drawdown = max(self.max_historical_drawdown, drawdown)
            return drawdown
        return Decimal("0")

    async def _calculate_daily_loss(self, current_balance: Decimal) -> Decimal:
        """Расчет дневных потерь"""
        # Сброс счетчика в начале нового дня
        if datetime.utcnow().date() > self.last_reset.date():
            self.daily_start_balance = current_balance
            self.last_reset = datetime.utcnow()

        if current_balance < self.daily_start_balance:
            daily_loss_percent = ((self.daily_start_balance - current_balance) / self.daily_start_balance) * 100
            return daily_loss_percent
        return Decimal("0")

    async def _check_daily_loss_limit(self) -> bool:
        """Проверка дневного лимита потерь"""
        portfolio_stats = await self.portfolio.get_portfolio_stats()
        daily_loss = await self._calculate_daily_loss(portfolio_stats['total_value'])
        return daily_loss >= Decimal(str(self.config.max_daily_loss_percent))

    async def _check_drawdown_limit(self) -> bool:
        """Проверка лимита просадки"""
        portfolio_stats = await self.portfolio.get_portfolio_stats()
        current_drawdown = await self._calculate_current_drawdown(portfolio_stats['total_value'])
        return current_drawdown >= Decimal(str(self.config.max_drawdown_percent))

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
        try:
            # Веса для разных компонентов риска
            drawdown_weight = 0.4
            daily_loss_weight = 0.3
            position_risk_weight = 0.3

            max_drawdown_decimal = Decimal(str(self.config.max_drawdown_percent))
            max_daily_loss_decimal = Decimal(str(self.config.max_daily_loss_percent))

            # Нормализация значений (0-100)
            drawdown_score = min(float(drawdown / max_drawdown_decimal) * 100, 100)
            daily_loss_score = min(float(daily_loss / max_daily_loss_decimal) * 100, 100)
            position_risk_score = min(float(position_risk / Decimal("10")) * 100, 100)

            # Взвешенный расчет
            risk_score = (
                    drawdown_score * drawdown_weight +
                    daily_loss_score * daily_loss_weight +
                    position_risk_score * position_risk_weight
            )

            return int(min(risk_score, 100))

        except Exception as e:
            logger.error(f"❌ Ошибка расчета риск-скора: {e}")
            return 50

    def _get_default_risk_metrics(self) -> RiskMetrics:
        """Метрики риска по умолчанию"""
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

    async def generate_risk_report(self) -> Dict:
        """Генерация полного отчета по рискам"""
        try:
            risk_metrics = await self.get_risk_metrics()
            performance_metrics = await self.get_performance_metrics()

            return {
                'timestamp': datetime.utcnow().isoformat(),
                'risk_metrics': {
                    'current_drawdown': float(risk_metrics.current_drawdown),
                    'max_drawdown': float(risk_metrics.max_drawdown),
                    'daily_loss': float(risk_metrics.daily_loss),
                    'position_risk': float(risk_metrics.position_risk),
                    'value_at_risk_95': float(risk_metrics.value_at_risk),
                    'risk_score': risk_metrics.risk_score
                },
                'performance_metrics': {
                    'total_return': performance_metrics.total_return,
                    'annualized_return': performance_metrics.annualized_return,
                    'volatility': performance_metrics.volatility,
                    'sharpe_ratio': risk_metrics.sharpe_ratio,
                    'sortino_ratio': risk_metrics.sortino_ratio,
                    'calmar_ratio': risk_metrics.calmar_ratio,
                    'win_rate': performance_metrics.win_rate,
                    'profit_factor': performance_metrics.profit_factor,
                    'max_consecutive_losses': performance_metrics.max_consecutive_losses
                },
                'risk_limits': {
                    'max_position_size_percent': self.config.max_position_size_percent,
                    'max_daily_loss_percent': self.config.max_daily_loss_percent,
                    'max_drawdown_percent': self.config.max_drawdown_percent,
                    'stop_loss_percent': self.config.stop_loss_percent,
                    'take_profit_percent': self.config.take_profit_percent
                },
                'recommendations': await self._generate_risk_recommendations(risk_metrics, performance_metrics)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка генерации отчета по рискам: {e}")
            return {'error': str(e)}

    async def _generate_risk_recommendations(self, risk_metrics: RiskMetrics,
                                             performance_metrics: PerformanceMetrics) -> List[str]:
        """Генерация рекомендаций по управлению рисками"""
        recommendations = []

        try:
            # Анализ просадки
            if risk_metrics.current_drawdown > 10:
                recommendations.append("⚠️ Высокая просадка: рассмотрите уменьшение размера позиций")

            if risk_metrics.daily_loss > 3:
                recommendations.append("🛑 Превышен дневной лимит потерь: прекратите торговлю на сегодня")

            # Анализ производительности
            if performance_metrics.win_rate < 0.4:
                recommendations.append("📊 Низкий винрейт: проверьте точки входа и критерии отбора сделок")

            if risk_metrics.sharpe_ratio < 0.5:
                recommendations.append("📈 Низкий Sharpe ratio: улучшите соотношение доходность/риск")

            if performance_metrics.max_consecutive_losses > 5:
                recommendations.append("🔄 Много убыточных сделок подряд: пересмотрите стратегию")

            # Анализ позиций
            if risk_metrics.position_risk > 15:
                recommendations.append("⚖️ Высокий позиционный риск: уменьшите размеры позиций или стоп-лоссы")

            # Положительные моменты
            if risk_metrics.sharpe_ratio > 1.5:
                recommendations.append("✅ Отличный Sharpe ratio: стратегия работает хорошо")

            if performance_metrics.win_rate > 0.6:
                recommendations.append("🎯 Хороший винрейт: поддерживайте текущий подход")

            return recommendations

        except Exception as e:
            logger.error(f"❌ Ошибка генерации рекомендаций: {e}")
            return ["❌ Ошибка анализа рисков"]

    async def emergency_stop(self, reason: str = "Emergency risk limit breached"):
        """Экстренная остановка торговли"""
        try:
            logger.critical(f"🚨 ЭКСТРЕННАЯ ОСТАНОВКА: {reason}")

            # Публикуем критическое событие
            await self.portfolio.event_bus.publish({
                'type': 'EMERGENCY_STOP',
                'data': {
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat(),
                    'current_positions': len(self.portfolio.positions),
                    'total_value': float((await self.portfolio.get_portfolio_stats())['total_value'])
                }
            })

            # Здесь должна быть логика закрытия всех позиций
            logger.warning("⚠️ Требуется ручное закрытие позиций через Position Manager")

        except Exception as e:
            logger.error(f"❌ Ошибка экстренной остановки: {e}")

    async def should_stop_trading(self) -> tuple[bool, str]:
        """Проверка необходимости остановки торговли"""
        try:
            risk_metrics = await self.get_risk_metrics()

            # Критические условия остановки
            if risk_metrics.current_drawdown >= Decimal(str(self.config.max_drawdown_percent)):
                return True, f"Превышена максимальная просадка: {risk_metrics.current_drawdown:.2f}%"

            if risk_metrics.daily_loss >= Decimal(str(self.config.max_daily_loss_percent)):
                return True, f"Превышен дневной лимит потерь: {risk_metrics.daily_loss:.2f}%"

            if risk_metrics.risk_score >= 90:
                return True, f"Критический уровень риска: {risk_metrics.risk_score}/100"

            # Предупреждающие условия
            if risk_metrics.current_drawdown >= Decimal(str(self.config.max_drawdown_percent)) * Decimal("0.8"):
                return False, f"Приближение к лимиту просадки: {risk_metrics.current_drawdown:.2f}%"

            return False, "Риски в пределах нормы"

        except Exception as e:
            logger.error(f"❌ Ошибка проверки остановки торговли: {e}")
            return True, "Ошибка анализа рисков - остановка из предосторожности"
            ум
            20 % в
            одном
            символе
            return concentration > 20

        except Exception as e:
            logger.error(f"❌ Ошибка проверки концентрации: {e}")
            return False

    async def add_trade_to_history(self, trade_data: Dict):
        """Добавление сделки в историю для анализа"""
        try:
            self.trade_history.append({
                'timestamp': trade_data.get('timestamp', datetime.utcnow()),
                'symbol': trade_data.get('symbol'),
                'side': trade_data.get('side'),
                'pnl': trade_data.get('pnl', 0),
                'return_percent': trade_data.get('return_percent', 0),
                'duration': trade_data.get('duration'),
                'strategy': trade_data.get('strategy')
            })

            # Ограничиваем историю (максимум 1000 сделок)
            if len(self.trade_history) > 1000:
                self.trade_history = self.trade_history[-1000:]

        except Exception as e:
            logger.error(f"❌ Ошибка добавления сделки в историю: {e}")

    async def get_performance_metrics(self) -> PerformanceMetrics:
        """Получение метрик производительности"""
        try:
            if not self.trade_history:
                return self._get_default_performance_metrics()

            trades = self.trade_history

            # Базовые метрики
            total_return = sum(t['return_percent'] for t in trades)
            winning_trades = [t for t in trades if t['pnl'] > 0]
            losing_trades = [t for t in trades if t['pnl'] < 0]

            win_rate = len(winning_trades) / len(trades) if trades else 0

            # Profit factor
            gross_profit = sum(t['pnl'] for t in winning_trades)
            gross_loss = abs(sum(t['pnl'] for t in losing_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

            # Максим