# exchange/base_exchange.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
Базовый класс для работы с биржами - исправлена асинхронность
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
import ccxt
from loguru import logger
import inspect


@dataclass
class Order:
    """Ордер на бирже"""
    id: str
    symbol: str
    type: str  # 'limit', 'market'
    side: str  # 'buy', 'sell'
    price: Optional[Decimal]
    quantity: Decimal
    status: str  # 'pending', 'filled', 'cancelled'
    filled_quantity: Decimal = Decimal("0")
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class Trade:
    """Исполненная сделка"""
    id: str
    order_id: str
    symbol: str
    side: str
    price: Decimal
    quantity: Decimal
    fee: Decimal
    fee_currency: str
    timestamp: datetime


class BaseExchange(ABC):
    """Базовый класс для работы с биржами"""

    def __init__(self, api_key: str = None, api_secret: str = None,
                 testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.exchange = None
        self._markets = {}

    @abstractmethod
    async def connect(self):
        """Подключение к бирже"""
        pass

    @abstractmethod
    async def disconnect(self):
        """Отключение от биржи"""
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, Dict]:
        """Получение балансов"""
        pass

    @abstractmethod
    async def place_order(self, symbol: str, side: str, order_type: str,
                          quantity: Decimal, price: Optional[Decimal] = None) -> Order:
        """Размещение ордера"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Отмена ордера"""
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Получение информации об ордере"""
        pass

    async def get_ticker(self, symbol: str) -> Dict:
        """Получение текущей цены"""
        try:
            # ИСПРАВЛЕНИЕ: Проверка асинхронности метода
            if inspect.iscoroutinefunction(self.exchange.fetch_ticker):
                return await self.exchange.fetch_ticker(symbol)
            else:
                return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Ошибка получения тикера {symbol}: {e}")
            raise

    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """Получение стакана"""
        try:
            # ИСПРАВЛЕНИЕ: Проверка асинхронности метода
            if inspect.iscoroutinefunction(self.exchange.fetch_order_book):
                return await self.exchange.fetch_order_book(symbol, limit)
            else:
                return self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            logger.error(f"Ошибка получения стакана {symbol}: {e}")
            raise

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List:
        """Получение исторических данных - ИСПРАВЛЕНО"""
        try:
            # ИСПРАВЛЕНИЕ: Правильная проверка асинхронности
            if inspect.iscoroutinefunction(self.exchange.fetch_ohlcv):
                result = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            else:
                result = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            # Убеждаемся что возвращаем список, а не что-то другое
            if isinstance(result, list):
                return result
            else:
                logger.error(f"Неожиданный тип данных OHLCV: {type(result)}")
                return []

        except Exception as e:
            logger.error(f"Ошибка получения OHLCV {symbol}: {e}")
            return []  # Возвращаем пустой список вместо исключения

    def _validate_symbol(self, symbol: str) -> bool:
        """Проверка валидности символа"""
        if not self._markets:
            return True  # Если рынки не загружены, пропускаем проверку
        return symbol in self._markets

    def _normalize_order(self, raw_order: Dict) -> Order:
        """Нормализация ордера из формата биржи"""
        return Order(
            id=raw_order['id'],
            symbol=raw_order['symbol'],
            type=raw_order['type'],
            side=raw_order['side'],
            price=Decimal(str(raw_order.get('price', 0))) if raw_order.get('price') else None,
            quantity=Decimal(str(raw_order['amount'])),
            status=raw_order['status'],
            filled_quantity=Decimal(str(raw_order.get('filled', 0))),
            timestamp=datetime.fromtimestamp(raw_order['timestamp'] / 1000) if raw_order.get(
                'timestamp') else datetime.utcnow()
        )