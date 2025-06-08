# trading/strategies/ai_driven.py
"""
Торговая стратегия, полностью управляемая ИИ
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
    """Стратегия, управляемая искусственным интеллектом"""

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
        if 'rsi' in current:
            summary['momentum']['rsi'] = {
                'value': float(current['rsi']),
                'signal': 'overbought' if current['rsi'] > 70 else 'oversold' if current['rsi'] < 30 else 'neutral'
            }

        # Скользящие средние
        if 'ema_fast' in current and 'ema_slow' in current:
            summary['momentum']['ema_crossover'] = {
                'fast': float(current['ema_fast']),
                'slow': float(current['ema_slow']),
                'signal': 'bullish' if current['ema_fast'] > current['ema_slow'] else 'bearish'
            }

        # Волатильность
        if 'bb_upper' in current and 'bb_lower' in current:
            bb_width = (current['bb_upper'] - current['bb_lower']) / current['bb_middle']
            summary['volatility']['bollinger_bands'] = {
                'width': float(bb_width),
                'position': (current['close'] - current['bb_lower']) / (current['bb_upper'] - current['bb_lower'])
            }

        # Объем
        if 'volume_sma' in current:
            summary['volume']['relative'] = float(current['volume'] / current['volume_sma'])
            summary['volume']['trend'] = 'increasing' if data['volume'].tail(5).mean() > data['volume'].tail(
                20).mean() else 'decreasing'

        # Уровни поддержки/сопротивления
        summary['support_resistance'] = self._find_support_resistance(data)

        return summary

    def _determine_trend(self, data: pd.DataFrame) -> str:
        """Определение тренда"""
        if len(data) < 2:
            return 'short'  # По умолчанию краткосрочная

    def _determine_time_horizon(self, data: pd.DataFrame) -> str:
        """Определение временного горизонта позиции"""
        if len(data) < 20:
            return 'short'

        # Анализ волатильности
        returns = data['close'].pct_change().dropna()
        volatility = returns.tail(20).std()

        # Анализ трендов на разных периодах
        short_trend = self._determine_trend(data.tail(20))
        medium_trend = self._determine_trend(data.tail(50)) if len(data) >= 50 else None

        # Анализ объема
        volume_trend = 'stable'
        if 'volume_sma' in data.columns:
            current_vol = data['volume'].iloc[-1]
            avg_vol = data['volume_sma'].iloc[-1]

            if current_vol > avg_vol * 1.5:
                volume_trend = 'high'
            elif current_vol < avg_vol * 0.7:
                volume_trend = 'low'

        # Логика определения горизонта
        if volatility > 0.03:  # Высокая волатильность > 3%
            return 'short'  # При высокой волатильности - краткосрочно

        if short_trend == medium_trend and 'strong' in short_trend:
            return 'medium'  # Сильный устойчивый тренд - средний срок

        if short_trend != medium_trend:
            return 'short'  # Противоречивые сигналы - краткосрочно

        if volume_trend == 'high' and 'strong' in short_trend:
            return 'medium'  # Высокий объем + сильный тренд

        return 'short'  # По умолчанию краткосрочно

    def _find_support_resistance(self, data: pd.DataFrame) -> Dict:
        """Поиск уровней поддержки и сопротивления для AI стратегии"""
        if len(data) < 20:
            return {
                'support_levels': [],
                'resistance_levels': [],
                'pivot_points': []
            }

        current_price = float(data['close'].iloc[-1])

        # Метод 1: Локальные экстремумы
        window = 14

        # Поиск локальных максимумов
        highs = data['high'].rolling(window=window, center=True).max()
        resistance_points = []

        for i in range(window, len(data) - window):
            if data['high'].iloc[i] == highs.iloc[i]:
                resistance_points.append(float(data['high'].iloc[i]))

        # Поиск локальных минимумов
        lows = data['low'].rolling(window=window, center=True).min()
        support_points = []

        for i in range(window, len(data) - window):
            if data['low'].iloc[i] == lows.iloc[i]:
                support_points.append(float(data['low'].iloc[i]))

        # Метод 2: Психологические уровни (круглые числа)
        psychological_levels = []
        if current_price > 1000:
            # Для больших цен - тысячи
            base = int(current_price // 1000) * 1000
            for i in range(-2, 3):
                psychological_levels.append(base + i * 1000)
        elif current_price > 100:
            # Для средних цен - сотни
            base = int(current_price // 100) * 100
            for i in range(-3, 4):
                psychological_levels.append(base + i * 100)
        else:
            # Для малых цен - десятки
            base = int(current_price // 10) * 10
            for i in range(-5, 6):
                psychological_levels.append(base + i * 10)

        # Объединяем и фильтруем
        all_resistance = resistance_points + [p for p in psychological_levels if p > current_price]
        all_support = support_points + [p for p in psychological_levels if p < current_price]

        # Убираем дубликаты и сортируем
        resistance_levels = sorted(list(set(all_resistance)))[:10]
        support_levels = sorted(list(set(all_support)), reverse=True)[:10]

        # Pivot points (классические)
        if len(data) >= 3:
            yesterday = data.iloc[-2]  # Предыдущий день
            pivot = (yesterday['high'] + yesterday['low'] + yesterday['close']) / 3

            r1 = 2 * pivot - yesterday['low']
            r2 = pivot + (yesterday['high'] - yesterday['low'])
            s1 = 2 * pivot - yesterday['high']
            s2 = pivot - (yesterday['high'] - yesterday['low'])

            pivot_points = {
                'pivot': float(pivot),
                'r1': float(r1),
                'r2': float(r2),
                's1': float(s1),
                's2': float(s2)
            }
        else:
            pivot_points = {}

        return {
            'support_levels': support_levels,
            'resistance_levels': resistance_levels,
            'pivot_points': pivot_points,
            'psychological_levels': [p for p in psychological_levels if abs(p - current_price) / current_price < 0.1]
        }

    def _create_market_snapshot(self, data: pd.DataFrame) -> Dict:
        """Создание снимка состояния рынка"""

        if len(data) < 1:
            return {}

        current = data.iloc[-1]

        return {
            'price': float(current['close']),
            'volume': float(current['volume']),
            'rsi': float(current.get('rsi', 0)),
            'timestamp': datetime.utcnow().isoformat()
        }

    async def should_enter(self, analysis: Dict[str, Any]) -> bool:
        """Проверка условий входа в позицию"""

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

    async def should_exit(self, analysis: Dict[str, Any],
                          position: Dict[str, Any]) -> bool:
        """Проверка условий выхода из позиции"""

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
            hold_time = datetime.utcnow() - position['opened_at']
            time_horizon = analysis.get('time_horizon', 'short')

            if time_horizon == 'short' and hold_time > timedelta(hours=4):
                return True
            elif time_horizon == 'medium' and hold_time > timedelta(days=1):
                return True

        return False

    async def update_performance(self, trade_result: Dict):
        """Обновление истории производительности для обучения"""

        self.performance_history.append({
            'timestamp': datetime.utcnow(),
            'trade': trade_result,
            'analysis_used': self.analysis_history[-1] if self.analysis_history else None
        })

        # Анализ производительности для корректировки параметров
        if len(self.performance_history) >= 10:
            await self._analyze_performance()

    async def _analyze_performance(self):
        """Анализ производительности и корректировка параметров"""

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