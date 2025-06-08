# core/engine/exchange_manager.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
Управление подключениями к биржам - ИСПРАВЛЕНО
"""
from typing import Dict, List, Optional
from loguru import logger
import asyncio

from config.settings import Settings
from core.event_bus import EventBus, Event, EventType
from core.order_manager import OrderManager
from exchange.bybit_client import BybitClient
from exchange.binance_client import BinanceClient


class ExchangeManager:
    """Менеджер подключений к биржам - ИСПРАВЛЕННАЯ ВЕРСИЯ"""

    def __init__(self, settings: Settings, event_bus: EventBus):
        self.settings = settings
        self.event_bus = event_bus
        self.exchanges = {}
        self.order_managers = {}
        self._connection_status = {}

    async def initialize(self):
        """Инициализация подключений к биржам"""
        logger.info("🔌 Инициализация подключений к биржам")

        # Последовательная инициализация для избежания конфликтов
        await self._initialize_bybit()
        await self._initialize_binance()

        if not self.exchanges:
            logger.warning("⚠️ Нет доступных подключений к биржам!")
            logger.info("ℹ️ Это нормально если API ключи не настроены для разработки")
        else:
            logger.info(f"✅ Подключено к биржам: {list(self.exchanges.keys())}")

    async def _initialize_bybit(self):
        """Инициализация Bybit"""
        if not self.settings.bybit_api_key or not self.settings.bybit_api_secret:
            logger.info("⚠️ Bybit API ключи не настроены")
            return

        try:
            logger.info("🔄 Подключение к Bybit...")

            bybit_client = BybitClient(
                self.settings.bybit_api_key,
                self.settings.bybit_api_secret,
                self.settings.bybit_testnet
            )

            # Таймаут для подключения
            await asyncio.wait_for(bybit_client.connect(), timeout=30.0)

            # Тест подключения
            try:
                balance = await asyncio.wait_for(bybit_client.get_balance(), timeout=10.0)
                logger.info(f"✅ Bybit баланс получен: {len(balance)} активов")
            except Exception as balance_error:
                logger.warning(f"⚠️ Не удалось получить баланс Bybit: {balance_error}")
                # Продолжаем, так как подключение может работать

            self.exchanges['bybit'] = bybit_client
            self.order_managers['bybit'] = OrderManager(bybit_client, self.event_bus)
            await self.order_managers['bybit'].start()
            self._connection_status['bybit'] = True

            logger.info("✅ Bybit подключен и готов к торговле")

        except asyncio.TimeoutError:
            logger.error("❌ Timeout подключения к Bybit")
            self._connection_status['bybit'] = False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Bybit: {e}")
            self._connection_status['bybit'] = False

    async def _initialize_binance(self):
        """Инициализация Binance"""
        if not self.settings.binance_api_key or not self.settings.binance_api_secret:
            logger.info("⚠️ Binance API ключи не настроены")
            return

        try:
            logger.info("🔄 Подключение к Binance...")

            binance_client = BinanceClient(
                self.settings.binance_api_key,
                self.settings.binance_api_secret,
                self.settings.binance_testnet
            )

            # Таймаут для подключения
            await asyncio.wait_for(binance_client.connect(), timeout=30.0)

            # Тест подключения
            try:
                balance = await asyncio.wait_for(binance_client.get_balance(), timeout=10.0)
                logger.info(f"✅ Binance баланс получен: {len(balance)} активов")
            except Exception as balance_error:
                logger.warning(f"⚠️ Не удалось получить баланс Binance: {balance_error}")

            self.exchanges['binance'] = binance_client
            self.order_managers['binance'] = OrderManager(binance_client, self.event_bus)
            await self.order_managers['binance'].start()
            self._connection_status['binance'] = True

            logger.info("✅ Binance подключен и готов к торговле")

        except asyncio.TimeoutError:
            logger.error("❌ Timeout подключения к Binance")
            self._connection_status['binance'] = False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Binance: {e}")
            self._connection_status['binance'] = False

    async def get_market_data(self, symbol: str, timeframe: str, limit: int = 100):
        """Получение рыночных данных с первой доступной биржи"""
        if not self.exchanges:
            logger.warning("⚠️ Нет подключенных бирж, используются тестовые данные")
            from utils.helpers import create_sample_data
            return create_sample_data(symbol, periods=limit)

        # Пробуем каждую биржу по очереди
        for exchange_name, exchange in self.exchanges.items():
            try:
                logger.debug(f"📡 Получение данных {symbol} с {exchange_name}")

                ohlcv = await asyncio.wait_for(
                    exchange.get_ohlcv(symbol, timeframe, limit),
                    timeout=15.0
                )

                if ohlcv and len(ohlcv) > 0:
                    import pandas as pd
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)

                    logger.info(f"✅ Получено {len(df)} свечей {symbol} с {exchange_name}")
                    return df

            except asyncio.TimeoutError:
                logger.warning(f"⏰ Timeout получения данных с {exchange_name}")
                continue
            except Exception as e:
                logger.warning(f"⚠️ Ошибка получения данных с {exchange_name}: {e}")
                continue

        # Если все биржи недоступны
        logger.warning(f"⚠️ Не удалось получить реальные данные для {symbol}, используются тестовые")
        from utils.helpers import create_sample_data
        return create_sample_data(symbol, periods=limit)

    async def place_order(self, symbol: str, side: str, order_type: str,
                          quantity: float, price: float = None, strategy: str = "manual"):
        """Размещение ордера через первую доступную биржу"""
        if not self.order_managers:
            raise Exception("No order managers available")

        # Выбираем первую доступную биржу
        for exchange_name, order_manager in self.order_managers.items():
            try:
                from decimal import Decimal

                logger.info(f"📝 Размещение ордера {symbol} {side} на {exchange_name}")

                result = await order_manager.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=Decimal(str(quantity)),
                    price=Decimal(str(price)) if price else None,
                    strategy=strategy
                )

                logger.info(f"✅ Ордер размещен: {result.order.id}")
                return result

            except Exception as e:
                logger.error(f"❌ Ошибка размещения ордера на {exchange_name}: {e}")
                continue

        raise Exception("Failed to place order on any exchange")

    async def get_connected_exchanges(self) -> List[str]:
        """Получение списка подключенных бирж"""
        connected = []
        for name, status in self._connection_status.items():
            if status and name in self.exchanges:
                connected.append(name)
        return connected

    async def get_connection_status(self) -> Dict[str, bool]:
        """Получение статуса подключений"""
        return self._connection_status.copy()

    async def test_all_connections(self) -> Dict[str, bool]:
        """Тестирование всех подключений"""
        results = {}

        for exchange_name, exchange in self.exchanges.items():
            try:
                # Простой тест - получение тикера
                ticker = await asyncio.wait_for(
                    exchange.get_ticker("BTCUSDT"),
                    timeout=10.0
                )
                results[exchange_name] = ticker is not None
                logger.info(f"✅ {exchange_name} connection test passed")

            except Exception as e:
                results[exchange_name] = False
                logger.warning(f"⚠️ {exchange_name} connection test failed: {e}")

        return results

    async def stop(self):
        """Остановка всех подключений"""
        logger.info("🔌 Остановка подключений к биржам")

        # Остановка order managers
        for exchange_name, order_manager in self.order_managers.items():
            try:
                await order_manager.stop()
                logger.info(f"✅ Order manager {exchange_name} остановлен")
            except Exception as e:
                logger.error(f"❌ Ошибка остановки order manager {exchange_name}: {e}")

        # Закрытие подключений к биржам
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.disconnect()
                logger.info(f"✅ {exchange_name} отключен")
            except Exception as e:
                logger.error(f"❌ Ошибка отключения {exchange_name}: {e}")

        self.exchanges.clear()
        self.order_managers.clear()
        self._connection_status.clear()

        logger.info("✅ Все подключения к биржам закрыты")

    async def get_balance_summary(self) -> Dict[str, Dict]:
        """Получение сводки балансов со всех бирж"""
        summary = {}

        for exchange_name, exchange in self.exchanges.items():
            try:
                balance = await asyncio.wait_for(exchange.get_balance(), timeout=10.0)
                summary[exchange_name] = {
                    'connected': True,
                    'balances': balance,
                    'total_assets': len(balance)
                }
            except Exception as e:
                summary[exchange_name] = {
                    'connected': False,
                    'error': str(e),
                    'balances': {},
                    'total_assets': 0
                }

        return summary