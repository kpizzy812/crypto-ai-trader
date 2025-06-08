# core/engine/signal_processor.py
"""
Улучшенный процессор сигналов с валидацией данных
"""
from typing import Dict, Optional
from decimal import Decimal
from loguru import logger
import json

from core.event_bus import EventBus, Event, EventType
from risk.risk_manager import RiskManager
from models.trading_signals import (
    AIAnalysisResult, TradingSignal, SignalType,
    create_signal_from_analysis, validate_analysis_event_data
)


class EnhancedSignalProcessor:
    """Улучшенный процессор торговых сигналов"""

    def __init__(self, event_bus: EventBus, risk_manager: RiskManager):
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self.processed_signals = {}
        self.signal_history = []

    async def initialize(self):
        """Инициализация процессора"""
        logger.info("⚡ Инициализация улучшенного процессора сигналов")

        # Подписка на события с улучшенной обработкой ошибок
        self.event_bus.subscribe(EventType.AI_ANALYSIS_COMPLETE, self._on_analysis_complete_safe)

    async def _on_analysis_complete_safe(self, event: Event):
        """Безопасная обработка завершенного анализа"""
        try:
            # Валидация входящих данных
            if not hasattr(event, 'data') or not event.data:
                logger.warning("⚠️ Получен event без данных")
                return

            # Проверяем обязательные поля
            required_fields = ['symbol', 'analysis']
            missing_fields = [field for field in required_fields if field not in event.data]

            if missing_fields:
                logger.error(f"❌ Отсутствуют обязательные поля: {missing_fields}")
                return

            # Валидация через Pydantic модель
            validated_data = validate_analysis_event_data(event.data)

            # Обработка валидированных данных
            await self._process_validated_analysis(validated_data)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки анализа: {e}")
            logger.error(f"Event data: {json.dumps(event.data, default=str, indent=2)}")

    async def _process_validated_analysis(self, data):
        """Обработка валидированного анализа"""
        symbol = data.symbol
        analysis = data.analysis

        logger.info(f"📊 Обработка анализа для {symbol}: {analysis.action}")

        try:
            # Проверка условий генерации сигнала
            signal = await self._evaluate_signal_safe(symbol, analysis)

            if signal:
                # Проверка риска
                if await self._validate_risk_safe(signal):
                    # Генерация торгового сигнала
                    await self._generate_trading_signal_safe(signal)
                else:
                    logger.info(f"⚠️ Сигнал {symbol} отклонен риск-менеджером")
            else:
                logger.debug(f"📊 {symbol}: Нет условий для генерации сигнала")

        except Exception as e:
            logger.error(f"❌ Ошибка процессинга анализа {symbol}: {e}")

    async def _evaluate_signal_safe(self, symbol: str, analysis: AIAnalysisResult) -> Optional[TradingSignal]:
        """Безопасная оценка сигнала"""
        try:
            # Проверка базовых условий
            if analysis.action == SignalType.HOLD:
                return None

            confidence = analysis.adjusted_confidence or analysis.confidence
            if confidence < 0.6:
                logger.debug(f"📊 {symbol}: Низкая уверенность {confidence:.2f}")
                return None

            # Проверка технической валидации
            if analysis.technical_validation:
                tech_score = analysis.technical_validation.score
                if tech_score < 0.3:
                    logger.debug(f"📊 {symbol}: Слабая техническая валидация {tech_score:.2f}")
                    return None

            # Расчет размера позиции
            position_size = await self._calculate_position_size_safe(analysis, confidence)

            if position_size <= 0:
                logger.warning(f"⚠️ Нулевой размер позиции для {symbol}")
                return None

            # Создание сигнала
            signal = create_signal_from_analysis(
                analysis=analysis,
                quantity=position_size,
                strategy="ai_driven"
            )

            return signal

        except Exception as e:
            logger.error(f"❌ Ошибка оценки сигнала {symbol}: {e}")
            return None

    async def _calculate_position_size_safe(self, analysis: AIAnalysisResult, confidence: float) -> Decimal:
        """Безопасный расчет размера позиции"""
        try:
            # Получение статистики портфеля
            portfolio_stats = await self.risk_manager.portfolio.get_portfolio_stats()
            available_balance = float(portfolio_stats['available_balance'])

            if available_balance <= 0:
                logger.warning("⚠️ Недостаточно средств для торговли")
                return Decimal("0")

            # Базовый процент от депозита
            base_percent = 2.0  # 2% базовый размер

            # Корректировка на уверенность
            adjusted_percent = base_percent * confidence

            # Корректировка на риск
            risk_score = analysis.risk_score or 0.5
            risk_multiplier = max(0.1, 1.0 - (risk_score * 0.5))  # Снижаем размер при высоком риске

            final_percent = adjusted_percent * risk_multiplier

            # Расчет размера в USD
            position_value = available_balance * (final_percent / 100)

            # Примерная цена (должна приходить из анализа)
            estimated_price = float(analysis.entry_price or Decimal("45000"))  # Fallback

            # Размер в базовой валюте
            position_size = position_value / estimated_price

            return Decimal(str(max(0.001, position_size)))  # Минимальный размер

        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            return Decimal("0")

    async def _validate_risk_safe(self, signal: TradingSignal) -> bool:
        """Безопасная валидация риска"""
        try:
            # Проверка через риск-менеджер
            risk_ok = await self.risk_manager.check_position_risk(
                symbol=signal.symbol,
                side=signal.action.value.lower(),
                entry_price=signal.position_size_usd / signal.quantity,  # Примерная цена
                quantity=signal.quantity
            )

            if not risk_ok:
                return False

            # Проверка риск-скора
            if signal.risk_score > 0.8:
                logger.warning(f"⚠️ Высокий риск-скор для {signal.symbol}: {signal.risk_score}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка валидации риска: {e}")
            return False

    async def _generate_trading_signal_safe(self, signal: TradingSignal):
        """Безопасная генерация торгового сигнала"""
        try:
            # Добавление в историю
            self.signal_history.append({
                'timestamp': signal.generated_at,
                'signal': signal,
                'processed': True
            })

            # Ограничение размера истории
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-500:]

            # Публикация события
            await self.event_bus.publish(Event(
                type=EventType.SIGNAL_GENERATED,
                data={
                    'symbol': signal.symbol,
                    'action': signal.action.value,
                    'quantity': float(signal.quantity),
                    'confidence': signal.confidence,
                    'priority': signal.priority,
                    'strategy': signal.strategy,
                    'risk_score': signal.risk_score,
                    'reasoning': signal.reasoning,
                    'timestamp': signal.generated_at.isoformat(),
                    'metadata': signal.metadata
                },
                source="EnhancedSignalProcessor"
            ))

            logger.info(f"🎯 Сгенерирован сигнал: {signal.symbol} {signal.action.value} "
                        f"(размер: {signal.quantity:.4f}, уверенность: {signal.confidence:.1%})")

        except Exception as e:
            logger.error(f"❌ Ошибка генерации сигнала: {e}")

    async def get_signal_statistics(self) -> Dict:
        """Получение статистики сигналов"""
        try:
            total_signals = len(self.signal_history)

            if total_signals == 0:
                return {
                    'total_signals': 0,
                    'avg_confidence': 0,
                    'most_active_symbol': None,
                    'signal_distribution': {}
                }

            # Расчет средней уверенности
            avg_confidence = sum(s['signal'].confidence for s in self.signal_history) / total_signals

            # Самый активный символ
            symbol_counts = {}
            action_counts = {'BUY': 0, 'SELL': 0, 'HOLD': 0}

            for record in self.signal_history:
                symbol = record['signal'].symbol
                action = record['signal'].action.value

                symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
                action_counts[action] = action_counts.get(action, 0) + 1

            most_active_symbol = max(symbol_counts.items(), key=lambda x: x[1])[0] if symbol_counts else None

            return {
                'total_signals': total_signals,
                'avg_confidence': avg_confidence,
                'most_active_symbol': most_active_symbol,
                'signal_distribution': action_counts,
                'symbols_traded': list(symbol_counts.keys()),
                'recent_signals': len([s for s in self.signal_history[-20:]]),  # Последние 20
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчета статистики сигналов: {e}")
            return {'error': str(e)}

    async def stop(self):
        """Остановка процессора"""
        logger.info("⚡ Остановка улучшенного процессора сигналов")

        # Сохранение статистики
        stats = await self.get_signal_statistics()
        logger.info(f"📊 Финальная статистика сигналов: {stats}")

        self.processed_signals.clear()
        self.signal_history.clear()


# Исправления для использования в TradingEngine
class EventDataFixer:
    """Помощник для исправления данных событий"""

    @staticmethod
    def fix_analysis_data(data: Dict) -> Dict:
        """Исправление данных анализа для Event Bus"""
        fixed_data = data.copy()

        # Убеждаемся что analysis содержит обязательные поля
        if 'analysis' in fixed_data:
            analysis = fixed_data['analysis']

            # Добавляем отсутствующие поля
            if 'action' not in analysis:
                analysis['action'] = 'HOLD'

            if 'confidence' not in analysis:
                analysis['confidence'] = 0.0

            if 'reasoning' not in analysis:
                analysis['reasoning'] = 'Недостаточно данных'

            if 'symbol' not in analysis:
                analysis['symbol'] = fixed_data.get('symbol', 'UNKNOWN')

        return fixed_data