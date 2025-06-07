# trading/strategies/simple_momentum.py
from .base_strategy import BaseStrategy
from data.processors.technical_processor import TechnicalProcessor
import pandas as pd
from typing import Dict, Any


class SimpleMomentumStrategy(BaseStrategy):
    """Простая моментум стратегия для Phase 0"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("SimpleMomentum", config)
        self.processor = TechnicalProcessor()

    async def analyze(self, market_data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Анализ на основе моментума"""

        # Добавление технических индикаторов
        processed_data = self.processor.process_ohlcv(market_data, self.config.get('indicators', {}))

        # Получение сигналов
        signals = self.processor.get_market_signals(processed_data)

        # Анализ моментума
        momentum_score = self._calculate_momentum_score(processed_data)

        return {
            "symbol": symbol,
            "strategy": self.name,
            "momentum_score": momentum_score,
            "technical_signals": signals,
            "recommendation": self._get_recommendation(momentum_score, signals),
            "confidence": abs(momentum_score) / 100,  # Нормализованная уверенность
            "processed_data": processed_data.tail(5)  # Последние 5 записей для анализа
        }

    def _calculate_momentum_score(self, df: pd.DataFrame) -> float:
        """Расчет оценки моментума (-100 до +100)"""
        if len(df) < 10:
            return 0.0

        current = df.iloc[-1]
        score = 0

        # RSI компонент
        if 'rsi' in current and not pd.isna(current['rsi']):
            if current['rsi'] > 70:
                score -= 30
            elif current['rsi'] < 30:
                score += 30
            else:
                # Нейтральная зона RSI
                score += (50 - current['rsi']) * 0.4

        # EMA тренд
        if all(x in current for x in ['ema_fast', 'ema_slow']) and not any(
                pd.isna(current[x]) for x in ['ema_fast', 'ema_slow']):
            ema_diff = (current['ema_fast'] - current['ema_slow']) / current['ema_slow'] * 100
            score += min(max(ema_diff * 10, -30), 30)

        # Объемный анализ
        if 'volume_sma' in current and not pd.isna(current['volume_sma']):
            volume_ratio = current['volume'] / current['volume_sma']
            if volume_ratio > 1.2:
                score *= 1.2  # Усиление сигнала при высоком объеме

        # Боллинджер позиция
        if all(x in current for x in ['bb_upper', 'bb_lower', 'bb_middle']) and not any(
                pd.isna(current[x]) for x in ['bb_upper', 'bb_lower', 'bb_middle']):
            bb_position = (current['close'] - current['bb_middle']) / (current['bb_upper'] - current['bb_middle'])
            if bb_position > 0.8:
                score -= 20  # Близко к верхней полосе
            elif bb_position < -0.8:
                score += 20  # Близко к нижней полосе

        return max(min(score, 100), -100)  # Ограничение в диапазоне [-100, 100]

    def _get_recommendation(self, momentum_score: float, signals: Dict[str, Any]) -> str:
        """Получение рекомендации на основе анализа"""

        # Подсчет сигналов
        buy_signals = len([s for s in signals.get('signals', []) if s.get('signal') == 'BUY'])
        sell_signals = len([s for s in signals.get('signals', []) if s.get('signal') == 'SELL'])

        # Комбинированное решение
        if momentum_score > 30 and buy_signals >= sell_signals:
            return "BUY"
        elif momentum_score < -30 and sell_signals >= buy_signals:
            return "SELL"
        else:
            return "HOLD"

    async def should_enter(self, analysis: Dict[str, Any]) -> bool:
        """Проверка условий входа"""
        recommendation = analysis.get('recommendation', 'HOLD')
        confidence = analysis.get('confidence', 0)

        # Вход только при высокой уверенности
        return recommendation in ['BUY', 'SELL'] and confidence > 0.6

    async def should_exit(self, analysis: Dict[str, Any], position: Dict[str, Any]) -> bool:
        """Проверка условий выхода"""
        recommendation = analysis.get('recommendation', 'HOLD')
        position_side = position.get('side', '')

        # Выход при противоположном сигнале или HOLD
        if position_side == 'BUY' and recommendation in ['SELL', 'HOLD']:
            return True
        elif position_side == 'SELL' and recommendation in ['BUY', 'HOLD']:
            return True

        return False