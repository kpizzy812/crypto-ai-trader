# ai/mock_analyzer.py
import random
from typing import Dict, List
from loguru import logger
import pandas as pd


class MockAIAnalyzer:
    """Mock AI анализатор для Phase 0"""

    def __init__(self):
        self.confidence_threshold = 0.7

    async def analyze_market(self, market_data: pd.DataFrame,
                             symbol: str = "BTCUSDT") -> Dict:
        """Mock анализ рынка"""
        logger.info(f"Запуск mock AI анализа для {symbol}")

        # Имитация анализа с рандомными результатами
        await self._simulate_processing()

        # Генерация mock сигнала
        signal_strength = random.uniform(-1, 1)  # от -1 (сильный SELL) до 1 (сильный BUY)
        confidence = random.uniform(0.3, 0.95)

        # Определение действия
        if abs(signal_strength) < 0.3:
            action = "HOLD"
        elif signal_strength > 0:
            action = "BUY"
        else:
            action = "SELL"

        analysis = {
            "symbol": symbol,
            "action": action,
            "signal_strength": signal_strength,
            "confidence": confidence,
            "reasoning": self._generate_mock_reasoning(action, signal_strength),
            "suggested_entry": self._get_suggested_entry(market_data, action),
            "risk_level": "LOW" if confidence > 0.8 else "MEDIUM" if confidence > 0.6 else "HIGH"
        }

        logger.info(f"AI анализ завершен: {action} с уверенностью {confidence:.2f}")
        return analysis

    async def _simulate_processing(self):
        """Имитация времени обработки"""
        import asyncio
        await asyncio.sleep(random.uniform(0.5, 2.0))

    def _generate_mock_reasoning(self, action: str, strength: float) -> str:
        """Генерация mock объяснения"""
        reasons = {
            "BUY": [
                "Технические индикаторы показывают восходящий тренд",
                "Объем торгов увеличивается на росте",
                "RSI указывает на перепроданность",
                "Пробой важного уровня сопротивления"
            ],
            "SELL": [
                "Формируется медвежий паттерн",
                "Объем торгов снижается",
                "RSI в зоне перекупленности",
                "Отбой от уровня сопротивления"
            ],
            "HOLD": [
                "Рынок находится в боковике",
                "Неопределенные сигналы от индикаторов",
                "Ожидание более четкого сигнала",
                "Низкая волатильность"
            ]
        }

        return random.choice(reasons[action])

    def _get_suggested_entry(self, market_data: pd.DataFrame, action: str) -> float:
        """Получение предполагаемой цены входа"""
        if market_data.empty:
            return 0.0

        current_price = market_data['close'].iloc[-1]

        if action == "BUY":
            return current_price * random.uniform(0.998, 1.002)
        elif action == "SELL":
            return current_price * random.uniform(0.998, 1.002)
        else:
            return current_price