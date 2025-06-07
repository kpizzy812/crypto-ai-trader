# ai/openai_analyzer.py
"""
Интеграция с OpenAI для анализа рынка
"""
import json
from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime
from loguru import logger
import openai
from config.settings import settings


class OpenAIAnalyzer:
    """AI анализатор на базе OpenAI"""

    def __init__(self):
        self.api_key = settings.openai_api_key
        if self.api_key:
            openai.api_key = self.api_key
        else:
            logger.warning("OpenAI API key не установлен")

        self.model = "gpt-4-turbo-preview"
        self.temperature = 0.7

    async def analyze_market(self, market_data: pd.DataFrame, symbol: str,
                             news: Optional[List[str]] = None,
                             technical_indicators: Optional[Dict] = None) -> Dict:
        """Комплексный анализ рынка с помощью AI"""

        if not self.api_key:
            logger.error("OpenAI API key отсутствует")
            return self._get_default_analysis(symbol)

        try:
            # Подготовка контекста для анализа
            context = self._prepare_context(market_data, symbol, news, technical_indicators)

            # Формирование промпта
            prompt = self._create_analysis_prompt(context)

            # Запрос к OpenAI
            response = await self._call_openai(prompt)

            # Парсинг ответа
            analysis = self._parse_response(response, symbol)

            logger.info(f"AI анализ для {symbol} завершен успешно")
            return analysis

        except Exception as e:
            logger.error(f"Ошибка AI анализа: {e}")
            return self._get_default_analysis(symbol)

    def _prepare_context(self, market_data: pd.DataFrame, symbol: str,
                         news: Optional[List[str]],
                         technical_indicators: Optional[Dict]) -> Dict:
        """Подготовка контекста для анализа"""

        # Последние данные рынка
        recent_data = market_data.tail(20)

        context = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "price_data": {
                "current": float(recent_data['close'].iloc[-1]),
                "high_24h": float(recent_data['high'].max()),
                "low_24h": float(recent_data['low'].min()),
                "volume_24h": float(recent_data['volume'].sum()),
                "price_change_percent": float(
                    (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) /
                    recent_data['close'].iloc[0] * 100
                )
            },
            "technical_indicators": technical_indicators or {},
            "recent_news": news[:5] if news else []
        }

        return context

    def _create_analysis_prompt(self, context: Dict) -> str:
        """Создание промпта для анализа"""

        prompt = f"""Ты опытный криптотрейдер и аналитик. Проанализируй текущую ситуацию для {context['symbol']}.

Текущие данные:
- Цена: ${context['price_data']['current']:.2f}
- Изменение за 24ч: {context['price_data']['price_change_percent']:.2f}%
- Объем за 24ч: ${context['price_data']['volume_24h']:,.0f}
- Максимум 24ч: ${context['price_data']['high_24h']:.2f}
- Минимум 24ч: ${context['price_data']['low_24h']:.2f}

Технические индикаторы:
{json.dumps(context['technical_indicators'], indent=2)}

{'Последние новости:' + chr(10).join(context['recent_news']) if context['recent_news'] else 'Новостей нет'}

Предоставь анализ в формате JSON со следующей структурой:
{{
    "action": "BUY/SELL/HOLD",
    "confidence": 0.0-1.0,
    "reasoning": "детальное обоснование",
    "entry_price": рекомендуемая цена входа,
    "stop_loss": уровень стоп-лосса,
    "take_profit": уровень тейк-профита,
    "risk_level": "LOW/MEDIUM/HIGH",
    "key_factors": ["фактор1", "фактор2", ...],
    "market_sentiment": "BULLISH/BEARISH/NEUTRAL",
    "time_horizon": "short/medium/long"
}}
"""

        return prompt

    async def _call_openai(self, prompt: str) -> str:
        """Вызов OpenAI API"""

        response = await openai.ChatCompletion.acreate(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Ты профессиональный криптотрейдер с 10-летним опытом. Даешь точные и обоснованные рекомендации."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=self.temperature,
            response_format={"type": "json_object"}
        )

        return response.choices[0].message.content

    def _parse_response(self, response: str, symbol: str) -> Dict:
        """Парсинг ответа от OpenAI"""

        try:
            analysis = json.loads(response)

            # Валидация и дополнение данных
            analysis['symbol'] = symbol
            analysis['timestamp'] = datetime.utcnow().isoformat()
            analysis['source'] = 'openai'

            # Проверка обязательных полей
            required_fields = ['action', 'confidence', 'reasoning']
            for field in required_fields:
                if field not in analysis:
                    raise ValueError(f"Отсутствует обязательное поле: {field}")

            return analysis

        except Exception as e:
            logger.error(f"Ошибка парсинга ответа OpenAI: {e}")
            return self._get_default_analysis(symbol)

    def _get_default_analysis(self, symbol: str) -> Dict:
        """Дефолтный анализ при ошибке"""

        return {
            "symbol": symbol,
            "action": "HOLD",
            "confidence": 0.0,
            "reasoning": "Недостаточно данных для анализа",
            "risk_level": "HIGH",
            "source": "default",
            "timestamp": datetime.utcnow().isoformat()
        }