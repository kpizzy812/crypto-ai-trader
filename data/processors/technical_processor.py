# data/processors/technical_processor.py
import pandas as pd
import numpy as np
from typing import Dict, Any
from loguru import logger


class TechnicalProcessor:
    """Процессор технических индикаторов"""

    def __init__(self):
        self.indicators = {}

    def calculate_rsi(self, data: pd.Series, period: int = 14) -> pd.Series:
        """Расчет RSI"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """Расчет EMA"""
        return data.ewm(span=period, adjust=False).mean()

    def calculate_sma(self, data: pd.Series, period: int) -> pd.Series:
        """Расчет SMA"""
        return data.rolling(window=period).mean()

    def calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Расчет VWAP"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()

    def calculate_bollinger_bands(self, data: pd.Series, period: int = 20, std_dev: int = 2):
        """Расчет полос Боллинджера"""
        sma = self.calculate_sma(data, period)
        std = data.rolling(window=period).std()

        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }

    def process_ohlcv(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """Обработка OHLCV данных с добавлением индикаторов"""
        result_df = df.copy()

        # RSI
        if 'rsi' in config:
            rsi_period = config['rsi'].get('period', 14)
            result_df['rsi'] = self.calculate_rsi(df['close'], rsi_period)

        # EMA быстрая и медленная
        if 'ema_fast' in config:
            fast_period = config['ema_fast'].get('period', 9)
            result_df['ema_fast'] = self.calculate_ema(df['close'], fast_period)

        if 'ema_slow' in config:
            slow_period = config['ema_slow'].get('period', 21)
            result_df['ema_slow'] = self.calculate_ema(df['close'], slow_period)

        # VWAP
        result_df['vwap'] = self.calculate_vwap(df)

        # Объем SMA
        if 'volume_sma' in config:
            vol_period = config['volume_sma'].get('period', 20)
            result_df['volume_sma'] = self.calculate_sma(df['volume'], vol_period)

        # Полосы Боллинджера
        bb = self.calculate_bollinger_bands(df['close'])
        result_df['bb_upper'] = bb['upper']
        result_df['bb_middle'] = bb['middle']
        result_df['bb_lower'] = bb['lower']

        return result_df

    def get_market_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Получение торговых сигналов на основе технических индикаторов"""
        if len(df) < 2:
            return {"error": "Недостаточно данных для анализа"}

        current = df.iloc[-1]
        previous = df.iloc[-2]

        signals = {
            "timestamp": current.name,
            "price": current['close'],
            "signals": []
        }

        # RSI сигналы
        if 'rsi' in current and not pd.isna(current['rsi']):
            if current['rsi'] > 70:
                signals["signals"].append(
                    {"type": "RSI", "signal": "SELL", "value": current['rsi'], "reason": "Перекупленность"})
            elif current['rsi'] < 30:
                signals["signals"].append(
                    {"type": "RSI", "signal": "BUY", "value": current['rsi'], "reason": "Перепроданность"})

        # EMA кроссовер
        if all(x in current for x in ['ema_fast', 'ema_slow']) and not any(
                pd.isna(current[x]) for x in ['ema_fast', 'ema_slow']):
            if all(x in previous for x in ['ema_fast', 'ema_slow']) and not any(
                    pd.isna(previous[x]) for x in ['ema_fast', 'ema_slow']):
                if current['ema_fast'] > current['ema_slow'] and previous['ema_fast'] <= previous['ema_slow']:
                    signals["signals"].append({"type": "EMA_CROSS", "signal": "BUY", "reason": "Бычий кроссовер EMA"})
                elif current['ema_fast'] < current['ema_slow'] and previous['ema_fast'] >= previous['ema_slow']:
                    signals["signals"].append(
                        {"type": "EMA_CROSS", "signal": "SELL", "reason": "Медвежий кроссовер EMA"})

        # Объемный анализ
        if 'volume_sma' in current and not pd.isna(current['volume_sma']):
            volume_ratio = current['volume'] / current['volume_sma']
            if volume_ratio > 1.5:
                signals["signals"].append(
                    {"type": "VOLUME", "signal": "ATTENTION", "value": volume_ratio, "reason": "Повышенный объем"})

        # Анализ Боллинджера
        if all(x in current for x in ['bb_upper', 'bb_lower']) and not any(
                pd.isna(current[x]) for x in ['bb_upper', 'bb_lower']):
            if current['close'] > current['bb_upper']:
                signals["signals"].append({"type": "BOLLINGER", "signal": "SELL", "reason": "Цена выше верхней полосы"})
            elif current['close'] < current['bb_lower']:
                signals["signals"].append({"type": "BOLLINGER", "signal": "BUY", "reason": "Цена ниже нижней полосы"})

        return signals