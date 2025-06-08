# exchange/bybit_client.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
Клиент для работы с Bybit
"""
import ccxt
from typing import Dict, Optional, List
from decimal import Decimal
from loguru import logger
from .base_exchange import BaseExchange, Order


class BybitClient(BaseExchange):
    """Клиент для работы с Bybit"""

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)

    async def connect(self):
        """Подключение к Bybit"""
        try:
            self.exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'testnet': self.testnet,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'linear',  # Для фьючерсов
                    'adjustForTimeDifference': True
                }
            })

            # Загрузка рынков - ИСПРАВЛЕНИЕ: убираем await для синхронного метода
            try:
                if hasattr(self.exchange, 'load_markets'):
                    # Проверяем, является ли метод асинхронным
                    import inspect
                    if inspect.iscoroutinefunction(self.exchange.load_markets):
                        self._markets = await self.exchange.load_markets()
                    else:
                        self._markets = self.exchange.load_markets()
                else:
                    self._markets = {}

                logger.info(f"Подключено к Bybit {'testnet' if self.testnet else 'mainnet'}")

            except Exception as markets_error:
                logger.warning(f"Не удалось загрузить рынки Bybit: {markets_error}")
                self._markets = {}

        except Exception as e:
            logger.error(f"Ошибка подключения к Bybit: {e}")
            raise

    async def disconnect(self):
        """Отключение от Bybit"""
        if self.exchange:
            try:
                # Проверяем есть ли метод close и является ли он асинхронным
                if hasattr(self.exchange, 'close'):
                    import inspect
                    if inspect.iscoroutinefunction(self.exchange.close):
                        await self.exchange.close()
                    else:
                        self.exchange.close()
                logger.info("Отключено от Bybit")
            except Exception as e:
                logger.warning(f"Ошибка при отключении от Bybit: {e}")

    async def get_balance(self) -> Dict[str, Dict]:
        """Получение балансов"""
        try:
            # Проверяем асинхронность метода
            import inspect
            if inspect.iscoroutinefunction(self.exchange.fetch_balance):
                balance = await self.exchange.fetch_balance()
            else:
                balance = self.exchange.fetch_balance()

            # Форматирование для унифицированного интерфейса
            formatted_balance = {}
            for currency, data in balance.get('total', {}).items():
                if data > 0:
                    formatted_balance[currency] = {
                        'free': Decimal(str(balance.get('free', {}).get(currency, 0))),
                        'used': Decimal(str(balance.get('used', {}).get(currency, 0))),
                        'total': Decimal(str(data))
                    }

            return formatted_balance

        except Exception as e:
            logger.error(f"Ошибка получения баланса Bybit: {e}")
            raise

    async def place_order(self, symbol: str, side: str, order_type: str,
                          quantity: Decimal, price: Optional[Decimal] = None) -> Order:
        """Размещение ордера"""
        try:
            # Валидация символа
            if not self._validate_symbol(symbol):
                raise ValueError(f"Неверный символ: {symbol}")

            # Параметры ордера
            params = {
                'timeInForce': 'GTC',  # Good Till Cancel
                'reduceOnly': False
            }

            # Размещение ордера - проверяем асинхронность
            import inspect

            if order_type == 'market':
                if inspect.iscoroutinefunction(self.exchange.create_market_order):
                    raw_order = await self.exchange.create_market_order(
                        symbol, side, float(quantity), None, params
                    )
                else:
                    raw_order = self.exchange.create_market_order(
                        symbol, side, float(quantity), None, params
                    )
            else:
                if price is None:
                    raise ValueError("Цена обязательна для лимитного ордера")

                if inspect.iscoroutinefunction(self.exchange.create_limit_order):
                    raw_order = await self.exchange.create_limit_order(
                        symbol, side, float(quantity), float(price), params
                    )
                else:
                    raw_order = self.exchange.create_limit_order(
                        symbol, side, float(quantity), float(price), params
                    )

            # Конвертация в наш формат
            order = self._normalize_order(raw_order)
            logger.info(f"Размещен ордер на Bybit: {order.id}")

            return order

        except Exception as e:
            logger.error(f"Ошибка размещения ордера на Bybit: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Отмена ордера"""
        try:
            import inspect
            if inspect.iscoroutinefunction(self.exchange.cancel_order):
                await self.exchange.cancel_order(order_id, symbol)
            else:
                self.exchange.cancel_order(order_id, symbol)

            logger.info(f"Отменен ордер на Bybit: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отмены ордера на Bybit: {e}")
            return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Получение информации об ордере"""
        try:
            import inspect
            if inspect.iscoroutinefunction(self.exchange.fetch_order):
                raw_order = await self.exchange.fetch_order(order_id, symbol)
            else:
                raw_order = self.exchange.fetch_order(order_id, symbol)

            return self._normalize_order(raw_order)

        except Exception as e:
            logger.error(f"Ошибка получения ордера с Bybit: {e}")
            return None