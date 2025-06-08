# core/engine.py - ПОЛНАЯ РЕАЛИЗАЦИЯ
import asyncio
from typing import Dict, List, Optional
from loguru import logger
from config.settings import Settings
from config.trading_config import TradingConfig
from core.event_bus import EventBus
from core.portfolio import Portfolio
from core.order_manager import OrderManager
from risk.risk_manager import RiskManager
from data.collectors.exchange_collector import ExchangeDataCollector
from ai.mock_analyzer import MockAIAnalyzer
from trading.strategies.simple_momentum import SimpleMomentumStrategy
from notifications.telegram_bot import TelegramBot


class TradingEngine:
    """Главный оркестратор торговой системы"""

    def __init__(self, settings: Settings, trading_config: TradingConfig):
        self.settings = settings
        self.trading_config = trading_config
        self.is_running = False

        # Инициализация компонентов
        self.event_bus = EventBus()
        self.portfolio = Portfolio()
        self.risk_manager = RiskManager(trading_config.risk, self.portfolio)

        # Сборщики данных
        self.exchanges = {}
        self.data_collectors = {}

        # AI анализатор
        self.ai_analyzer = MockAIAnalyzer()

        # Стратегии
        self.strategies = []

        # Менеджеры
        self.order_managers = {}

        # Telegram бот
        self.telegram_bot = None

    async def initialize(self):
        """Инициализация всех компонентов"""
        logger.info("Инициализация торгового движка...")

        # Запуск шины событий
        await self.event_bus.start()

        # Инициализация бирж
        await self._initialize_exchanges()

        # Инициализация стратегий
        await self._initialize_strategies()

        # Инициализация Telegram бота
        if self.settings.telegram_bot_token:
            self.telegram_bot = TelegramBot(
                self.settings.telegram_bot_token,
                self.event_bus
            )
            await self.telegram_bot.start()

        logger.info("Торговый движок инициализирован")

    async def _initialize_exchanges(self):
        """Инициализация подключений к биржам"""

        # Bybit
        if self.settings.bybit_api_key:
            try:
                collector = ExchangeDataCollector(
                    'bybit',
                    self.settings.bybit_api_key,
                    self.settings.bybit_api_secret,
                    self.settings.bybit_testnet
                )

                if await collector.test_connection():
                    self.data_collectors['bybit'] = collector
                    logger.info("Bybit подключен успешно")
                else:
                    logger.warning("Не удалось подключиться к Bybit")

            except Exception as e:
                logger.error(f"Ошибка подключения к Bybit: {e}")

        # Binance
        if self.settings.binance_api_key:
            try:
                collector = ExchangeDataCollector(
                    'binance',
                    self.settings.binance_api_key,
                    self.settings.binance_api_secret,
                    self.settings.binance_testnet
                )

                if await collector.test_connection():
                    self.data_collectors['binance'] = collector
                    logger.info("Binance подключен успешно")
                else:
                    logger.warning("Не удалось подключиться к Binance")

            except Exception as e:
                logger.error(f"Ошибка подключения к Binance: {e}")

    async def _initialize_strategies(self):
        """Инициализация торговых стратегий"""

        # Простая моментум стратегия
        momentum_config = {
            'indicators': self.trading_config.technical_indicators,
            'position_size_percent': self.trading_config.risk.max_position_size_percent
        }

        momentum_strategy = SimpleMomentumStrategy(momentum_config)
        momentum_strategy.active = True
        self.strategies.append(momentum_strategy)

        logger.info(f"Инициализировано стратегий: {len(self.strategies)}")

    async def start(self):
        """Запуск торговой системы"""
        if self.is_running:
            logger.warning("Движок уже запущен")
            return

        await self.initialize()
        self.is_running = True
        logger.info("Торговый движок запущен")

        # Основной цикл работы
        try:
            while self.is_running:
                await self._main_loop()
                await asyncio.sleep(5)  # Цикл каждые 5 секунд
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        finally:
            await self.stop()

    async def stop(self):
        """Остановка торговой системы"""
        logger.info("Остановка торгового движка...")
        self.is_running = False

        # Закрытие соединений с биржами
        for collector in self.data_collectors.values():
            await collector.close()

        # Остановка Telegram бота
        if self.telegram_bot:
            await self.telegram_bot.stop()

        # Остановка шины событий
        await self.event_bus.stop()

        logger.info("Торговый движок остановлен")

    async def _main_loop(self):
        """Основной цикл работы"""
        try:
            # Анализ каждой торговой пары
            for trading_pair in self.trading_config.trading_pairs:
                if not trading_pair.enabled:
                    continue

                await self._analyze_symbol(trading_pair.symbol)

        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")

    async def _analyze_symbol(self, symbol: str):
        """Анализ конкретного символа"""
        try:
            # Получение данных с первой доступной биржи
            if not self.data_collectors:
                return

            collector = list(self.data_collectors.values())[0]

            # Получение данных
            ohlcv_data = await collector.get_ohlcv(
                symbol,
                self.trading_config.primary_timeframe,
                100
            )

            if ohlcv_data.empty:
                return

            # Анализ через активные стратегии
            for strategy in self.strategies:
                if not strategy.active:
                    continue

                analysis = await strategy.analyze(ohlcv_data, symbol)

                # Проверка условий входа
                if await strategy.should_enter(analysis):
                    logger.info(f"Сигнал на вход: {symbol} - {analysis.get('recommendation')}")
                    # Здесь будет логика размещения ордеров

        except Exception as e:
            logger.error(f"Ошибка анализа {symbol}: {e}")