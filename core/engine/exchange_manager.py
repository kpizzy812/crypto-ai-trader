# core/engine/exchange_manager.py
"""
Управление подключениями к биржам
"""
from typing import Dict, List
from loguru import logger

from config.settings import Settings
from core.event_bus import EventBus, Event, EventType
from core.order_manager import OrderManager
from exchange.bybit_client import BybitClient
from exchange.binance_client import BinanceClient


class ExchangeManager:
    """Менеджер подключений к биржам"""

    def __init__(self, settings: Settings, event_bus: EventBus):
        self.settings = settings
        self.event_bus = event_bus
        self.exchanges = {}
        self.order_managers = {}

    async def initialize(self):
        """Инициализация подключений к биржам"""
        logger.info("🔌 Инициализация подключений к биржам")

        await self._initialize_bybit()
        await self._initialize_binance()

        if not self.exchanges:
            logger.error("❌ Нет доступных подключений к биржам!")
            raise Exception("No exchange connections available")

        logger.info(f"✅ Подключено к биржам: {list(self.exchanges.keys())}")

    async def _initialize_bybit(self):
        """Инициализация Bybit"""
        if not self.settings.bybit_api_key:
            logger.info("⚠️ Bybit API ключи не настроены")
            return

        try:
            bybit_client = BybitClient(
                self.settings.bybit_api_key,
                self.settings.bybit_api_secret,
                self.settings.bybit_testnet
            )
            await bybit_client.connect()

            self.exchanges['bybit'] = bybit_client
            self.order_managers['bybit'] = OrderManager(bybit_client, self.event_bus)
            await self.order_managers['bybit'].start()

            logger.info("✅ Bybit подключен и готов к торговле")

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Bybit: {e}")

    async def _initialize_binance(self):
        """Инициализация Binance"""
        if not self.settings.binance_api_key:
            logger.info("⚠️ Binance API ключи не настроены")
            return

        try:
            binance_client = BinanceClient(
                self.settings.binance_api_key,
                self.settings.binance_api_secret,
                self.settings.binance_testnet
            )
            await binance_client.connect()

            self.exchanges['binance'] = binance_client
            self.order_managers['binance'] = OrderManager(binance_client, self.event_bus)
            await self.order_managers['binance'].start()

            logger.info("✅ Binance подключен и готов к торговле")

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Binance: {e}")

    async def get_market_data(self, symbol: str, timeframe: str, limit: int = 100):
        """Получение рыночных данных с первой доступной биржи"""
        if not self.exchanges:
            raise Exception("No exchanges available")

        exchange_name = list(self.exchanges.keys())[0]
        exchange = self.exchanges[exchange_name]

        try:
            ohlcv = await exchange.get_ohlcv(symbol, timeframe, limit)

            import pandas as pd
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df

        except Exception as e:
            logger.error(f"❌ Ошибка получения данных для {symbol}: {e}")
            import pandas as pd
            return pd.DataFrame()

    async def place_order(self, symbol: str, side: str, order_type: str,
                          quantity: float, price: float = None, strategy: str = "manual"):
        """Размещение ордера через первую доступную биржу"""
        if not self.order_managers:
            raise Exception("No order managers available")

        exchange_name = list(self.order_managers.keys())[0]
        order_manager = self.order_managers[exchange_name]

        from decimal import Decimal

        return await order_manager.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(price)) if price else None,
            strategy=strategy
        )

    async def get_connected_exchanges(self) -> List[str]:
        """Получение списка подключенных бирж"""
        return list(self.exchanges.keys())

    async def stop(self):
        """Остановка всех подключений"""
        logger.info("🔌 Остановка подключений к биржам")

        # Остановка order managers
        for order_manager in self.order_managers.values():
            await order_manager.stop()

        # Закрытие подключений к биржам
        for exchange in self.exchanges.values():
            await exchange.disconnect()

        logger.info("✅ Все подключения к биржам закрыты")