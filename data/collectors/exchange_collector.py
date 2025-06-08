# data/collectors/exchange_collector.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
import ccxt.pro as ccxt
import pandas as pd
from typing import Dict, List, Optional
from loguru import logger
import asyncio


class ExchangeError(Exception):
    """Локальное определение ошибки для избежания циклического импорта"""
    pass


class DataError(Exception):
    """Локальное определение ошибки для избежания циклического импорта"""
    pass


class ExchangeDataCollector:
    """Сборщик данных с криптобирж - исправленная версия"""

    def __init__(self, exchange_name: str, api_key: str = None,
                 api_secret: str = None, testnet: bool = True):
        self.exchange_name = exchange_name
        self.testnet = testnet
        self.exchange = None

        try:
            # Создание объекта биржи
            exchange_class = getattr(ccxt, exchange_name.lower())

            # Настройки для testnet
            config = {
                'enableRateLimit': True,
                'timeout': 30000,  # 30 секунд timeout
            }

            # Добавляем API ключи только если они есть
            if api_key and api_secret:
                config['apiKey'] = api_key
                config['secret'] = api_secret

            # Специфичные настройки для разных бирж
            if exchange_name.lower() == 'bybit':
                if testnet:
                    config['testnet'] = True
                    config['sandbox'] = True
                config['options'] = {
                    'defaultType': 'linear',  # USDT perpetual
                    'adjustForTimeDifference': True,
                    'recvWindow': 20000
                }

            elif exchange_name.lower() == 'binance':
                if testnet:
                    config['testnet'] = True
                    config['sandbox'] = True
                config['options'] = {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True
                }

            self.exchange = exchange_class(config)

        except AttributeError:
            raise ExchangeError(f"Неподдерживаемая биржа: {exchange_name}")
        except Exception as e:
            raise ExchangeError(f"Ошибка подключения к {exchange_name}: {e}")

    async def get_ohlcv(self, symbol: str, timeframe: str = '5m',
                        limit: int = 100) -> pd.DataFrame:
        """Получение OHLCV данных с улучшенной обработкой ошибок"""
        try:
            # Проверяем подключение
            if not self.exchange:
                raise DataError("Exchange не инициализирован")

            # Загружаем рынки если еще не загружены
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                await self.exchange.load_markets()

            # Получаем данные
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            if not ohlcv:
                raise DataError(f"Нет данных для {symbol}")

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            logger.debug(f"Получено {len(df)} свечей для {symbol}")
            return df

        except Exception as e:
            logger.error(f"Ошибка получения OHLCV для {symbol}: {e}")
            # Возвращаем пустой DataFrame вместо исключения
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

    async def get_ticker(self, symbol: str) -> Dict:
        """Получение тикера с обработкой ошибок"""
        try:
            if not self.exchange:
                raise DataError("Exchange не инициализирован")

            # Загружаем рынки если еще не загружены
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                await self.exchange.load_markets()

            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker

        except Exception as e:
            logger.error(f"Ошибка получения тикера для {symbol}: {e}")
            # Возвращаем заглушку
            return {
                'symbol': symbol,
                'last': 0.0,
                'bid': 0.0,
                'ask': 0.0,
                'volume': 0.0
            }

    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """Получение стакана заявок"""
        try:
            if not self.exchange:
                raise DataError("Exchange не инициализирован")

            return await self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            logger.error(f"Ошибка получения стакана для {symbol}: {e}")
            return {'bids': [], 'asks': []}

    async def test_connection(self) -> bool:
        """Тест подключения к бирже с улучшенной обработкой"""
        try:
            if not self.exchange:
                logger.error("Exchange объект не создан")
                return False

            # Попытка загрузить рынки
            await asyncio.wait_for(self.exchange.load_markets(), timeout=30.0)

            # Проверяем что рынки загружены
            if not self.exchange.markets:
                logger.error("Рынки не загружены")
                return False

            logger.info(f"Подключение к {self.exchange_name} успешно. Загружено {len(self.exchange.markets)} рынков")
            return True

        except asyncio.TimeoutError:
            logger.error(f"Timeout при подключении к {self.exchange_name}")
            return False
        except Exception as e:
            logger.error(f"Ошибка подключения к {self.exchange_name}: {e}")
            return False

    async def close(self):
        """Закрытие соединения"""
        if self.exchange:
            try:
                await self.exchange.close()
                logger.debug(f"Соединение с {self.exchange_name} закрыто")
            except Exception as e:
                logger.error(f"Ошибка закрытия соединения с {self.exchange_name}: {e}")