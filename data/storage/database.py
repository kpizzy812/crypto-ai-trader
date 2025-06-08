# data/storage/database.py - СИСТЕМА ХРАНЕНИЯ ДАННЫХ
"""
Система хранения данных в базе
"""
import sqlite3
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

Base = declarative_base()


class Trade(Base):
    """Модель сделки"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    quantity = Column(Float, nullable=False)
    pnl = Column(Float)
    strategy = Column(String(50))
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)
    context_json = Column(Text)


class MarketData(Base):
    """Модель рыночных данных"""
    __tablename__ = 'market_data'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    timeframe = Column(String(10), nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)


class DatabaseManager:
    """Менеджер базы данных"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Создание таблиц
        Base.metadata.create_all(bind=self.engine)
        logger.info("База данных инициализирована")

    def save_trade(self, trade_data: Dict) -> int:
        """Сохранение сделки"""
        session = self.SessionLocal()
        try:
            trade = Trade(**trade_data)
            session.add(trade)
            session.commit()
            trade_id = trade.id
            logger.info(f"Сделка сохранена: ID {trade_id}")
            return trade_id
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка сохранения сделки: {e}")
            raise
        finally:
            session.close()

    def save_market_data(self, symbol: str, timeframe: str,
                         ohlcv_data: pd.DataFrame):
        """Сохранение рыночных данных"""
        session = self.SessionLocal()
        try:
            for timestamp, row in ohlcv_data.iterrows():
                market_data = MarketData(
                    symbol=symbol,
                    timestamp=timestamp,
                    timeframe=timeframe,
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume']
                )
                session.merge(market_data)  # merge для избежания дубликатов

            session.commit()
            logger.debug(f"Сохранено {len(ohlcv_data)} записей для {symbol}")

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка сохранения данных: {e}")
            raise
        finally:
            session.close()

    def get_trades(self, symbol: str = None,
                   strategy: str = None,
                   limit: int = 100) -> List[Dict]:
        """Получение сделок"""
        session = self.SessionLocal()
        try:
            query = session.query(Trade)

            if symbol:
                query = query.filter(Trade.symbol == symbol)
            if strategy:
                query = query.filter(Trade.strategy == strategy)

            trades = query.order_by(Trade.opened_at.desc()).limit(limit).all()

            return [
                {
                    'id': t.id,
                    'symbol': t.symbol,
                    'side': t.side,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'quantity': t.quantity,
                    'pnl': t.pnl,
                    'strategy': t.strategy,
                    'opened_at': t.opened_at,
                    'closed_at': t.closed_at
                }
                for t in trades
            ]

        finally:
            session.close()

    def get_market_data(self, symbol: str, timeframe: str,
                        start_date: datetime = None,
                        end_date: datetime = None) -> pd.DataFrame:
        """Получение рыночных данных"""
        session = self.SessionLocal()
        try:
            query = session.query(MarketData).filter(
                MarketData.symbol == symbol,
                MarketData.timeframe == timeframe
            )

            if start_date:
                query = query.filter(MarketData.timestamp >= start_date)
            if end_date:
                query = query.filter(MarketData.timestamp <= end_date)

            data = query.order_by(MarketData.timestamp).all()

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame([
                {
                    'timestamp': d.timestamp,
                    'open': d.open,
                    'high': d.high,
                    'low': d.low,
                    'close': d.close,
                    'volume': d.volume
                }
                for d in data
            ])

            df.set_index('timestamp', inplace=True)
            return df

        finally:
            session.close()