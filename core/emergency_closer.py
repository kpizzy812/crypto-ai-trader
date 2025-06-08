# core/emergency_closer.py
"""
Экстренное закрытие позиций при критических ситуациях
"""
import asyncio
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
from loguru import logger

from core.portfolio import Portfolio
from core.event_bus import EventBus, Event, EventType


class EmergencyPositionCloser:
    """Система экстренного закрытия позиций"""

    def __init__(self, portfolio: Portfolio, event_bus: EventBus):
        self.portfolio = portfolio
        self.event_bus = event_bus
        self.exchange_manager = None  # Будет установлен извне
        self.is_emergency_mode = False
        self.closure_attempts = {}

    def set_exchange_manager(self, exchange_manager):
        """Установка менеджера бирж"""
        self.exchange_manager = exchange_manager

    async def emergency_close_all_positions(self, reason: str = "Emergency stop") -> Dict:
        """Экстренное закрытие всех позиций"""

        if self.is_emergency_mode:
            logger.warning("⚠️ Экстренное закрытие уже в процессе")
            return {'status': 'already_in_progress'}

        self.is_emergency_mode = True

        logger.critical(f"🚨 ЭКСТРЕННОЕ ЗАКРЫТИЕ ВСЕХ ПОЗИЦИЙ: {reason}")

        try:
            positions_to_close = list(self.portfolio.positions.values())

            if not positions_to_close:
                logger.info("✅ Нет открытых позиций для закрытия")
                return {'status': 'success', 'closed_positions': 0}

            logger.info(f"🔄 Закрытие {len(positions_to_close)} позиций...")

            # Результаты закрытия
            results = {
                'status': 'in_progress',
                'total_positions': len(positions_to_close),
                'successfully_closed': 0,
                'failed_to_close': 0,
                'errors': []
            }

            # Параллельное закрытие позиций
            close_tasks = []
            for position in positions_to_close:
                task = asyncio.create_task(
                    self._close_single_position_emergency(position, reason)
                )
                close_tasks.append(task)

            # Ждем завершения всех задач
            close_results = await asyncio.gather(*close_tasks, return_exceptions=True)

            # Анализ результатов
            for i, result in enumerate(close_results):
                if isinstance(result, Exception):
                    results['failed_to_close'] += 1
                    results['errors'].append(str(result))
                    logger.error(f"❌ Ошибка закрытия позиции {positions_to_close[i].id}: {result}")
                elif result.get('success'):
                    results['successfully_closed'] += 1
                    logger.info(f"✅ Позиция {result['position_id']} закрыта")
                else:
                    results['failed_to_close'] += 1
                    results['errors'].append(result.get('error', 'Unknown error'))

            # Финальный статус
            if results['successfully_closed'] == results['total_positions']:
                results['status'] = 'success'
                logger.info(f"🎉 Все {results['successfully_closed']} позиций успешно закрыты")
            elif results['successfully_closed'] > 0:
                results['status'] = 'partial_success'
                logger.warning(f"⚠️ Закрыто {results['successfully_closed']} из {results['total_positions']} позиций")
            else:
                results['status'] = 'failed'
                logger.error(f"❌ Не удалось закрыть ни одной позиции")

            # Публикация события
            await self.event_bus.publish(Event(
                type=EventType.EMERGENCY_STOP,
                data={
                    'reason': reason,
                    'results': results,
                    'timestamp': datetime.utcnow().isoformat()
                },
                source="EmergencyCloser"
            ))

            return results

        except Exception as e:
            logger.error(f"💥 Критическая ошибка экстренного закрытия: {e}")
            return {
                'status': 'critical_error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        finally:
            self.is_emergency_mode = False

    async def _close_single_position_emergency(self, position, reason: str) -> Dict:
        """Закрытие одной позиции в экстренном режиме"""

        max_attempts = 3
        position_id = position.id

        if position_id in self.closure_attempts:
            self.closure_attempts[position_id] += 1
        else:
            self.closure_attempts[position_id] = 1

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 Попытка {attempt}/{max_attempts} закрыть позицию {position_id}")

                # Определяем противоположную сторону
                close_side = 'sell' if position.side == 'long' else 'buy'

                # Размещаем рыночный ордер на закрытие
                if self.exchange_manager:
                    result = await self.exchange_manager.place_order(
                        symbol=position.symbol,
                        side=close_side,
                        order_type='market',
                        quantity=float(position.quantity),
                        strategy=f'emergency_close_{reason}'
                    )

                    if result:
                        # Ждем исполнения
                        await asyncio.sleep(2)

                        # Проверяем, закрылась ли позиция
                        if position_id not in self.portfolio.positions:
                            return {
                                'success': True,
                                'position_id': position_id,
                                'attempt': attempt,
                                'method': 'exchange_order'
                            }
                        else:
                            logger.warning(f"⚠️ Позиция {position_id} не закрылась после ордера")

                else:
                    # Если нет менеджера бирж - закрываем программно
                    logger.warning(f"⚠️ Закрытие позиции {position_id} программно (нет exchange_manager)")

                    # Эмулируем текущую цену (в реальности получили бы с биржи)
                    current_price = position.entry_price * Decimal("1.001")  # +0.1%

                    closed_position = await self.portfolio.close_position(position_id, current_price)

                    if closed_position:
                        return {
                            'success': True,
                            'position_id': position_id,
                            'attempt': attempt,
                            'method': 'programmatic',
                            'note': 'Closed programmatically due to missing exchange manager'
                        }

            except Exception as e:
                logger.error(f"❌ Ошибка попытки {attempt} закрытия {position_id}: {e}")

                if attempt < max_attempts:
                    # Увеличиваем задержку между попытками
                    await asyncio.sleep(attempt * 2)
                continue

        # Все попытки неудачны
        return {
            'success': False,
            'position_id': position_id,
            'error': f'Failed to close after {max_attempts} attempts',
            'attempts_made': max_attempts
        }

    async def force_close_position(self, position_id: str, reason: str = "Manual force close") -> Dict:
        """Принудительное закрытие конкретной позиции"""

        if position_id not in self.portfolio.positions:
            return {
                'success': False,
                'error': f'Position {position_id} not found'
            }

        position = self.portfolio.positions[position_id]

        logger.warning(f"⚠️ Принудительное закрытие позиции {position_id}: {reason}")

        try:
            result = await self._close_single_position_emergency(position, reason)

            if result['success']:
                logger.info(f"✅ Позиция {position_id} принудительно закрыта")

                # Публикация события
                await self.event_bus.publish(Event(
                    type=EventType.POSITION_CLOSED,
                    data={
                        'position_id': position_id,
                        'symbol': position.symbol,
                        'reason': reason,
                        'method': 'force_close',
                        'timestamp': datetime.utcnow().isoformat()
                    },
                    source="EmergencyCloser"
                ))

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка принудительного закрытия {position_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def emergency_reduce_position_sizes(self, reduction_percent: float = 50.0) -> Dict:
        """Экстренное уменьшение размеров всех позиций"""

        logger.warning(f"⚠️ Экстренное уменьшение позиций на {reduction_percent}%")

        results = {
            'total_positions': 0,
            'successfully_reduced': 0,
            'errors': []
        }

        try:
            positions = list(self.portfolio.positions.values())
            results['total_positions'] = len(positions)

            for position in positions:
                try:
                    # Рассчитываем количество для уменьшения
                    reduction_quantity = position.quantity * Decimal(str(reduction_percent / 100))

                    if reduction_quantity < Decimal("0.001"):  # Минимальное количество
                        continue

                    # Определяем сторону для частичного закрытия
                    close_side = 'sell' if position.side == 'long' else 'buy'

                    if self.exchange_manager:
                        # Размещаем ордер на частичное закрытие
                        result = await self.exchange_manager.place_order(
                            symbol=position.symbol,
                            side=close_side,
                            order_type='market',
                            quantity=float(reduction_quantity),
                            strategy='emergency_reduce'
                        )

                        if result:
                            results['successfully_reduced'] += 1
                            logger.info(f"✅ Уменьшена позиция {position.id} на {reduction_percent}%")
                    else:
                        # Программное уменьшение
                        position.quantity -= reduction_quantity
                        results['successfully_reduced'] += 1
                        logger.info(f"✅ Программно уменьшена позиция {position.id}")

                except Exception as e:
                    results['errors'].append(f"Position {position.id}: {str(e)}")
                    logger.error(f"❌ Ошибка уменьшения позиции {position.id}: {e}")

            return results

        except Exception as e:
            logger.error(f"❌ Критическая ошибка уменьшения позиций: {e}")
            return {
                'status': 'critical_error',
                'error': str(e)
            }

    async def get_emergency_status(self) -> Dict:
        """Получение статуса экстренной системы"""
        return {
            'is_emergency_mode': self.is_emergency_mode,
            'closure_attempts': dict(self.closure_attempts),
            'exchange_manager_available': self.exchange_manager is not None,
            'open_positions_count': len(self.portfolio.positions),
            'timestamp': datetime.utcnow().isoformat()
        }

    async def reset_emergency_state(self):
        """Сброс экстренного состояния"""
        logger.info("🔄 Сброс состояния экстренного закрытия")
        self.is_emergency_mode = False
        self.closure_attempts.clear()

    async def test_emergency_system(self) -> Dict:
        """Тестирование экстренной системы"""
        logger.info("🧪 Тестирование экстренной системы закрытия")

        checks = {
            'exchange_manager': self.exchange_manager is not None,
            'portfolio_accessible': hasattr(self.portfolio, 'positions'),
            'event_bus_accessible': hasattr(self.event_bus, 'publish'),
            'emergency_mode_clear': not self.is_emergency_mode
        }

        all_checks_passed = all(checks.values())

        return {
            'system_ready': all_checks_passed,
            'checks': checks,
            'timestamp': datetime.utcnow().isoformat(),
            'recommendation': 'System ready for emergency operations' if all_checks_passed
            else 'Some components need attention before emergency operations'
        }