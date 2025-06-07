# core/portfolio.py
"""
Управление портфелем и балансами
"""
from typing import Dict, List, Optional
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
import asyncio


@dataclass
class Asset:
    """Актив в портфеле"""
    symbol: str
    free: Decimal
    locked: Decimal
    total: Decimal
    usd_value: Decimal = Decimal("0")

    @property
    def available(self) -> Decimal:
        return self.free


@dataclass
class Position:
    """Открытая позиция"""
    id: str
    symbol: str
    side: str  # 'long' или 'short'
    entry_price: Decimal
    quantity: Decimal
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    opened_at: datetime = field(default_factory=datetime.utcnow)
    pnl: Decimal = Decimal("0")
    pnl_percent: Decimal = Decimal("0")

    def update_pnl(self, current_price: Decimal):
        """Обновление PnL"""
        if self.side == 'long':
            self.pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - current_price) * self.quantity

        self.pnl_percent = (self.pnl / (self.entry_price * self.quantity)) * 100


class Portfolio:
    """Управление портфелем"""

    def __init__(self, initial_balance: Decimal = Decimal("10000")):
        self.initial_balance = initial_balance
        self.assets: Dict[str, Asset] = {}
        self.positions: Dict[str, Position] = {}
        self.total_value = initial_balance
        self.available_balance = initial_balance
        self._lock = asyncio.Lock()

        # Инициализация с USDT
        self.assets['USDT'] = Asset(
            symbol='USDT',
            free=initial_balance,
            locked=Decimal("0"),
            total=initial_balance
        )

    async def update_asset(self, symbol: str, free: Decimal, locked: Decimal):
        """Обновление баланса актива"""
        async with self._lock:
            total = free + locked

            if symbol in self.assets:
                self.assets[symbol].free = free
                self.assets[symbol].locked = locked
                self.assets[symbol].total = total
            else:
                self.assets[symbol] = Asset(
                    symbol=symbol,
                    free=free,
                    locked=locked,
                    total=total
                )

            logger.debug(f"Обновлен баланс {symbol}: {free} (свободно) + {locked} (заблокировано)")

    async def open_position(self, position: Position) -> bool:
        """Открытие новой позиции"""
        async with self._lock:
            # Проверка доступного баланса
            required_balance = position.entry_price * position.quantity

            if self.assets['USDT'].free < required_balance:
                logger.warning(
                    f"Недостаточно средств для открытия позиции: требуется {required_balance}, доступно {self.assets['USDT'].free}")
                return False

            # Блокировка средств
            self.assets['USDT'].free -= required_balance
            self.assets['USDT'].locked += required_balance

            # Добавление позиции
            self.positions[position.id] = position

            logger.info(
                f"Открыта позиция {position.id}: {position.side} {position.quantity} {position.symbol} @ {position.entry_price}")
            return True

    async def close_position(self, position_id: str, close_price: Decimal) -> Optional[Position]:
        """Закрытие позиции"""
        async with self._lock:
            if position_id not in self.positions:
                logger.warning(f"Позиция {position_id} не найдена")
                return None

            position = self.positions[position_id]
            position.update_pnl(close_price)

            # Расчет результата
            if position.side == 'long':
                result = position.entry_price * position.quantity + position.pnl
            else:
                result = position.entry_price * position.quantity + position.pnl

            # Обновление баланса
            self.assets['USDT'].locked -= position.entry_price * position.quantity
            self.assets['USDT'].free += result
            self.assets['USDT'].total = self.assets['USDT'].free + self.assets['USDT'].locked

            # Удаление позиции
            closed_position = self.positions.pop(position_id)

            logger.info(f"Закрыта позиция {position_id}: PnL = {position.pnl} ({position.pnl_percent:.2f}%)")
            return closed_position

    async def get_portfolio_stats(self) -> Dict:
        """Получение статистики портфеля"""
        async with self._lock:
            # Подсчет общей стоимости
            total_value = self.assets.get('USDT', Asset('USDT', Decimal("0"), Decimal("0"), Decimal("0"))).total

            # Подсчет PnL по открытым позициям
            unrealized_pnl = sum(pos.pnl for pos in self.positions.values())

            # Статистика
            stats = {
                "total_value": total_value,
                "available_balance": self.assets.get('USDT',
                                                     Asset('USDT', Decimal("0"), Decimal("0"), Decimal("0"))).free,
                "locked_balance": self.assets.get('USDT',
                                                  Asset('USDT', Decimal("0"), Decimal("0"), Decimal("0"))).locked,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": total_value - self.initial_balance - unrealized_pnl,
                "total_pnl": total_value - self.initial_balance,
                "roi_percent": ((total_value - self.initial_balance) / self.initial_balance) * 100,
                "positions_count": len(self.positions),
                "assets": {symbol: {
                    "free": asset.free,
                    "locked": asset.locked,
                    "total": asset.total
                } for symbol, asset in self.assets.items()}
            }

            return stats