# ai/enhanced_analyzer.py
"""
Улучшенный AI анализатор с дополнительными возможностями
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from ai.mock_analyzer import MockAIAnalyzer


class EnhancedAIAnalyzer(MockAIAnalyzer):
    """Улучшенная версия AI анализатора"""

    def __init__(self):
        super().__init__()
        self.news_weight = 0.3
        self.technical_weight = 0.7

    def _determine_trend(self, data: pd.DataFrame) -> str:
        """Определение тренда"""
        if len(data) < 2:
            return 'neutral'

        # Простое определение по направлению цены
        start_price = data['close'].iloc[0]
        end_price = data['close'].iloc[-1]
        change_percent = (end_price - start_price) / start_price * 100

        if change_percent > 2:
            return 'strong_uptrend'
        elif change_percent > 0.5:
            return 'uptrend'
        elif change_percent < -2:
            return 'strong_downtrend'
        elif change_percent < -0.5:
            return 'downtrend'
        else:
            return 'sideways'

    def _find_support_resistance(self, data: pd.DataFrame) -> Dict:
        """Поиск уровней поддержки и сопротивления"""

        # Простой метод: локальные минимумы и максимумы
        highs = data['high'].rolling(window=10).max()
        lows = data['low'].rolling(window=10).min()

        current_price = float(data['close'].iloc[-1])

        # Ближайшие уровни
        resistance_levels = highs[highs > current_price].dropna().unique()[-3:] if len(
            highs[highs > current_price]) > 0 else []
        support_levels = lows[lows < current_price].dropna().unique()[:3] if len(lows[lows < current_price]) > 0 else []

        return {
            'nearest_resistance': float(resistance_levels[0]) if len(resistance_levels) > 0 else None,
            'nearest_support': float(support_levels[-1]) if len(support_levels) > 0 else None,
            'resistance_levels': [float(x) for x in resistance_levels],
            'support_levels': [float(x) for x in support_levels]
        }

    async def _enhance_analysis(self, ai_analysis: Dict,
                                technical_data: pd.DataFrame) -> Dict:
        """Улучшение и валидация AI анализа"""

        enhanced = ai_analysis.copy()

        # Добавление дополнительных метрик
        enhanced['technical_validation'] = self._validate_with_technicals(
            ai_analysis,
            technical_data
        )

        # Корректировка уверенности на основе валидации
        validation_score = enhanced['technical_validation']['score']
        original_confidence = enhanced.get('confidence', 0.5)

        # Взвешенная уверенность
        enhanced['adjusted_confidence'] = (
                original_confidence * 0.7 + validation_score * 0.3
        )

        # Добавление риск-скора
        enhanced['risk_score'] = self._calculate_risk_score(
            technical_data,
            enhanced
        )

        # Таймфрейм для позиции
        if 'time_horizon' not in enhanced:
            enhanced['time_horizon'] = self._determine_time_horizon(
                technical_data,
                enhanced
            )

        return enhanced

    def _validate_with_technicals(self, ai_analysis: Dict,
                                  data: pd.DataFrame) -> Dict:
        """Валидация AI анализа техническими индикаторами"""

        validation = {
            'score': 0.5,
            'confirmations': [],
            'conflicts': []
        }

        if len(data) < 20:
            return validation

        current = data.iloc[-1]
        ai_action = ai_analysis.get('action', 'HOLD')

        # Проверка RSI
        if 'rsi' in current:
            rsi_signal = 'BUY' if current['rsi'] < 30 else 'SELL' if current['rsi'] > 70 else 'NEUTRAL'
            if rsi_signal == ai_action:
                validation['confirmations'].append('RSI подтверждает сигнал')
                validation['score'] += 0.1
            elif rsi_signal != 'NEUTRAL' and rsi_signal != ai_action:
                validation['conflicts'].append('RSI противоречит сигналу')
                validation['score'] -= 0.1

        # Проверка EMA кроссовера
        if 'ema_fast' in current and 'ema_slow' in current:
            ema_signal = 'BUY' if current['ema_fast'] > current['ema_slow'] else 'SELL'
            if ema_signal == ai_action:
                validation['confirmations'].append('EMA кроссовер подтверждает')
                validation['score'] += 0.15
            else:
                validation['conflicts'].append('EMA кроссовер противоречит')
                validation['score'] -= 0.15

        # Ограничение score в диапазоне [0, 1]
        validation['score'] = max(0, min(1, validation['score']))

        return validation

    def _calculate_risk_score(self, data: pd.DataFrame,
                              analysis: Dict) -> float:
        """Расчет риск-скора позиции"""

        risk_score = 0.5  # Базовый риск

        # Волатильность
        if len(data) >= 20:
            volatility = data['close'].pct_change().tail(20).std()
            if volatility > 0.05:  # Высокая волатильность
                risk_score += 0.2
            elif volatility < 0.01:  # Низкая волатильность
                risk_score -= 0.1

        # Расстояние до уровней
        if 'stop_loss' in analysis and 'entry_price' in analysis:
            sl_distance = abs(analysis['entry_price'] - analysis['stop_loss']) / analysis['entry_price']
            if sl_distance > 0.05:  # Далекий стоп
                risk_score += 0.15

        # Уверенность AI
        confidence = analysis.get('adjusted_confidence', 0.5)
        if confidence < 0.6:
            risk_score += 0.2
        elif confidence > 0.8:
            risk_score -= 0.1

        return max(0, min(1, risk_score))

    def _determine_time_horizon(self, data: pd.DataFrame,
                                analysis: Dict) -> str:
        """Определение временного горизонта позиции"""

        # На основе волатильности и тренда
        if len(data) >= 50:
            short_trend = self._determine_trend(data.tail(20))
            medium_trend = self._determine_trend(data.tail(50))

            if 'strong' in short_trend and 'strong' in medium_trend:
                return 'medium'  # Сильный тренд - держим дольше
            elif short_trend != medium_trend:
                return 'short'  # Противоречивые сигналы - краткосрочно

        return 'short'  # По умолчанию краткосрочная