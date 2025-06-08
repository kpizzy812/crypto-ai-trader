# exchange/binance_client.py - НЕДОСТАЮЩИЙ ФАЙЛ
"""
Клиент для работы с Binance
"""
import ccxt
from typing import Dict, Optional, List
from decimal import Decimal
from loguru import logger
from .base_exchange import BaseExchange, Order


class BinanceClient(BaseExchange):
    """Клиент для работы с Binance"""

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)

    async def connect(self):
        """Подключение к Binance"""
        try:
            self.exchange = ccxt.binance({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'testnet': self.testnet,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # Для фьючерсов
                    'adjustForTimeDifference': True
                }
            })

            # Загрузка рынков
            self._markets = await self.exchange.load_markets()
            logger.info(f"Подключено к Binance {'testnet' if self.testnet else 'mainnet'}")

        except Exception as e:
            logger.error(f"Ошибка подключения к Binance: {e}")
            raise

    async def disconnect(self):
        """Отключение от Binance"""
        if self.exchange:
            await self.exchange.close()
            logger.info("Отключено от Binance")

    async def get_balance(self) -> Dict[str, Dict]:
        """Получение балансов"""
        try:
            balance = await self.exchange.fetch_balance()

            # Форматирование для унифицированного интерфейса
            formatted_balance = {}
            for currency, data in balance['total'].items():
                if data > 0:
                    formatted_balance[currency] = {
                        'free': Decimal(str(balance['free'].get(currency, 0))),
                        'used': Decimal(str(balance['used'].get(currency, 0))),
                        'total': Decimal(str(data))
                    }

            return formatted_balance

        except Exception as e:
            logger.error(f"Ошибка получения баланса Binance: {e}")
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

            # Размещение ордера
            if order_type == 'market':
                raw_order = await self.exchange.create_market_order(
                    symbol, side, float(quantity), params
                )
            else:
                if price is None:
                    raise ValueError("Цена обязательна для лимитного ордера")

                raw_order = await self.exchange.create_limit_order(
                    symbol, side, float(quantity), float(price), params
                )

            # Конвертация в наш формат
            order = self._normalize_order(raw_order)
            logger.info(f"Размещен ордер на Binance: {order.id}")

            return order

        except Exception as e:
            logger.error(f"Ошибка размещения ордера на Binance: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Отмена ордера"""
        try:
            await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Отменен ордер на Binance: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отмены ордера на Binance: {e}")
            return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Получение информации об ордере"""
        try:
            raw_order = await self.exchange.fetch_order(order_id, symbol)
            return self._normalize_order(raw_order)

        except Exception as e:
            logger.error(f"Ошибка получения ордера с Binance: {e}")
            return None