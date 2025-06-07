# notifications/telegram_bot.py
"""
Telegram бот для уведомлений и управления
"""
import asyncio
from typing import Optional, List, Dict, Callable
from datetime import datetime
from loguru import logger
import aiohttp
from config.settings import settings
from core.event_bus import EventBus, Event, EventType


class TelegramBot:
    """Telegram бот для уведомлений"""

    def __init__(self, token: str, event_bus: EventBus):
        self.token = token
        self.event_bus = event_bus
        self.chat_ids: List[int] = []  # Список авторизованных чатов
        self.api_url = f"https://api.telegram.org/bot{token}"
        self._running = False
        self._poll_task = None
        self._last_update_id = 0

        # Подписка на события
        self._subscribe_to_events()

        # Команды бота
        self.commands = {
            '/start': self._cmd_start,
            '/status': self._cmd_status,
            '/balance': self._cmd_balance,
            '/positions': self._cmd_positions,
            '/stop': self._cmd_stop,
            '/help': self._cmd_help
        }

    def _subscribe_to_events(self):
        """Подписка на события системы"""
        # Торговые события
        self.event_bus.subscribe(EventType.ORDER_PLACED, self._on_order_placed)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
        self.event_bus.subscribe(EventType.POSITION_OPENED, self._on_position_opened)
        self.event_bus.subscribe(EventType.POSITION_CLOSED, self._on_position_closed)

        # AI события
        self.event_bus.subscribe(EventType.AI_ANALYSIS_COMPLETE, self._on_ai_analysis)
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal_generated)

        # Системные события
        self.event_bus.subscribe(EventType.RISK_ALERT, self._on_risk_alert)
        self.event_bus.subscribe(EventType.SYSTEM_ERROR, self._on_system_error)

    async def start(self):
        """Запуск бота"""
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_updates())

        # Отправка стартового сообщения
        await self._broadcast("🤖 Crypto AI Trading Bot запущен!")
        logger.info("Telegram бот запущен")

    async def stop(self):
        """Остановка бота"""
        self._running = False
        if self._poll_task:
            await self._poll_task

        await self._broadcast("🛑 Crypto AI Trading Bot остановлен")
        logger.info("Telegram бот остановлен")

    async def send_message(self, chat_id: int, text: str,
                           parse_mode: str = "HTML") -> bool:
        """Отправка сообщения"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.api_url}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": text,
                            "parse_mode": parse_mode
                        }
                ) as response:
                    return response.status == 200

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
            return False

    async def _broadcast(self, message: str):
        """Отправка сообщения всем авторизованным чатам"""
        for chat_id in self.chat_ids:
            await self.send_message(chat_id, message)

    async def _poll_updates(self):
        """Получение обновлений от Telegram"""
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            f"{self.api_url}/getUpdates",
                            params={
                                "offset": self._last_update_id + 1,
                                "timeout": 30
                            }
                    ) as response:
                        if response.status == 200:
                            data = await response.json()

                            for update in data.get('result', []):
                                self._last_update_id = update['update_id']
                                await self._process_update(update)

            except Exception as e:
                logger.error(f"Ошибка получения обновлений Telegram: {e}")
                await asyncio.sleep(5)

    async def _process_update(self, update: Dict):
        """Обработка обновления от Telegram"""

        # Обработка сообщений
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']

            # Добавление чата в список авторизованных
            if chat_id not in self.chat_ids:
                self.chat_ids.append(chat_id)
                await self.send_message(
                    chat_id,
                    "✅ Вы подписаны на уведомления от Crypto AI Trading Bot"
                )

            # Обработка команд
            if 'text' in message:
                text = message['text']

                # Поиск команды
                command = text.split()[0]
                if command in self.commands:
                    await self.commands[command](chat_id, message)

    async def _cmd_start(self, chat_id: int, message: Dict):
        """Команда /start"""
        welcome_text = """
🤖 <b>Добро пожаловать в Crypto AI Trading Bot!</b>

Я буду отправлять вам уведомления о:
• 📈 Торговых сигналах
• 💰 Открытии/закрытии позиций
• 📊 Анализе рынка от AI
• ⚠️ Важных событиях и рисках

<b>Доступные команды:</b>
/status - Текущий статус бота
/balance - Баланс счета
/positions - Открытые позиции
/help - Справка по командам

Бот уже работает и готов к торговле! 🚀
"""
        await self.send_message(chat_id, welcome_text)

    async def _cmd_status(self, chat_id: int, message: Dict):
        """Команда /status"""
        # Здесь должна быть интеграция с основной системой
        status_text = """
📊 <b>Статус системы</b>

🟢 Бот: <i>Активен</i>
🟢 Биржа: <i>Подключена</i>
🟢 AI: <i>Работает</i>

⏱ Время работы: 2ч 15м
📈 Активных позиций: 3
💰 Прибыль за сегодня: +2.5%
"""
        await self.send_message(chat_id, status_text)

    async def _cmd_balance(self, chat_id: int, message: Dict):
        """Команда /balance"""
        # Здесь должна быть интеграция с портфелем
        balance_text = """
💰 <b>Баланс счета</b>

