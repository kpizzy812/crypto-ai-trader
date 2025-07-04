# core/engine/market_analyzer.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
Анализ рыночных данных и технических индикаторов - исправлено для реальных данных
"""
import pandas as pd
from typing import Dict, Optional
from loguru import logger

from config.trading_config import TradingConfig
from core.event_bus import EventBus, Event, EventType
from data.processors.technical_processor import TechnicalProcessor
from ai.openai_analyzer import OpenAIAnalyzer
from ai.mock_analyzer import MockAIAnalyzer


class MarketAnalyzer:
    """Анализатор рыночных данных - исправленная версия"""

    def __init__(self, trading_config: TradingConfig, event_bus: EventBus):
        self.trading_config = trading_config
        self.event_bus = event_bus
        self.technical_processor = TechnicalProcessor()

        # AI компоненты
        self.ai_analyzer = None
        self.mock_analyzer = MockAIAnalyzer()

        # Кэш данных
        self.market_data_cache = {}
        self.analysis_cache = {}

        # Ссылка на exchange_manager (будет установлена после инициализации)
        self.exchange_manager = None

    def set_exchange_manager(self, exchange_manager):
        """Установка ссылки на exchange_manager"""
        self.exchange_manager = exchange_manager
        logger.info("✅ Exchange Manager подключен к Market Analyzer")

    async def initialize(self):
        """Инициализация анализатора"""
        logger.info("📊 Инициализация анализатора рынка")

        # Попытка инициализации OpenAI
        try:
            self.ai_analyzer = OpenAIAnalyzer()
            logger.info("✅ OpenAI анализатор готов")
        except Exception as e:
            logger.warning(f"⚠️ OpenAI недоступен, используется Mock: {e}")

    async def analyze_symbol(self, symbol: str):
        """Полный анализ символа"""
        try:
            # 1. Получение рыночных данных
            market_data = await self._get_market_data(symbol)
            if market_data.empty:
                logger.warning(f"⚠️ Нет данных для {symbol}")
                return

            # 2. Технический анализ
            processed_data = self._perform_technical_analysis(market_data)

            # 3. AI анализ
            ai_analysis = await self._perform_ai_analysis(processed_data, symbol)

            # 4. Сохранение в кэш
            self.analysis_cache[symbol] = {
                'market_data': processed_data,
                'ai_analysis': ai_analysis,
                'timestamp': pd.Timestamp.now()
            }

            # 5. Публикация события с результатами анализа
            await self.event_bus.publish(Event(
                type=EventType.AI_ANALYSIS_COMPLETE,
                data={
                    'symbol': symbol,
                    'analysis': ai_analysis,
                    'technical_data': processed_data.tail(1).to_dict('records')[0] if not processed_data.empty else {}
                },
                source="MarketAnalyzer"
            ))

            logger.debug(f"📊 Анализ {symbol} завершен: {ai_analysis.get('action', 'HOLD')}")

        except Exception as e:
            logger.error(f"❌ Ошибка анализа {symbol}: {e}")

    async def _get_market_data(self, symbol: str) -> pd.DataFrame:
        """Получение рыночных данных - ИСПРАВЛЕНО"""
        try:
            # Сначала пытаемся получить реальные данные
            if self.exchange_manager:
                logger.info(f"📡 Получение реальных данных для {symbol}")
                data = await self.exchange_manager.get_market_data(
                    symbol,
                    self.trading_config.primary_timeframe,
                    100
                )

                if not data.empty:
                    logger.info(f"✅ Получено {len(data)} реальных свечей для {symbol}")
                    return data
                else:
                    logger.warning(f"⚠️ Реальные данные пусты для {symbol}")
            else:
                logger.warning("⚠️ Exchange Manager не подключен")

            # Если реальные данные недоступны, используем заглушку
            logger.info(f"📊 Используются тестовые данные для {symbol}")
            from utils.helpers import create_sample_data
            return create_sample_data(symbol, periods=100)

        except Exception as e:
            logger.error(f"❌ Ошибка получения данных {symbol}: {e}")
            # В крайнем случае возвращаем тестовые данные
            from utils.helpers import create_sample_data
            return create_sample_data(symbol, periods=100)

    def _perform_technical_analysis(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Технический анализ"""
        try:
            return self.technical_processor.process_ohlcv(
                market_data,
                self.trading_config.technical_indicators
            )
        except Exception as e:
            logger.error(f"❌ Ошибка технического анализа: {e}")
            return market_data

    async def _perform_ai_analysis(self, processed_data: pd.DataFrame, symbol: str) -> Dict:
        """AI анализ"""
        try:
            if self.ai_analyzer:
                # Реальный OpenAI анализ
                logger.info(f"🤖 Запуск реального AI анализа для {symbol}")
                analysis = await self.ai_analyzer.analyze_market(processed_data, symbol)
            else:
                # Mock анализ
                logger.info(f"🤖 Запуск Mock AI анализа для {symbol}")
                analysis = await self.mock_analyzer.analyze_market(processed_data, symbol)

            # Улучшение анализа техническими данными
            enhanced_analysis = await self._enhance_analysis(analysis, processed_data)

            return enhanced_analysis

        except Exception as e:
            logger.error(f"❌ Ошибка AI анализа {symbol}: {e}")
            return {'action': 'HOLD', 'confidence': 0.0, 'reasoning': 'Ошибка анализа'}

    async def _enhance_analysis(self, ai_analysis: Dict,
                                technical_data: pd.DataFrame) -> Dict:
        """Улучшение AI анализа техническими данными"""
        enhanced = ai_analysis.copy()

        # Техническая валидация
        enhanced['technical_validation'] = self._validate_with_technicals(
            ai_analysis, technical_data
        )

        # Корректировка уверенности
        validation_score = enhanced['technical_validation']['score']
        original_confidence = enhanced.get('confidence', 0.5)

        enhanced['adjusted_confidence'] = (
                original_confidence * 0.7 + validation_score * 0.3
        )

        # Риск-скор
        enhanced['risk_score'] = self._calculate_risk_score(technical_data, enhanced)

        # Временной горизонт
        enhanced['time_horizon'] = self._determine_time_horizon(technical_data)

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

        # RSI валидация
        if 'rsi' in current and not pd.isna(current['rsi']):
            rsi_signal = 'BUY' if current['rsi'] < 30 else 'SELL' if current['rsi'] > 70 else 'NEUTRAL'
            if rsi_signal == ai_action:
                validation['confirmations'].append('RSI подтверждает')
                validation['score'] += 0.1
            elif rsi_signal != 'NEUTRAL' and rsi_signal != ai_action:
                validation['conflicts'].append('RSI противоречит')
                validation['score'] -= 0.1

        # EMA кроссовер
        if all(x in current for x in ['ema_fast', 'ema_slow']):
            if not any(pd.isna(current[x]) for x in ['ema_fast', 'ema_slow']):
                ema_signal = 'BUY' if current['ema_fast'] > current['ema_slow'] else 'SELL'
                if ema_signal == ai_action:
                    validation['confirmations'].append('EMA подтверждает')
                    validation['score'] += 0.15
                else:
                    validation['conflicts'].append('EMA противоречит')
                    validation['score'] -= 0.15

        validation['score'] = max(0, min(1, validation['score']))
        return validation

    def _calculate_risk_score(self, data: pd.DataFrame, analysis: Dict) -> float:
        """Расчет риск-скора"""
        risk_score = 0.5

        # Волатильность
        if len(data) >= 20:
            volatility = data['close'].pct_change().tail(20).std()
            if volatility > 0.05:
                risk_score += 0.2
            elif volatility < 0.01:
                risk_score -= 0.1

        # Уверенность AI
        confidence = analysis.get('adjusted_confidence', 0.5)
        if confidence < 0.6:
            risk_score += 0.2
        elif confidence > 0.8:
            risk_score -= 0.1

        return max(0, min(1, risk_score))

    def _determine_time_horizon(self, data: pd.DataFrame) -> str:
        """Определение временного горизонта"""
        if len(data) < 50:
            return 'short'

        # Простое определение по волатильности
        volatility = data['close'].pct_change().tail(20).std()

        if volatility > 0.05:
            return 'short'  # Высокая волатильность - краткосрочно
        elif volatility < 0.02:
            return 'medium'  # Низкая волатильность - можем держать дольше
        else:
            return 'short'

    def _determine_trend(self, data: pd.DataFrame) -> str:
        """Определение тренда на основе цен и скользящих средних"""
        if len(data) < 2:
            return 'neutral'

        # Простое определение по направлению цены
        start_price = data['close'].iloc[0]
        end_price = data['close'].iloc[-1]
        price_change_percent = (end_price - start_price) / start_price * 100

        # Определение по скользящим средним если есть
        ema_trend = None
        if 'ema_fast' in data.columns and 'ema_slow' in data.columns:
            current_fast = data['ema_fast'].iloc[-1]
            current_slow = data['ema_slow'].iloc[-1]

            if not (pd.isna(current_fast) or pd.isna(current_slow)):
                ema_diff = (current_fast - current_slow) / current_slow * 100

                if ema_diff > 2:
                    ema_trend = 'strong_uptrend'
                elif ema_diff > 0.5:
                    ema_trend = 'uptrend'
                elif ema_diff < -2:
                    ema_trend = 'strong_downtrend'
                elif ema_diff < -0.5:
                    ema_trend = 'downtrend'
                else:
                    ema_trend = 'sideways'

        # Определение по изменению цены
        if price_change_percent > 3:
            price_trend = 'strong_uptrend'
        elif price_change_percent > 1:
            price_trend = 'uptrend'
        elif price_change_percent < -3:
            price_trend = 'strong_downtrend'
        elif price_change_percent < -1:
            price_trend = 'downtrend'
        else:
            price_trend = 'sideways'

        # Комбинированное решение
        if ema_trend:
            # Если есть EMA данные, используем их с весом
            if ema_trend == price_trend:
                return ema_trend
            elif 'strong' in ema_trend and 'strong' in price_trend:
                return ema_trend  # Приоритет EMA для сильных трендов
            else:
                return 'sideways'  # При конфликте - боковой тренд
        else:
            return price_trend

    def _find_support_resistance(self, data: pd.DataFrame) -> Dict:
        """Поиск уровней поддержки и сопротивления"""
        if len(data) < 20:
            return {
                'nearest_resistance': None,
                'nearest_support': None,
                'resistance_levels': [],
                'support_levels': []
            }

        # Локальные максимумы и минимумы
        window = min(10, len(data) // 4)  # Адаптивное окно

        # Локальные максимумы (потенциальные сопротивления)
        highs = data['high'].rolling(window=window, center=True).max()
        local_maxima = data['high'][data['high'] == highs]

        # Локальные минимумы (потенциальные поддержки)
        lows = data['low'].rolling(window=window, center=True).min()
        local_minima = data['low'][data['low'] == lows]

        current_price = float(data['close'].iloc[-1])

        # Фильтруем уровни
        resistance_levels = []
        support_levels = []

        # Сопротивления (выше текущей цены)
        for price in local_maxima.dropna().values:
            if price > current_price:
                resistance_levels.append(float(price))

        # Поддержки (ниже текущей цены)
        for price in local_minima.dropna().values:
            if price < current_price:
                support_levels.append(float(price))

        # Сортируем и берем ближайшие
        resistance_levels = sorted(set(resistance_levels))[:5]  # Топ 5 ближайших
        support_levels = sorted(set(support_levels), reverse=True)[:5]  # Топ 5 ближайших

        return {
            'nearest_resistance': resistance_levels[0] if resistance_levels else None,
            'nearest_support': support_levels[0] if support_levels else None,
            'resistance_levels': resistance_levels,
            'support_levels': support_levels
        }

    def get_cached_analysis(self, symbol: str) -> Optional[Dict]:
        """Получение кэшированного анализа"""
        return self.analysis_cache.get(symbol)

    async def stop(self):
        """Остановка анализатора"""
        logger.info("📊 Остановка анализатора рынка")
        self.market_data_cache.clear()
        self.analysis_cache.clear()