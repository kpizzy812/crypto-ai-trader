# core/engine/position_manager.py
"""
Управление позициями и их жизненным циклом
"""
from typing import Dict, Optional
from decimal import Decimal
from loguru import logger
from datetime import datetime
import asyncio

from core.event_bus import EventBus, Event, EventType
from core.portfolio import Portfolio, Position


class PositionManager:
    """Менеджер позиций"""

    def __init__(self, portfolio: Portfolio, event_bus: EventBus):
        self.portfolio = portfolio
        self.event_bus = event_bus
        self.position_trackers = {}  # Отслеживание метаданных позиций

    async def initialize(self):
        """Инициализация менеджера позиций"""
        logger.info("📈 Инициализация менеджера позиций")

        # Подписка на торговые события
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal_generated)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)

        await self.setup_position_monitoring()

    async def _on_signal_generated(self, event: Event):
        """Обработка торгового сигнала"""
        data = event.data

        # Проверяем, нужно ли открыть позицию
        if data.get('source') == 'strategy' or data.get('source') == 'SignalProcessor':
            await self._process_entry_signal(data)

    async def _on_order_filled(self, event: Event):
        """Обработка исполненного ордера"""
        data = event.data

        try:
            # Определяем, открывается или закрывается позиция
            if await self._is_opening_position(data):
                await self._handle_position_opening(data)
            else:
                await self._handle_position_closing(data)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки исполненного ордера: {e}")

    async def _process_entry_signal(self, signal_data: Dict):
        """Обработка сигнала на открытие позиции"""

        symbol = signal_data['symbol']
        action = signal_data['action']

        # Проверяем, есть ли уже позиция по этому символу
        existing_position = await self._get_position_by_symbol(symbol)

        if existing_position:
            # Проверяем, нужно ли закрыть существующую позицию
            if self._should_reverse_position(existing_position, action):
                await self._close_position(existing_position, "strategy_reversal")
                # После закрытия будет открыта новая позиция
            else:
                logger.info(f"📈 Позиция {symbol} уже открыта, сигнал игнорирован")
                return

        # Генерируем событие для размещения ордера
        await self.event_bus.publish(Event(
            type=EventType.ORDER_PLACED,
            data={
                'symbol': symbol,
                'side': action,
                'quantity': signal_data.get('quantity', 0),
                'strategy': signal_data.get('strategy', 'unknown'),
                'signal_metadata': signal_data
            },
            source="PositionManager"
        ))

    def _should_reverse_position(self, position: Position, new_action: str) -> bool:
        """Проверка необходимости разворота позиции"""

        current_side = position.side

        # Разворот если противоположные направления
        if current_side == 'long' and new_action == 'sell':
            return True
        elif current_side == 'short' and new_action == 'buy':
            return True

        return False

    async def _get_position_by_symbol(self, symbol: str) -> Optional[Position]:
        """Получение позиции по символу"""

        for position in self.portfolio.positions.values():
            if position.symbol == symbol:
                return position
        return None

    async def _is_opening_position(self, order_data: Dict) -> bool:
        """Определение, открывается ли новая позиция"""

        symbol = order_data['symbol']
        existing_position = await self._get_position_by_symbol(symbol)

        return existing_position is None

    async def _handle_position_opening(self, order_data: Dict):
        """Обработка открытия позиции"""

        try:
            symbol = order_data['symbol']
            side = order_data['side']
            price = Decimal(str(order_data['price']))
            quantity = Decimal(str(order_data['quantity']))

            # Создание новой позиции
            position_id = f"pos_{symbol}_{datetime.utcnow().timestamp()}"

            position = Position(
                id=position_id,
                symbol=symbol,
                side='long' if side == 'buy' else 'short',
                entry_price=price,
                quantity=quantity,
                opened_at=datetime.utcnow()
            )

            # Добавление в портфель
            success = await self.portfolio.open_position(position)

            if success:
                # Добавление метаданных
                self.position_trackers[position_id] = {
                    'strategy': order_data.get('strategy', 'unknown'),
                    'signal_metadata': order_data.get('signal_metadata', {}),
                    'entry_time': datetime.utcnow()
                }

                # Публикация события
                await self.event_bus.publish(Event(
                    type=EventType.POSITION_OPENED,
                    data={
                        'position_id': position_id,
                        'symbol': symbol,
                        'side': position.side,
                        'entry_price': float(price),
                        'quantity': float(quantity),
                        'strategy': order_data.get('strategy')
                    },
                    source="PositionManager"
                ))

                logger.info(f"🟢 Открыта позиция {symbol}: {position.side} @ ${price}")
            else:
                logger.error(f"❌ Не удалось открыть позицию {symbol}")

        except Exception as e:
            logger.error(f"❌ Ошибка открытия позиции: {e}")

    async def _handle_position_closing(self, order_data: Dict):
        """Обработка закрытия позиции"""

        try:
            symbol = order_data['symbol']
            close_price = Decimal(str(order_data['price']))

            # Находим позицию для закрытия
            position = await self._get_position_by_symbol(symbol)

            if not position:
                logger.warning(f"⚠️ Позиция для закрытия {symbol} не найдена")
                return

            # Закрытие позиции
            closed_position = await self.portfolio.close_position(position.id, close_price)

            if closed_position:
                # Получение метаданных
                metadata = self.position_trackers.get(position.id, {})

                # Публикация события
                await self.event_bus.publish(Event(
                    type=EventType.POSITION_CLOSED,
                    data={
                        'position_id': position.id,
                        'symbol': symbol,
                        'pnl': float(closed_position.pnl),
                        'pnl_percent': float(closed_position.pnl_percent),
                        'duration': str(datetime.utcnow() - position.opened_at),
                        'strategy': metadata.get('strategy', 'unknown'),
                        'entry_price': float(position.entry_price),
                        'exit_price': float(close_price)
                    },
                    source="PositionManager"
                ))

                # Очистка метаданных
                if position.id in self.position_trackers:
                    del self.position_trackers[position.id]

                pnl_emoji = "🟢" if closed_position.pnl > 0 else "🔴" if closed_position.pnl < 0 else "⚪"
                logger.info(f"{pnl_emoji} Закрыта позиция {symbol}: PnL = ${closed_position.pnl:.2f}")
            else:
                logger.error(f"❌ Не удалось закрыть позицию {symbol}")

        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиции: {e}")

    async def _close_position(self, position: Position, reason: str = "manual"):
        """Принудительное закрытие позиции"""

        try:
            # Здесь должен быть вызов к exchange_manager для размещения ордера на закрытие
            # В упрощенной версии эмулируем закрытие

            # Получаем текущую цену (заглушка)
            current_price = position.entry_price * Decimal("1.01")  # +1% для примера

            closed_position = await self.portfolio.close_position(position.id, current_price)

            if closed_position:
                # Публикация события
                await self.event_bus.publish(Event(
                    type=EventType.POSITION_CLOSED,
                    data={
                        'position_id': position.id,
                        'symbol': position.symbol,
                        'pnl': float(closed_position.pnl),
                        'pnl_percent': float(closed_position.pnl_percent),
                        'reason': reason,
                        'duration': str(datetime.utcnow() - position.opened_at)
                    },
                    source="PositionManager"
                ))

                logger.info(f"✅ Принудительно закрыта позиция {position.symbol}: {reason}")

        except Exception as e:
            logger.error(f"❌ Ошибка принудительного закрытия позиции: {e}")

    async def get_position_statistics(self) -> Dict:
        """Получение статистики по позициям"""

        open_positions = len(self.portfolio.positions)
        total_pnl = sum(float(pos.pnl) for pos in self.portfolio.positions.values())

        # Статистика по стратегиям
        strategy_stats = {}
        for pos_id, metadata in self.position_trackers.items():
            strategy = metadata.get('strategy', 'unknown')
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {'count': 0, 'total_value': 0}

            position = self.portfolio.positions.get(pos_id)
            if position:
                strategy_stats[strategy]['count'] += 1
                strategy_stats[strategy]['total_value'] += float(position.entry_price * position.quantity)

        return {
            'open_positions': open_positions,
            'total_unrealized_pnl': total_pnl,
            'strategy_breakdown': strategy_stats
        }

    async def close_all_positions(self, reason: str = "emergency_close"):
        """Экстренное закрытие всех позиций"""

        logger.warning(f"⚠️ Экстренное закрытие всех позиций: {reason}")

        positions_to_close = list(self.portfolio.positions.values())

        for position in positions_to_close:
            await self._close_position(position, reason)

        logger.info(f"✅ Закрыто позиций: {len(positions_to_close)}")

    async def emergency_close_all_positions(self, reason: str = "Emergency stop"):
        """Экстренное закрытие всех позиций"""
        logger.critical(f"🚨 ЭКСТРЕННОЕ ЗАКРЫТИЕ ВСЕХ ПОЗИЦИЙ: {reason}")

        positions_to_close = list(self.portfolio.positions.values())

        if not positions_to_close:
            logger.info("✅ Нет открытых позиций для закрытия")
            return {'status': 'success', 'closed_positions': 0}

        results = {
            'total_positions': len(positions_to_close),
            'successfully_closed': 0,
            'failed_to_close': 0,
            'errors': []
        }

        # Закрываем все позиции параллельно
        close_tasks = []
        for position in positions_to_close:
            task = asyncio.create_task(self._emergency_close_single_position(position, reason))
            close_tasks.append(task)

        # Ждем завершения всех задач
        close_results = await asyncio.gather(*close_tasks, return_exceptions=True)

        # Анализируем результаты
        for i, result in enumerate(close_results):
            if isinstance(result, Exception):
                results['failed_to_close'] += 1
                results['errors'].append(str(result))
                logger.error(f"❌ Ошибка закрытия позиции {positions_to_close[i].id}: {result}")
            elif result and result.get('success'):
                results['successfully_closed'] += 1
                logger.info(f"✅ Позиция {result['position_id']} закрыта")
            else:
                results['failed_to_close'] += 1
                error_msg = result.get('error', 'Unknown error') if result else 'No result'
                results['errors'].append(error_msg)

        # Публикация события
        await self.event_bus.publish(Event(
            type=EventType.EMERGENCY_STOP,
            data={
                'reason': reason,
                'results': results,
                'timestamp': datetime.utcnow().isoformat()
            },
            source="PositionManager"
        ))

        if results['successfully_closed'] == results['total_positions']:
            logger.info(f"🎉 Все {results['successfully_closed']} позиций успешно закрыты")
        else:
            logger.warning(f"⚠️ Закрыто {results['successfully_closed']} из {results['total_positions']} позиций")

        return results

    async def _emergency_close_single_position(self, position, reason: str):
        """Экстренное закрытие одной позиции"""
        position_id = position.id

        try:
            logger.info(f"🔄 Экстренное закрытие позиции {position_id}")

            # Программное закрытие позиции (эмулируем текущую цену)
            # В реальной системе здесь должен быть вызов к exchange_manager
            current_price = position.entry_price * Decimal("1.001")  # +0.1% для примера

            closed_position = await self.portfolio.close_position(position_id, current_price)

            if closed_position:
                # Публикация события закрытия
                await self.event_bus.publish(Event(
                    type=EventType.POSITION_CLOSED,
                    data={
                        'position_id': position_id,
                        'symbol': position.symbol,
                        'pnl': float(closed_position.pnl),
                        'pnl_percent': float(closed_position.pnl_percent),
                        'reason': f"emergency_{reason}",
                        'duration': str(datetime.utcnow() - position.opened_at),
                        'entry_price': float(position.entry_price),
                        'exit_price': float(current_price)
                    },
                    source="PositionManager"
                ))

                # Очистка метаданных
                if position_id in self.position_trackers:
                    del self.position_trackers[position_id]

                return {
                    'success': True,
                    'position_id': position_id,
                    'method': 'emergency_programmatic'
                }
            else:
                logger.error(f"❌ Не удалось закрыть позицию {position_id}")
                return {
                    'success': False,
                    'position_id': position_id,
                    'error': 'Failed to close position programmatically'
                }

        except Exception as e:
            logger.error(f"❌ Ошибка экстренного закрытия {position_id}: {e}")
            return {
                'success': False,
                'position_id': position_id,
                'error': str(e)
            }

    async def force_close_position_by_symbol(self, symbol: str, reason: str = "Manual force close"):
        """Принудительное закрытие позиции по символу"""
        try:
            position = await self._get_position_by_symbol(symbol)

            if not position:
                logger.warning(f"⚠️ Позиция по символу {symbol} не найдена")
                return {'success': False, 'error': f'Position for {symbol} not found'}

            logger.warning(f"⚠️ Принудительное закрытие позиции {symbol}: {reason}")

            result = await self._emergency_close_single_position(position, reason)

            if result['success']:
                logger.info(f"✅ Позиция {symbol} принудительно закрыта")

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка принудительного закрытия {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    async def get_emergency_status(self):
        """Получение статуса экстренных операций"""
        return {
            'open_positions_count': len(self.portfolio.positions),
            'positions_by_symbol': {pos.symbol: pos.id for pos in self.portfolio.positions.values()},
            'emergency_available': True,
            'last_emergency_time': getattr(self, '_last_emergency_time', None),
            'timestamp': datetime.utcnow().isoformat()
        }

    async def setup_position_monitoring(self):
        """Настройка мониторинга позиций"""
        # Подписка на дополнительные события
        self.event_bus.subscribe(EventType.RISK_ALERT, self._on_risk_alert)
        self.event_bus.subscribe(EventType.SYSTEM_ERROR, self._on_system_error)

    async def _on_risk_alert(self, event: Event):
        """Обработка риск-алертов"""
        data = event.data
        alert_type = data.get('type', '')
        level = data.get('level', '')

        # При критических алертах закрываем позиции
        if level == 'CRITICAL' and alert_type in ['CRITICAL_RISK_SCORE', 'MAX_DRAWDOWN_EXCEEDED']:
            logger.critical(f"🚨 Получен критический риск-алерт: {alert_type}")
            await self.emergency_close_all_positions(f"Risk alert: {alert_type}")

    async def _on_system_error(self, event: Event):
        """Обработка системных ошибок"""
        data = event.data
        component = data.get('component', '')

        # При критических ошибках exchange_manager закрываем позиции
        if 'exchange' in component.lower() and data.get('severity') == 'critical':
            logger.critical(f"🚨 Критическая ошибка в {component}")
            await self.emergency_close_all_positions(f"System error: {component}")

    async def stop(self):
        """Остановка менеджера позиций"""
        logger.info("📈 Остановка менеджера позиций")

        # Экстренное закрытие всех позиций при остановке
        if self.portfolio.positions:
            await self.close_all_positions("engine_shutdown")

        self.position_trackers.clear()