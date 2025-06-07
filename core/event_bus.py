# core/event_bus.py
"""
Асинхронная шина событий для связи компонентов
"""
import asyncio
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
from enum import Enum


class EventType(Enum):
    """Типы событий в системе"""
    # Рыночные события
    PRICE_UPDATE = "price_update"
    OHLCV_UPDATE = "ohlcv_update"
    ORDER_BOOK_UPDATE = "order_book_update"

    # Торговые события
    SIGNAL_GENERATED = "signal_generated"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"

    # AI события
    AI_ANALYSIS_COMPLETE = "ai_analysis_complete"
    PATTERN_DETECTED = "pattern_detected"
    SENTIMENT_UPDATE = "sentiment_update"

    # Системные события
    RISK_ALERT = "risk_alert"
    SYSTEM_ERROR = "system_error"
    PERFORMANCE_UPDATE = "performance_update"


@dataclass
class Event:
    """Базовый класс события"""
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = None
    source: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class EventBus:
    """Асинхронная шина событий"""

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task = None

    def subscribe(self, event_type: EventType, handler: Callable):
        """Подписка на событие"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Подписка на {event_type.value}: {handler.__name__}")

    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Отписка от события"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event):
        """Публикация события"""
        await self._event_queue.put(event)
        logger.debug(f"Событие опубликовано: {event.type.value}")

    async def start(self):
        """Запуск обработки событий"""
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        logger.info("EventBus запущен")

    async def stop(self):
        """Остановка обработки событий"""
        self._running = False
        if self._worker_task:
            await self._worker_task
        logger.info("EventBus остановлен")

    async def _process_events(self):
        """Обработка очереди событий"""
        while self._running:
            try:
                # Ждем событие с таймаутом
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )

                # Вызываем все подписанные обработчики
                if event.type in self._subscribers:
                    handlers = self._subscribers[event.type]

                    # Запускаем обработчики параллельно
                    tasks = [
                        asyncio.create_task(self._call_handler(handler, event))
                        for handler in handlers
                    ]

                    # Ждем завершения всех обработчиков
                    await asyncio.gather(*tasks, return_exceptions=True)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Ошибка обработки события: {e}")

    async def _call_handler(self, handler: Callable, event: Event):
        """Безопасный вызов обработчика"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(f"Ошибка в обработчике {handler.__name__}: {e}")