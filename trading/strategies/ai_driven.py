# trading/strategies/ai_driven.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
Торговая стратегия, полностью управляемая ИИ - ДОБАВЛЕН ОТСУТСТВУЮЩИЙ МЕТОД
"""
from typing import Dict, Any, Optional, List
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from loguru import logger
from trading.strategies.base_strategy import BaseStrategy
from ai.openai_analyzer import OpenAIAnalyzer
from data.processors.technical_processor import TechnicalProcessor
from core.event_bus import EventBus, Event, EventType


class AIDrivenStrategy(BaseStrategy):
    """Стратегия, управляемая искусственным интеллектом - ИСПРАВЛЕННАЯ ВЕРСИЯ"""

    def __init__(self, config: Dict[str, Any], event_bus: EventBus):
        super().__init__("AI_Driven", config)
        self.event_bus = event_bus
        self.ai_analyzer = OpenAIAnalyzer()
        self.technical_processor = TechnicalProcessor()

        # Параметры стратегии
        self.min_confidence = config.get('min_confidence', 0.7)
        self.use_news = config.get('use_news', True)
        self.use_sentiment = config.get('use_sentiment', True)
        self.risk_multiplier = config.get('risk_multiplier', 1.0)

        # История анализов для обучения
        self.analysis_history: List[Dict] = []
        self.performance_history: List[Dict] = []

    async def analyze(self, market_data: pd.DataFrame, symbol: str,
                      news: Optional[List[str]] = None) -> Dict[str, Any]:
        """Комплексный AI анализ рынка"""

        logger.info(f"AI анализ для {symbol}")

        # Технический анализ
        processed_data = self.technical_processor.process_ohlcv(
            market_data,
            self.config.get('technical_indicators', {})
        )

        # Подготовка технических индикаторов для AI
        technical_summary = self._prepare_technical_summary(processed_data)

        # AI анализ
        ai_analysis = await self.ai_analyzer.analyze_market(
            market_data,
            symbol,
            news=news if self.use_news else None,
            technical_indicators=technical_summary
        )

        # Валидация и улучшение анализа
        enhanced_analysis = await self._enhance_analysis(ai_analysis, processed_data)

        # Сохранение в историю
        self.analysis_history.append({
            'timestamp': datetime.utcnow(),
            'symbol': symbol,
            'analysis': enhanced_analysis,
            'market_snapshot': self._create_market_snapshot(processed_data)
        })

        # Публикация события
        await self.event_bus.publish(Event(
            type=EventType.AI_ANALYSIS_COMPLETE,
            data=enhanced_analysis,
            source="AIDrivenStrategy"
        ))

        return enhanced_analysis

    async def _enhance_analysis(self, ai_analysis: Dict, technical_data: pd.DataFrame) -> Dict:
        """ДОБАВЛЕННЫЙ ОТСУТСТВУЮЩИЙ МЕТОД - Улучшение и валидация AI анализа"""
        enhanced = ai_analysis.copy()

        try:
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

            # Добавление уровней поддержки/сопротивления
            enhanced['support_resistance'] = self._find_support_resistance(technical_data)

            return enhanced

        except Exception as e:
            logger.error(f"❌ Ошибка улучшения анализа: {e}")
            # Возвращаем оригинальный анализ с минимальными добавлениями
            enhanced['adjusted_confidence'] = enhanced.get('confidence', 0.5)
            enhanced['risk_score'] = 0.5
            enhanced['time_horizon'] = 'short'
            return enhanced

    def _validate_with_technicals(self, ai_analysis: Dict, data: pd.DataFrame) -> Dict:
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
        if 'rsi' in current and not pd.isna(current['rsi']):
            rsi_signal = 'BUY' if current['rsi'] < 30 else 'SELL' if current['rsi'] > 70 else 'NEUTRAL'
            if rsi_signal == ai_action:
                validation['confirmations'].append('RSI подтверждает сигнал')
                validation['score'] += 0.1
            elif rsi_signal != 'NEUTRAL' and rsi_signal != ai_action:
                validation['conflicts'].append('RSI противоречит сигналу')
                validation['score'] -= 0.1

        # Проверка EMA кроссовера
        if 'ema_fast' in current and 'ema_slow' in current:
            if not (pd.isna(current['ema_fast']) or pd.isna(current['ema_slow'])):
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

    def _calculate_risk_score(self, data: pd.DataFrame, analysis: Dict) -> float:
        """Расчет риск-скора позиции"""
        risk_score = 0.5  # Базовый риск

        try:
            # Волатильность
            if len(data) >= 20:
                volatility = data['close'].pct_change().tail(20).std()
                if pd.notna(volatility):
                    if volatility > 0.05:  # Высокая волатильность
                        risk_score += 0.2
                    elif volatility < 0.01:  # Низкая волатильность
                        risk_score -= 0.1

            # Расстояние до уровней
            if 'stop_loss' in analysis and 'entry_price' in analysis:
                try:
                    entry_price = float(analysis['entry_price'])
                    stop_loss = float(analysis['stop_loss'])
                    sl_distance = abs(entry_price - stop_loss) / entry_price
                    if sl_distance > 0.05:  # Далекий стоп
                        risk_score += 0.15
                except (ValueError, TypeError, ZeroDivisionError):
                    pass

            # Уверенность AI
            confidence = analysis.get('adjusted_confidence', 0.5)
            if confidence < 0.6:
                risk_score += 0.2
            elif confidence > 0.8:
                risk_score -= 0.1

        except Exception as e:
            logger.error(f"❌ Ошибка расчета риск-скора: {e}")

        return max(0, min(1, risk_score))

    def _determine_time_horizon(self, data: pd.DataFrame, analysis: Dict) -> str:
        """Определение временного горизонта позиции"""
        try:
            # На основе волатильности и тренда
            if len(data) >= 50:
                short_trend = self._determine_trend(data.tail(20))
                medium_trend = self._determine_trend(data.tail(50))

                if 'strong' in short_trend and 'strong' in medium_trend:
                    return 'medium'  # Сильный тренд - держим дольше
                elif short_trend != medium_trend:
                    return 'short'  # Противоречивые сигналы - краткосрочно

            return 'short'  # По умолчанию краткосрочная

        except Exception as e:
            logger.error(f"❌ Ошибка определения временного горизонта: {e}")
            return 'short'

    def _prepare_technical_summary(self, data: pd.DataFrame) -> Dict:
        """Подготовка технического резюме для AI"""

        if len(data) < 20:
            return {}

        current = data.iloc[-1]

        summary = {
            'trends': {
                'short_term': self._determine_trend(data.tail(20)),
                'medium_term': self._determine_trend(data.tail(50)) if len(data) >= 50 else None,
                'long_term': self._determine_trend(data.tail(100)) if len(data) >= 100 else None
            },
            'momentum': {},
            'volatility': {},
            'volume': {},
            'support_resistance': {}
        }

        # Моментум индикаторы
        if 'rsi' in current and not pd.isna(current['rsi']):
            summary['momentum']['rsi'] = {
                'value': float(current['rsi']),
                'signal': 'overbought' if current['rsi'] > 70 else 'oversold' if current['rsi'] < 30 else 'neutral'
            }

        # Скользящие средние
        if 'ema_fast' in current and 'ema_slow' in current:
            if not (pd.isna(current['ema_fast']) or pd.isna(current['ema_slow'])):
                summary['momentum']['ema_crossover'] = {
                    'fast': float(current['ema_fast']),
                    'slow': float(current['ema_slow']),
                    'signal': 'bullish' if current['ema_fast'] > current['ema_slow'] else 'bearish'
                }

        # Волатильность
        if 'bb_upper' in current and 'bb_lower' in current and 'bb_middle' in current:
            if not any(pd.isna(current[col]) for col in ['bb_upper', 'bb_lower', 'bb_middle']):
                bb_width = (current['bb_upper'] - current['bb_lower']) / current['bb_middle']
                summary['volatility']['bollinger_bands'] = {
                    'width': float(bb_width),
                    'position': float(
                        (current['close'] - current['bb_lower']) / (current['bb_upper'] - current['bb_lower']))
                }

        # Объем
        if 'volume_sma' in current and not pd.isna(current['volume_sma']):
            if current['volume_sma'] > 0:
                summary['volume']['relative'] = float(current['volume'] / current['volume_sma'])
                summary['volume']['trend'] = 'increasing' if data['volume'].tail(5).mean() > data['volume'].tail(
                    20).mean() else 'decreasing'

        # Уровни поддержки/сопротивления
        summary['support_resistance'] = self._find_support_resistance(data)

        return summary

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
        """Поиск уровней поддержки и сопротивления для AI стратегии"""
        if len(data) < 20:
            return {
                'support_levels': [],
                'resistance_levels': [],
                'pivot_points': []
            }

        try:
            current_price = float(data['close'].iloc[-1])

            # Метод 1: Локальные экстремумы
            window = min(14, len(data) // 4)

            # Поиск локальных максимумов
            resistance_points = []
            support_points = []

            for i in range(window, len(data) - window):
                # Локальный максимум
                if data['high'].iloc[i] == data['high'].iloc[i - window:i + window + 1].max():
                    resistance_points.append(float(data['high'].iloc[i]))

                # Локальный минимум
                if data['low'].iloc[i] == data['low'].iloc[i - window:i + window + 1].min():
                    support_points.append(float(data['low'].iloc[i]))

            # Фильтруем и сортируем
            resistance_levels = sorted([r for r in resistance_points if r > current_price])[:5]
            support_levels = sorted([s for s in support_points if s < current_price], reverse=True)[:5]

            # Pivot points (классические)
            pivot_points = {}
            if len(data) >= 3:
                yesterday = data.iloc[-2]  # Предыдущий день
                pivot = (yesterday['high'] + yesterday['low'] + yesterday['close']) / 3

                pivot_points = {
                    'pivot': float(pivot),
                    'r1': float(2 * pivot - yesterday['low']),
                    'r2': float(pivot + (yesterday['high'] - yesterday['low'])),
                    's1': float(2 * pivot - yesterday['high']),
                    's2': float(pivot - (yesterday['high'] - yesterday['low']))
                }

            return {
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'pivot_points': pivot_points
            }

        except Exception as e:
            logger.error(f"❌ Ошибка поиска уровней: {e}")
            return {
                'support_levels': [],
                'resistance_levels': [],
                'pivot_points': {}
            }

    def _create_market_snapshot(self, data: pd.DataFrame) -> Dict:
        """Создание снимка состояния рынка"""

        if len(data) < 1:
            return {}

        try:
            current = data.iloc[-1]

            return {
                'price': float(current['close']),
                'volume': float(current['volume']),
                'rsi': float(current.get('rsi', 0)) if 'rsi' in current and not pd.isna(current['rsi']) else 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Ошибка создания снимка рынка: {e}")
            return {}

    async def should_enter(self, analysis: Dict[str, Any]) -> bool:
        """Проверка условий входа в позицию"""

        try:
            # Основные условия
            if analysis.get('action', 'HOLD') == 'HOLD':
                return False

            # Проверка минимальной уверенности
            confidence = analysis.get('adjusted_confidence', 0)
            if confidence < self.min_confidence:
                logger.info(f"Уверенность {confidence:.2f} ниже минимальной {self.min_confidence}")
                return False

            # Проверка риска
            risk_score = analysis.get('risk_score', 1)
            if risk_score > 0.8:
                logger.warning(f"Слишком высокий риск: {risk_score:.2f}")
                return False

            # Проверка технической валидации
            tech_validation = analysis.get('technical_validation', {})
            if tech_validation.get('score', 0) < 0.3:
                logger.info("Низкая техническая валидация")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки условий входа: {e}")
            return False

    async def should_exit(self, analysis: Dict[str, Any],
                          position: Dict[str, Any]) -> bool:
        """Проверка условий выхода из позиции"""

        try:
            # Проверка смены направления
            position_side = position.get('side', '').upper()
            new_action = analysis.get('action', 'HOLD')

            if position_side == 'BUY' and new_action == 'SELL':
                return True
            elif position_side == 'SELL' and new_action == 'BUY':
                return True

            # Проверка падения уверенности
            if analysis.get('adjusted_confidence', 0) < 0.4:
                return True

            # Проверка времени удержания
            if 'opened_at' in position:
                try:
                    if isinstance(position['opened_at'], str):
                        opened_at = datetime.fromisoformat(position['opened_at'])
                    else:
                        opened_at = position['opened_at']

                    hold_time = datetime.utcnow() - opened_at
                    time_horizon = analysis.get('time_horizon', 'short')

                    if time_horizon == 'short' and hold_time > timedelta(hours=4):
                        return True
                    elif time_horizon == 'medium' and hold_time > timedelta(days=1):
                        return True
                except (ValueError, TypeError) as e:
                    logger.warning(f"Ошибка обработки времени позиции: {e}")

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка проверки условий выхода: {e}")
            return False

    async def update_performance(self, trade_result: Dict):
        """Обновление истории производительности для обучения"""

        try:
            self.performance_history.append({
                'timestamp': datetime.utcnow(),
                'trade': trade_result,
                'analysis_used': self.analysis_history[-1] if self.analysis_history else None
            })

            # Анализ производительности для корректировки параметров
            if len(self.performance_history) >= 10:
                await self._analyze_performance()

        except Exception as e:
            logger.error(f"❌ Ошибка обновления производительности: {e}")

    async def _analyze_performance(self):
        """Анализ производительности и корректировка параметров"""

        try:
            # Расчет метрик за последние сделки
            recent_trades = self.performance_history[-20:]

            wins = sum(1 for t in recent_trades if t['trade'].get('pnl', 0) > 0)
            losses = sum(1 for t in recent_trades if t['trade'].get('pnl', 0) < 0)

            win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

            # Корректировка параметров на основе производительности
            if win_rate < 0.4:
                # Увеличиваем требования к уверенности
                self.min_confidence = min(0.9, self.min_confidence + 0.05)
                logger.info(f"Увеличена минимальная уверенность до {self.min_confidence}")
            elif win_rate > 0.6:
                # Можем немного снизить требования
                self.min_confidence = max(0.6, self.min_confidence - 0.02)
                logger.info(f"Снижена минимальная уверенность до {self.min_confidence}")

        except Exception as e:
            logger.error(f"❌ Ошибка анализа производительности: {e}")