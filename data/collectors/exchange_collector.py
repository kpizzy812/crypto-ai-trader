import ccxt.pro as ccxt  # Изменено на ccxt.pro для async
import pandas as pd
from typing import Dict, List, Optional
from loguru import logger
from core.exceptions import ExchangeError, DataError


class ExchangeDataCollector:
    """Сборщик данных с криптобирж"""

    def __init__(self, exchange_name: str, api_key: str = None,
                 api_secret: str = None, testnet: bool = True):
        self.exchange_name = exchange_name
        self.testnet = testnet

        try:
            # Создание объекта биржи
            exchange_class = getattr(ccxt, exchange_name.lower())
            self.exchange = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'sandbox': testnet,
                'enableRateLimit': True,
            })
        except AttributeError:
            raise ExchangeError(f"Неподдерживаемая биржа: {exchange_name}")
        except Exception as e:
            raise ExchangeError(f"Ошибка подключения к {exchange_name}: {e}")

    async def get_ohlcv(self, symbol: str, timeframe: str = '5m',
                        limit: int = 100) -> pd.DataFrame:
        """Получение OHLCV данных"""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df
        except Exception as e:
            raise DataError(f"Ошибка получения OHLCV для {symbol}: {e}")

    async def get_ticker(self, symbol: str) -> Dict:
        """Получение тикера"""
        try:
            return await self.exchange.fetch_ticker(symbol)
        except Exception as e:
            raise DataError(f"Ошибка получения тикера для {symbol}: {e}")

    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """Получение стакана заявок"""
        try:
            return await self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            raise DataError(f"Ошибка получения стакана для {symbol}: {e}")

    async def test_connection(self) -> bool:
        """Тест подключения к бирже"""
        try:
            await self.exchange.load_markets()
            logger.info(f"Подключение к {self.exchange_name} успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к {self.exchange_name}: {e}")
            return False

    async def close(self):
        """Закрытие соединения"""
        if self.exchange:
            await self.exchange.close()