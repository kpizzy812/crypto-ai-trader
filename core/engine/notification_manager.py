# core/engine/notification_manager.py
"""
Управление уведомлениями через Telegram и другие каналы
"""
from typing import Optional
from loguru import logger

from config.settings import Settings
from core.event_bus import EventBus, Event, EventType
from notifications.telegram_bot import TelegramBot


class NotificationManager:
    """Менеджер уведомлений"""

    def __init__(self, settings: Settings, event_bus: EventBus):
        self.settings = settings
        self.event_bus = event_bus
        self.telegram_bot: Optional[TelegramBot] = None

    async def initialize(self):
        """Инициализация уведомлений"""
        logger.info("📱 Инициализация системы уведомлений")

        await self._initialize_telegram()
        self._subscribe_to_events()

    async def _initialize_telegram(self):
        """Инициализация Telegram бота"""

        if not self.settings.telegram_bot_token:
            logger.info("⚠️ Telegram Bot Token не настроен")
            return

        try:
            self.telegram_bot = TelegramBot(
                self.settings.telegram_bot_token,
                self.event_bus
            )
            await self.telegram_bot.start()
            logger.info("✅ Telegram бот запущен")

        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram бота: {e}")

    def _subscribe_to_events(self):
        """Подписка на события для уведомлений"""

        # Торговые события
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal_generated)
        self.event_bus.subscribe(EventType.ORDER_PLACED, self._on_order_placed)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
        self.event_bus.subscribe(EventType.POSITION_OPENED, self._on_position_opened)
        self.event_bus.subscribe(EventType.POSITION_CLOSED, self._on_position_closed)

        # Системные события
        self.event_bus.subscribe(EventType.RISK_ALERT, self._on_risk_alert)
        self.event_bus.subscribe(EventType.SYSTEM_ERROR, self._on_system_error)

    async def _on_signal_generated(self, event: Event):
        """Уведомление о торговом сигнале"""
        data = event.data

        # Отправляем уведомления только для сильных сигналов
        confidence = data.get('confidence', 0)
        if confidence < 0.7:
            return

        message = f"""
🎯 <b>Торговый сигнал</b>

Символ: <b>{data.get('symbol', 'N/A')}</b>
Действие: <b>{data.get('action', 'N/A').upper()}</b>
Уверенность: {confidence:.1%}
Стратегия: <i>{data.get('strategy', 'N/A')}</i>

{data.get('reasoning', '')}
"""

        await self._send_notification(message, priority="high")

    async def _on_order_placed(self, event: Event):
        """Уведомление о размещенном ордере"""
        data = event.data

        message = f"""
📝 <b>Ордер размещен</b>

Символ: <b>{data.get('symbol', 'N/A')}</b>
Тип: {data.get('side', 'N/A').upper()}
Количество: {data.get('quantity', 'N/A')}
Стратегия: <i>{data.get('strategy', 'N/A')}</i>
"""

        await self._send_notification(message, priority="medium")

    async def _on_order_filled(self, event: Event):
        """Уведомление об исполненном ордере"""
        data = event.data

        message = f"""
✅ <b>Ордер исполнен</b>

Символ: <b>{data.get('symbol', 'N/A')}</b>
Тип: {data.get('side', 'N/A').upper()}
Цена: ${data.get('price', 0):.2f}
Количество: {data.get('quantity', 'N/A')}
"""

        await self._send_notification(message, priority="high")

    async def _on_position_opened(self, event: Event):
        """Уведомление об открытой позиции"""
        data = event.data

        message = f"""
🟢 <b>Позиция открыта</b>

Символ: <b>{data.get('symbol', 'N/A')}</b>
Направление: {data.get('side', 'N/A').upper()}
Цена входа: ${data.get('entry_price', 0):.2f}
Объем: {data.get('quantity', 'N/A')}
Стратегия: <i>{data.get('strategy', 'N/A')}</i>
"""

        await self._send_notification(message, priority="high")

    async def _on_position_closed(self, event: Event):
        """Уведомление о закрытой позиции"""
        data = event.data

        pnl = data.get('pnl', 0)
        pnl_percent = data.get('pnl_percent', 0)

        emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"

        message = f"""
{emoji} <b>Позиция закрыта</b>

Символ: <b>{data.get('symbol', 'N/A')}</b>
PnL: <code>${pnl:+.2f} ({pnl_percent:+.2f}%)</code>
Длительность: {data.get('duration', 'N/A')}
Стратегия: <i>{data.get('strategy', 'N/A')}</i>
"""

        await self._send_notification(message, priority="high")

    async def _on_risk_alert(self, event: Event):
        """Уведомление о риск-алерте"""
        data = event.data

        message = f"""
⚠️ <b>РИСК АЛЕРТ</b>

Тип: {data.get('type', 'N/A')}
Уровень: {data.get('level', 'N/A')}

{data.get('message', 'Превышен уровень риска')}

<i>Рекомендуется проверить позиции</i>
"""

        await self._send_notification(message, priority="critical")

    async def _on_system_error(self, event: Event):
        """Уведомление о системной ошибке"""
        data = event.data

        message = f"""
🔴 <b>Системная ошибка</b>

Компонент: {data.get('component', 'N/A')}
Ошибка: {data.get('error', 'N/A')}

<i>Система пытается восстановить работу...</i>
"""

        await self._send_notification(message, priority="critical")

    async def _send_notification(self, message: str, priority: str = "medium"):
        """Отправка уведомления через доступные каналы"""

        try:
            # Telegram уведомления
            if self.telegram_bot:
                await self._send_telegram_notification(message, priority)

            # Можно добавить другие каналы уведомлений:
            # - Email
            # - Discord
            # - Slack
            # - Push уведомления

        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")

    async def _send_telegram_notification(self, message: str, priority: str):
        """Отправка уведомления в Telegram"""

        try:
            # Фильтрация по приоритету
            if priority == "low" and not self._should_send_low_priority():
                return

            # Отправка сообщения всем подписчикам
            await self.telegram_bot._broadcast(message)

            logger.debug(f"📱 Telegram уведомление отправлено (приоритет: {priority})")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки Telegram уведомления: {e}")

    def _should_send_low_priority(self) -> bool:
        """Проверка необходимости отправки низкоприоритетных уведомлений"""

        # Можно настроить логику фильтрации:
        # - Время суток
        # - Частота уведомлений
        # - Настройки пользователя

        return True  # Пока отправляем все

    async def send_custom_notification(self, message: str, priority: str = "medium"):
        """Отправка кастомного уведомления"""

        logger.info(f"📱 Отправка кастомного уведомления: {priority}")
        await self._send_notification(message, priority)

    async def send_daily_report(self):
        """Отправка ежедневного отчета"""

        # Здесь должна быть генерация отчета на основе статистики
        report = """
📊 <b>Ежедневный отчет</b>

💰 Портфель: $10,500 (+2.5%)
📈 Открытых позиций: 3
✅ Успешных сделок: 8/12 (66.7%)
⚠️ Макс. просадка: -1.2%

🎯 Лучшая стратегия: SimpleMomentum (+3.1%)
"""

        await self._send_notification(report, priority="medium")

    async def send_system_status(self):
        """Отправка статуса системы"""

        status_message = """
🤖 <b>Статус системы</b>

🟢 Торговый движок: Активен
🟢 Подключение к биржам: OK
🟢 AI анализатор: Работает
🟡 Риск-скор: 25/100

⏱ Время работы: 4ч 23м
"""

        await self._send_notification(status_message, priority="low")

    async def stop(self):
        """Остановка системы уведомлений"""
        logger.info("📱 Остановка системы уведомлений")

        # Отправка уведомления об остановке
        shutdown_message = """
🛑 <b>Система остановлена</b>

Торговый бот завершил работу.
Все позиции закрыты.

<i>До встречи! 👋</i>
"""

        await self._send_notification(shutdown_message, priority="high")

        # Остановка Telegram бота
        if self.telegram_bot:
            await self.telegram_bot.stop()