USDT: 10,500.25
├── Доступно: 8,500.25
└── В ордерах: 2,000.00

BTC: 0.15
ETH: 2.5

<i>Общая стоимость: $15,234.50</i>
"""
        await self.send_message(chat_id, balance_text)

    async def _cmd_positions(self, chat_id: int, message: Dict):
        """Команда /positions"""
        positions_text = """
📈 <b>Открытые позиции</b>

1️⃣ <b>BTCUSDT</b> LONG
   Вход: $45,230 | Текущая: $45,450
   PnL: <code>+$220 (+0.49%)</code>

2️⃣ <b>ETHUSDT</b> LONG  
   Вход: $2,340 | Текущая: $2,355
   PnL: <code>+$15 (+0.64%)</code>

3️⃣ <b>SOLUSDT</b> SHORT
   Вход: $98.50 | Текущая: $97.80
   PnL: <code>+$0.70 (+0.71%)</code>

<i>Общий PnL: +$235.70 (+0.58%)</i>
"""
        await self.send_message(chat_id, positions_text)

    async def _cmd_stop(self, chat_id: int, message: Dict):
        """Команда /stop"""
        self.chat_ids.remove(chat_id)
        await self.send_message(
            chat_id,
            "❌ Вы отписались от уведомлений. Используйте /start для возобновления."
        )

    async def _cmd_help(self, chat_id: int, message: Dict):
        """Команда /help"""
        help_text = """
📚 <b>Справка по командам</b>

/start - Начать получать уведомления
/status - Текущий статус системы
/balance - Показать баланс счета  
/positions - Список открытых позиций
/stop - Остановить уведомления
/help - Показать эту справку

<b>Типы уведомлений:</b>
• 🟢 Успешные операции
• 🔴 Ошибки и проблемы
• 🟡 Предупреждения
• 📊 Аналитика и сигналы
• 💰 Финансовые результаты

<i>По всем вопросам: @your_support</i>
"""
        await self.send_message(chat_id, help_text)

    # Обработчики событий
    async def _on_order_placed(self, event: Event):
        """Обработка размещения ордера"""
        data = event.data
        message = f"""
📝 <b>Новый ордер</b>

Символ: <b>{data['symbol']}</b>
Тип: {data['side'].upper()}
Количество: {data['quantity']}
{'Цена: ' + str(data['price']) if data['price'] else 'По рынку'}
Стратегия: <i>{data['strategy']}</i>
"""
        await self._broadcast(message)

    async def _on_order_filled(self, event: Event):
        """Обработка исполнения ордера"""
        data = event.data
        message = f"""
✅ <b>Ордер исполнен</b>

Символ: <b>{data['symbol']}</b>
Тип: {data['side'].upper()}
Количество: {data['quantity']}
Цена: {data['price']}
"""
        await self._broadcast(message)

    async def _on_position_opened(self, event: Event):
        """Обработка открытия позиции"""
        data = event.data
        message = f"""
🟢 <b>Открыта позиция</b>

Символ: <b>{data['symbol']}</b>
Направление: {data['side'].upper()}
Объем: ${data['volume']:.2f}
Цена входа: ${data['entry_price']}
"""
        await self._broadcast(message)

    async def _on_position_closed(self, event: Event):
        """Обработка закрытия позиции"""
        data = event.data
        pnl = data['pnl']
        pnl_percent = data['pnl_percent']

        emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"

        message = f"""
{emoji} <b>Закрыта позиция</b>

Символ: <b>{data['symbol']}</b>
PnL: <code>${pnl:+.2f} ({pnl_percent:+.2f}%)</code>
Длительность: {data['duration']}
"""
        await self._broadcast(message)

    async def _on_ai_analysis(self, event: Event):
        """Обработка AI анализа"""
        data = event.data
        message = f"""
🤖 <b>AI Анализ {data['symbol']}</b>

Рекомендация: <b>{data['action']}</b>
Уверенность: {data['confidence']:.1%}
Риск: {data['risk_level']}

<i>{data['reasoning']}</i>
"""
        await self._broadcast(message)

    async def _on_signal_generated(self, event: Event):
        """Обработка торгового сигнала"""
        data = event.data
        message = f"""
📊 <b>Торговый сигнал</b>

Символ: <b>{data['symbol']}</b>
Действие: <b>{data['action']}</b>
Сила сигнала: {data['strength']}/10
Таймфрейм: {data['timeframe']}

{data.get('description', '')}
"""
        await self._broadcast(message)

    async def _on_risk_alert(self, event: Event):
        """Обработка риск-алерта"""
        data = event.data
        message = f"""
⚠️ <b>Предупреждение о риске</b>

Тип: {data['type']}
Уровень: {data['level']}

{data['message']}

<i>Рекомендуется проверить позиции</i>
"""
        await self._broadcast(message)

    async def _on_system_error(self, event: Event):
        """Обработка системной ошибки"""
        data = event.data
        message = f"""
🔴 <b>Системная ошибка</b>

Компонент: {data['component']}
Ошибка: {data['error']}

<i>Система пытается восстановить работу...</i>
"""
        await self._broadcast(message)