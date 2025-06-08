# utils/helpers.py - ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
"""
Вспомогательные функции
"""
import hashlib
import secrets
from typing import Any, Dict, List
from decimal import Decimal, ROUND_DOWN
import pandas as pd
from datetime import datetime, timedelta


def generate_order_id() -> str:
    """Генерация уникального ID ордера"""
    return f"order_{int(datetime.utcnow().timestamp() * 1000)}_{secrets.token_hex(4)}"


def generate_position_id() -> str:
    """Генерация уникального ID позиции"""
    return f"pos_{int(datetime.utcnow().timestamp() * 1000)}_{secrets.token_hex(4)}"


def round_price(price: Decimal, tick_size: Decimal) -> Decimal:
    """Округление цены до tick size"""
    return (price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size


def round_quantity(quantity: Decimal, min_quantity: Decimal) -> Decimal:
    """Округление количества до минимального размера"""
    return (quantity / min_quantity).quantize(Decimal('1'), rounding=ROUND_DOWN) * min_quantity


def calculate_commission(price: Decimal, quantity: Decimal,
                         commission_rate: Decimal = Decimal('0.001')) -> Decimal:
    """Расчет комиссии"""
    return price * quantity * commission_rate


def format_currency(amount: float, decimals: int = 2) -> str:
    """Форматирование валюты"""
    return f"${amount:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Форматирование процентов"""
    return f"{value:.{decimals}f}%"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Безопасное деление"""
    return numerator / denominator if denominator != 0 else default


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Расчет процентного изменения"""
    return safe_divide((new_value - old_value), old_value) * 100


def validate_symbol(symbol: str) -> bool:
    """Валидация торгового символа"""
    return len(symbol) >= 3 and symbol.replace('/', '').replace('-', '').isalnum()


def validate_timeframe(timeframe: str) -> bool:
    """Валидация таймфрейма"""
    valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    return timeframe in valid_timeframes


def merge_ohlcv_data(data_sources: List[pd.DataFrame]) -> pd.DataFrame:
    """Объединение OHLCV данных из разных источников"""
    if not data_sources:
        return pd.DataFrame()

    # Объединение по индексу (timestamp)
    merged = data_sources[0]
    for df in data_sources[1:]:
        merged = merged.combine_first(df)

    return merged.sort_index()


def resample_ohlcv(df: pd.DataFrame, new_timeframe: str) -> pd.DataFrame:
    """Ресэмплинг OHLCV данных в другой таймфрейм"""

    # Маппинг таймфреймов pandas
    timeframe_mapping = {
        '1m': '1T', '3m': '3T', '5m': '5T', '15m': '15T', '30m': '30T',
        '1h': '1H', '2h': '2H', '4h': '4H', '6h': '6H', '8h': '8H', '12h': '12H',
        '1d': '1D', '3d': '3D', '1w': '1W', '1M': '1M'
    }

    if new_timeframe not in timeframe_mapping:
        raise ValueError(f"Неподдерживаемый таймфрейм: {new_timeframe}")

    pandas_freq = timeframe_mapping[new_timeframe]

    resampled = df.resample(pandas_freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()

    return resampled


def create_sample_data(symbol: str, periods: int = 100,
                       start_price: float = 100.0) -> pd.DataFrame:
    """Создание тестовых данных для разработки"""

    import numpy as np

    # Генерация временных меток
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=periods * 5)
    timestamps = pd.date_range(start_time, end_time, periods=periods)

    # Генерация цен (случайное блуждание)
    np.random.seed(42)  # Для воспроизводимости
    returns = np.random.normal(0, 0.02, periods)  # 2% волатильность
    prices = [start_price]

    for ret in returns[1:]:
        new_price = prices[-1] * (1 + ret)
        prices.append(new_price)

    # Создание OHLCV
    data = []
    for i, (timestamp, close) in enumerate(zip(timestamps, prices)):
        # Генерация open, high, low на основе close
        open_price = prices[i - 1] if i > 0 else close
        high = max(open_price, close) * np.random.uniform(1.0, 1.02)
        low = min(open_price, close) * np.random.uniform(0.98, 1.0)
        volume = np.random.uniform(1000, 10000)

        data.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(data, index=timestamps)
    return df


def hash_string(text: str) -> str:
    """Хэширование строки"""
    return hashlib.sha256(text.encode()).hexdigest()


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Разбиение списка на чанки"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def retry_async(max_attempts: int = 3, delay: float = 1.0):
    """Декоратор для повторных попыток асинхронных функций"""
    import asyncio
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay * (2 ** attempt))  # Экспоненциальная задержка
                    else:
                        break

            raise last_exception

        return wrapper

    return decorator