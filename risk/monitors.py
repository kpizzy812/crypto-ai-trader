# risk/monitors.py
"""
Мониторы для отслеживания рисков в реальном времени
"""
from typing import List, Dict
from datetime import datetime, date
from decimal import Decimal
from loguru import logger
from config.trading_config import RiskConfig
from core.portfolio import Portfolio


class RiskMonitor:
    """Монитор рисков в реальном времени"""

    def __init__(self, risk_config: RiskConfig, portfolio: Portfolio):
        self.config = risk_config
        self.portfolio = portfolio

        # История для расчетов
        self.daily_returns: List[float] = []
        self.daily_balances: List[tuple] = []  # (date, balance)
        self.trade_history: List[Dict] = []

        # Состояние мониторинга
        self.last_balance_update = datetime.utcnow()
        self.alerts_sent = set()  # Избегаем спама алертов

    async def update_daily_performance(self, current_balance: Decimal):
        """Обновление дневной производительности"""
        try:
            today = datetime.utcnow().date()

            # Добавляем баланс если это новый день
            if not self.daily_balances or self.daily_balances[-1][0] != today:
                self.daily_balances.append((today, float(current_balance)))

                # Рассчитываем дневной возврат
                if len(self.daily_balances) > 1:
                    prev_balance = self.daily_balances[-2][1]
                    daily_return = (float(current_balance) - prev_balance) / prev_balance
                    self.daily_returns.append(daily_return)

                # Ограничиваем историю (252 дня = 1 год)
                if len(self.daily_balances) > 252:
                    self.daily_balances = self.daily_balances[-252:]
                    self.daily_returns = self.daily_returns[-251:]

            self.last_balance_update = datetime.utcnow()

        except Exception as e:
            logger.error(f"❌ Ошибка обновления производительности: {e}")

    async def check_risk_alerts(self, current_metrics) -> List[Dict]:
        """Проверка и генерация риск-алертов"""
        alerts = []

        try:
            # 1. Проверка просадки
            if current_metrics.current_drawdown > Decimal("10"):
                alert_key = f"drawdown_{current_metrics.current_drawdown:.1f}"
                if alert_key not in self.alerts_sent:
                    alerts.append({
                        'type': 'HIGH_DRAWDOWN',
                        'level': 'WARNING',
                        'message': f'Высокая просадка: {current_metrics.current_drawdown:.2f}%',
                        'value': float(current_metrics.current_drawdown),
                        'threshold': 10.0
                    })
                    self.alerts_sent.add(alert_key)

            # 2. Проверка дневных потерь
            if current_metrics.daily_loss > Decimal("3"):
                alert_key = f"daily_loss_{current_metrics.daily_loss:.1f}"
                if alert_key not in self.alerts_sent:
                    alerts.append({
                        'type': 'HIGH_DAILY_LOSS',
                        'level': 'WARNING',
                        'message': f'Высокие дневные потери: {current_metrics.daily_loss:.2f}%',
                        'value': float(current_metrics.daily_loss),
                        'threshold': 3.0
                    })
                    self.alerts_sent.add(alert_key)

            # 3. Критический риск-скор
            if current_metrics.risk_score > 80:
                alert_key = f"risk_score_{current_metrics.risk_score}"
                if alert_key not in self.alerts_sent:
                    alerts.append({
                        'type': 'CRITICAL_RISK_SCORE',
                        'level': 'CRITICAL',
                        'message': f'Критический уровень риска: {current_metrics.risk_score}/100',
                        'value': current_metrics.risk_score,
                        'threshold': 80
                    })
                    self.alerts_sent.add(alert_key)

            # 4. Много открытых позиций
            positions_count = len(self.portfolio.positions)
            if positions_count > 10:
                alert_key = f"positions_count_{positions_count}"
                if alert_key not in self.alerts_sent:
                    alerts.append({
                        'type': 'TOO_MANY_POSITIONS',
                        'level': 'INFO',
                        'message': f'Много открытых позиций: {positions_count}',
                        'value': positions_count,
                        'threshold': 10
                    })
                    self.alerts_sent.add(alert_key)

            # Очистка старых алертов (раз в час)
            self._cleanup_old_alerts()

        except Exception as e:
            logger.error(f"❌ Ошибка проверки алертов: {e}")

        return alerts

    def _cleanup_old_alerts(self):
        """Очистка старых алертов для повторной отправки"""
        # Очищаем алерты раз в час, чтобы важные могли повториться
        now = datetime.utcnow()
        if not hasattr(self, '_last_cleanup') or (now - self._last_cleanup).seconds > 3600:
            self.alerts_sent.clear()
            self._last_cleanup = now

    async def add_trade_result(self, trade_data: Dict):
        """Добавление результата сделки"""
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

            # Ограничиваем историю
            if len(self.trade_history) > 1000:
                self.trade_history = self.trade_history[-1000:]

        except Exception as e:
            logger.error(f"❌ Ошибка добавления сделки: {e}")

    def get_performance_summary(self) -> Dict:
        """Получение сводки производительности"""
        try:
            if not self.trade_history:
                return {
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_return': 0,
                    'best_trade': 0,
                    'worst_trade': 0
                }

            trades = self.trade_history
            winning_trades = [t for t in trades if t['pnl'] > 0]

            return {
                'total_trades': len(trades),
                'win_rate': len(winning_trades) / len(trades) if trades else 0,
                'avg_return': sum(t['return_percent'] for t in trades) / len(trades),
                'best_trade': max(t['pnl'] for t in trades) if trades else 0,
                'worst_trade': min(t['pnl'] for t in trades) if trades else 0,
                'last_updated': self.last_balance_update.isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки: {e}")
            return {'error': str(e)}


class PositionMonitor:
    """Монитор для отслеживания отдельных позиций"""

    def __init__(self):
        self.position_alerts = {}
        self.position_history = {}

    async def monitor_position(self, position, current_price: Decimal) -> List[Dict]:
        """Мониторинг отдельной позиции"""
        alerts = []
        position_id = position.id

        try:
            # Обновляем PnL
            position.update_pnl(current_price)

            # Проверка больших потерь
            if position.pnl_percent < -5:  # Более 5% потерь
                alerts.append({
                    'type': 'LARGE_POSITION_LOSS',
                    'level': 'WARNING',
                    'position_id': position_id,
                    'symbol': position.symbol,
                    'pnl_percent': float(position.pnl_percent),
                    'message': f'Большие потери по позиции {position.symbol}: {position.pnl_percent:.2f}%'
                })

            # Проверка стоп-лосса
            if position.stop_loss:
                if position.side == 'long' and current_price <= position.stop_loss:
                    alerts.append({
                        'type': 'STOP_LOSS_HIT',
                        'level': 'HIGH',
                        'position_id': position_id,
                        'symbol': position.symbol,
                        'current_price': float(current_price),
                        'stop_loss': float(position.stop_loss),
                        'message': f'Достигнут стоп-лосс для {position.symbol}'
                    })
                elif position.side == 'short' and current_price >= position.stop_loss:
                    alerts.append({
                        'type': 'STOP_LOSS_HIT',
                        'level': 'HIGH',
                        'position_id': position_id,
                        'symbol': position.symbol,
                        'current_price': float(current_price),
                        'stop_loss': float(position.stop_loss),
                        'message': f'Достигнут стоп-лосс для {position.symbol}'
                    })

            # Сохраняем историю позиции
            if position_id not in self.position_history:
                self.position_history[position_id] = []

            self.position_history[position_id].append({
                'timestamp': datetime.utcnow(),
                'price': float(current_price),
                'pnl': float(position.pnl),
                'pnl_percent': float(position.pnl_percent)
            })

            # Ограничиваем историю позиции
            if len(self.position_history[position_id]) > 1000:
                self.position_history[position_id] = self.position_history[position_id][-500:]

        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга позиции {position_id}: {e}")

        return alerts

    def get_position_analytics(self, position_id: str) -> Dict:
        """Получение аналитики по позиции"""
        try:
            if position_id not in self.position_history:
                return {'error': 'Position history not found'}

            history = self.position_history[position_id]
            if not history:
                return {'error': 'Empty position history'}

            # Базовая аналитика
            pnl_values = [h['pnl'] for h in history]

            return {
                'max_profit': max(pnl_values),
                'max_loss': min(pnl_values),
                'current_pnl': pnl_values[-1],
                'volatility': self._calculate_pnl_volatility(pnl_values),
                'data_points': len(history),
                'time_in_position': (history[-1]['timestamp'] - history[0]['timestamp']).total_seconds() / 3600  # часы
            }

        except Exception as e:
            logger.error(f"❌ Ошибка аналитики позиции: {e}")
            return {'error': str(e)}

    def _calculate_pnl_volatility(self, pnl_values: List[float]) -> float:
        """Расчет волатильности PnL позиции"""
        try:
            if len(pnl_values) < 2:
                return 0.0

            import numpy as np
            return float(np.std(pnl_values))
        except Exception:
            return 0.0