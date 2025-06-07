# core/order_manager.py
"""
Управление жизненным циклом ордеров
"""
from typing import Dict, List, Optional, Callable
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from loguru import logger
from core.event_bus import EventBus, Event, EventType
from exchange.base_exchange import BaseExchange, Order


class OrderStatus(Enum):
    """Статусы ордеров в системе"""
    PENDING = "pending"
    PLACED = "placed"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ManagedOrder:
    """Управляемый ордер с дополнительной логикой"""
    order: Order
    strategy: str
    position_id: Optional[str] = None
    parent_order_id: Optional[str] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    expire_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.order.status in ['pending', 'placed', 'partially_filled']


class OrderManager:
    """Менеджер управления ордерами"""

    def __init__(self, exchange: BaseExchange, event_bus: EventBus):
        self.exchange = exchange
        self.event_bus = event_bus
        self.orders: Dict[str, ManagedOrder] = {}
        self.active_orders: Dict[str, ManagedOrder] = {}
        self._monitor_task = None
        self._running = False

    async def start(self):
        """Запуск мониторинга ордеров"""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_orders())
        logger.info("OrderManager запущен")

    async def stop(self):
        """Остановка мониторинга"""
        self._running = False
        if self._monitor_task:
            await self._monitor_task
        logger.info("OrderManager остановлен")

    async def place_order(self, symbol: str, side: str, order_type: str,
                          quantity: Decimal, price: Optional[Decimal] = None,
                          strategy: str = "manual",
                          stop_loss: Optional[Decimal] = None,
                          take_profit: Optional[Decimal] = None,
                          expire_minutes: Optional[int] = None) -> ManagedOrder:
        """Размещение управляемого ордера"""

        try:
            # Размещение ордера на бирже
            order = await self.exchange.place_order(
                symbol, side, order_type, quantity, price
            )

            # Создание управляемого ордера
            expire_time = None
            if expire_minutes:
                expire_time = datetime.utcnow() + timedelta(minutes=expire_minutes)

            managed_order = ManagedOrder(
                order=order,
                strategy=strategy,
                stop_loss=stop_loss,
                take_profit=take_profit,
                expire_time=expire_time
            )

            # Сохранение ордера
            self.orders[order.id] = managed_order
            self.active_orders[order.id] = managed_order

            # Публикация события
            await self.event_bus.publish(Event(
                type=EventType.ORDER_PLACED,
                data={
                    "order_id": order.id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "price": price,
                    "strategy": strategy
                },
                source="OrderManager"
            ))

            logger.info(f"Размещен ордер {order.id}: {side} {quantity} {symbol}")

            # Создание связанных ордеров (SL/TP)
            if stop_loss or take_profit:
                await self._create_bracket_orders(managed_order)

            return managed_order

        except Exception as e:
            logger.error(f"Ошибка размещения ордера: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """Отмена ордера"""

        if order_id not in self.active_orders:
            logger.warning(f"Ордер {order_id} не найден или уже неактивен")
            return False

        try:
            managed_order = self.active_orders[order_id]
            success = await self.exchange.cancel_order(order_id, managed_order.order.symbol)

            if success:
                managed_order.order.status = 'cancelled'
                del self.active_orders[order_id]

                # Публикация события
                await self.event_bus.publish(Event(
                    type=EventType.ORDER_CANCELLED,
                    data={
                        "order_id": order_id,
                        "symbol": managed_order.order.symbol,
                        "reason": "manual_cancel"
                    },
                    source="OrderManager"
                ))

                logger.info(f"Ордер {order_id} отменен")

            return success

        except Exception as e:
            logger.error(f"Ошибка отмены ордера {order_id}: {e}")
            return False

    async def update_order(self, order_id: str,
                           new_price: Optional[Decimal] = None,
                           new_quantity: Optional[Decimal] = None) -> bool:
        """Обновление ордера (отмена и пересоздание)"""

        if order_id not in self.active_orders:
            return False

        managed_order = self.active_orders[order_id]

        try:
            # Отмена старого ордера
            await self.cancel_order(order_id)

            # Создание нового с обновленными параметрами
            new_managed_order = await self.place_order(
                symbol=managed_order.order.symbol,
                side=managed_order.order.side,
                order_type=managed_order.order.type,
                quantity=new_quantity or managed_order.order.quantity,
                price=new_price or managed_order.order.price,
                strategy=managed_order.strategy,
                stop_loss=managed_order.stop_loss,
                take_profit=managed_order.take_profit
            )

            # Связывание с родительским ордером
            new_managed_order.parent_order_id = managed_order.parent_order_id

            return True

        except Exception as e:
            logger.error(f"Ошибка обновления ордера {order_id}: {e}")
            return False

    async def _monitor_orders(self):
        """Мониторинг активных ордеров"""

        while self._running:
            try:
                # Копия списка для безопасной итерации
                active_orders = list(self.active_orders.values())

                for managed_order in active_orders:
                    # Проверка статуса на бирже
                    updated_order = await self.exchange.get_order(
                        managed_order.order.id,
                        managed_order.order.symbol
                    )

                    if updated_order:
                        # Обновление локального статуса
                        old_status = managed_order.order.status
                        managed_order.order = updated_order

                        # Обработка изменения статуса
                        if old_status != updated_order.status:
                            await self._handle_status_change(managed_order, old_status)

                    # Проверка истечения времени
                    if managed_order.expire_time and datetime.utcnow() > managed_order.expire_time:
                        await self._handle_order_expiration(managed_order)

                # Пауза между проверками
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Ошибка мониторинга ордеров: {e}")
                await asyncio.sleep(5)

    async def _handle_status_change(self, managed_order: ManagedOrder, old_status: str):
        """Обработка изменения статуса ордера"""

        new_status = managed_order.order.status

        if new_status == 'filled':
            # Ордер полностью исполнен
            del self.active_orders[managed_order.order.id]

            await self.event_bus.publish(Event(
                type=EventType.ORDER_FILLED,
                data={
                    "order_id": managed_order.order.id,
                    "symbol": managed_order.order.symbol,
                    "side": managed_order.order.side,
                    "price": managed_order.order.price,
                    "quantity": managed_order.order.quantity,
                    "strategy": managed_order.strategy
                },
                source="OrderManager"
            ))

            logger.info(f"Ордер {managed_order.order.id} исполнен")

        elif new_status == 'cancelled':
            # Ордер отменен
            del self.active_orders[managed_order.order.id]

        elif new_status == 'rejected':
            # Ордер отклонен
            del self.active_orders[managed_order.order.id]

            # Попытка повторного размещения
            if managed_order.retry_count < managed_order.max_retries:
                await self._retry_order(managed_order)

    async def _handle_order_expiration(self, managed_order: ManagedOrder):
        """Обработка истечения времени ордера"""

        logger.info(f"Истекло время ордера {managed_order.order.id}")
        await self.cancel_order(managed_order.order.id)

    async def _retry_order(self, managed_order: ManagedOrder):
        """Повторная попытка размещения ордера"""

        managed_order.retry_count += 1
        logger.info(f"Повторная попытка размещения ордера (попытка {managed_order.retry_count})")

        # Задержка перед повторной попыткой
        await asyncio.sleep(2 ** managed_order.retry_count)

        try:
            new_order = await self.place_order(
                symbol=managed_order.order.symbol,
                side=managed_order.order.side,
                order_type=managed_order.order.type,
                quantity=managed_order.order.quantity,
                price=managed_order.order.price,
                strategy=managed_order.strategy,
                stop_loss=managed_order.stop_loss,
                take_profit=managed_order.take_profit
            )

            new_order.retry_count = managed_order.retry_count

        except Exception as e:
            logger.error(f"Ошибка повторного размещения ордера: {e}")

    async def _create_bracket_orders(self, managed_order: ManagedOrder):
        """Создание связанных ордеров (стоп-лосс и тейк-профит)"""

        # Ждем исполнения основного ордера
        asyncio.create_task(self._wait_and_create_brackets(managed_order))

    async def _wait_and_create_brackets(self, managed_order: ManagedOrder):
        """Ожидание исполнения и создание bracket ордеров"""

        # Ждем исполнения основного ордера
        max_wait = 300  # 5 минут
        waited = 0

        while waited < max_wait and managed_order.order.id in self.active_orders:
            await asyncio.sleep(1)
            waited += 1

            if managed_order.order.status == 'filled':
                # Создаем стоп-лосс
                if managed_order.stop_loss:
                    sl_side = 'sell' if managed_order.order.side == 'buy' else 'buy'
                    sl_order = await self.place_order(
                        symbol=managed_order.order.symbol,
                        side=sl_side,
                        order_type='limit',
                        quantity=managed_order.order.quantity,
                        price=managed_order.stop_loss,
                        strategy=f"{managed_order.strategy}_sl",
                        metadata={'parent_order': managed_order.order.id, 'type': 'stop_loss'}
                    )
                    sl_order.parent_order_id = managed_order.order.id

                # Создаем тейк-профит
                if managed_order.take_profit:
                    tp_side = 'sell' if managed_order.order.side == 'buy' else 'buy'
                    tp_order = await self.place_order(
                        symbol=managed_order.order.symbol,
                        side=tp_side,
                        order_type='limit',
                        quantity=managed_order.order.quantity,
                        price=managed_order.take_profit,
                        strategy=f"{managed_order.strategy}_tp",
                        metadata={'parent_order': managed_order.order.id, 'type': 'take_profit'}
                    )
                    tp_order.parent_order_id = managed_order.order.id

                break