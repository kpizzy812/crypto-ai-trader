# core/engine/signal_processor.py
"""
Обработка торговых сигналов и принятие решений
"""
from typing import Dict, Optional
from decimal import Decimal
from loguru import logger


from core.event_bus import EventBus, Event, EventType
from risk.risk_manager import RiskManager


class SignalProcessor:
    """Обработчик торговых сигналов"""

    def __init__(self, event_bus: EventBus, risk_manager: RiskManager):
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self.pending_signals = {}

    async def initialize(self):
        """Инициализация процессора сигналов"""
        logger.info("⚡ Инициализация процессора сигналов")

        # Подписка на события анализа
        self.event_bus.subscribe(EventType.AI_ANALYSIS_COMPLETE, self._on_analysis_complete)

    async def _on_analysis_complete(self, event: Event):
        """Обработка завершенного анализа"""
        data = event.data
        symbol = data['symbol']
        analysis = data['analysis']

        try:
            # Проверка условий генерации сигнала
            signal = await self._evaluate_signal(symbol, analysis)

            if signal:
                # Проверка риска
                if await self._validate_risk(signal):
                    # Генерация торгового сигнала
                    await self._generate_trading_signal(signal)
                else:
                    logger.info(f"⚠️ Сигнал {symbol} отклонен риск-менеджером")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки сигнала {symbol}: {e}")

    async def _evaluate_signal(self, symbol: str, analysis: Dict) -> Optional[Dict]:
        """Оценка необходимости генерации сигнала"""

        action = analysis.get('action', 'HOLD')
        confidence = analysis.get('adjusted_confidence', 0)

        # Проверка базовых условий
        if action == 'HOLD':
            return None

        if confidence < 0.6:  # Минимальная уверенность
            logger.debug(f"📊 {symbol}: Низкая уверенность {confidence:.2f}")
            return None

        # Проверка технической валидации
        tech_validation = analysis.get('technical_validation', {})
        if tech_validation.get('score', 0) < 0.3:
            logger.debug(f"📊 {symbol}: Слабая техническая валидация")
            return None

        # Формирование сигнала
        signal = {
            'symbol': symbol,
            'action': action.lower(),  # buy/sell
            'confidence': confidence,
            'analysis': analysis,
            'priority': self._calculate_priority(analysis),
            'metadata': {
                'risk_score': analysis.get('risk_score', 0.5),
                'time_horizon': analysis.get('time_horizon', 'short'),
                'reasoning': analysis.get('reasoning', '')
            }
        }

        return signal

    def _calculate_priority(self, analysis: Dict) -> int:
        """Расчет приоритета сигнала (1-10)"""

        confidence = analysis.get('adjusted_confidence', 0)
        risk_score = analysis.get('risk_score', 0.5)

        # Высокая уверенность + низкий риск = высокий приоритет
        priority = int((confidence * 10) - (risk_score * 5))

        return max(1, min(10, priority))

    async def _validate_risk(self, signal: Dict) -> bool:
        """Валидация сигнала через риск-менеджер"""

        try:
            symbol = signal['symbol']
            action = signal['action']

            # Примерные параметры для проверки риска
            # В реальности здесь нужна интеграция с exchange_manager
            # для получения текущей цены
            estimated_price = Decimal("45000")  # Заглушка
            estimated_quantity = Decimal("0.001")  # Заглушка

            # Проверка через риск-менеджер
            risk_ok = await self.risk_manager.check_position_risk(
                symbol=symbol,
                side=action,
                entry_price=estimated_price,
                quantity=estimated_quantity
            )

            if not risk_ok:
                return False

            # Дополнительная проверка риск-скора
            risk_score = signal['metadata']['risk_score']
            if risk_score > 0.8:
                logger.warning(f"⚠️ Высокий риск-скор для {symbol}: {risk_score}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка валидации риска: {e}")
            return False

    async def _generate_trading_signal(self, signal: Dict):
        """Генерация итогового торгового сигнала"""

        symbol = signal['symbol']

        try:
            # Расчет размера позиции
            position_size = await self._calculate_position_size(signal)

            if position_size <= 0:
                logger.warning(f"⚠️ Нулевой размер позиции для {symbol}")
                return

            # Формирование финального сигнала
            trading_signal = {
                'symbol': symbol,
                'action': signal['action'],
                'quantity': float(position_size),
                'confidence': signal['confidence'],
                'priority': signal['priority'],
                'strategy': 'ai_driven',  # Или определить из анализа
                'risk_score': signal['metadata']['risk_score'],
                'reasoning': signal['metadata']['reasoning'],
                'timestamp': str(pd.Timestamp.now())
            }

            # Публикация сигнала
            await self.event_bus.publish(Event(
                type=EventType.SIGNAL_GENERATED,
                data=trading_signal,
                source="SignalProcessor"
            ))

            logger.info(f"🎯 Сгенерирован сигнал: {symbol} {signal['action'].upper()} "
                        f"(размер: {position_size:.4f}, уверенность: {signal['confidence']:.1%})")

        except Exception as e:
            logger.error(f"❌ Ошибка генерации сигнала {symbol}: {e}")

    async def _calculate_position_size(self, signal: Dict) -> float:
        """Расчет размера позиции"""

        try:
            # Получение статистики портфеля
            portfolio_stats = await self.risk_manager.portfolio.get_portfolio_stats()
            available_balance = float(portfolio_stats['available_balance'])

            # Базовый процент от депозита
            base_percent = 2.0  # 2% базовый размер

            # Корректировка на уверенность
            confidence = signal['confidence']
            adjusted_percent = base_percent * confidence

            # Корректировка на риск
            risk_score = signal['metadata']['risk_score']
            risk_multiplier = 1.0 - (risk_score * 0.5)  # Снижаем размер при высоком риске

            final_percent = adjusted_percent * risk_multiplier

            # Расчет размера в USD
            position_value = available_balance * (final_percent / 100)

            # Примерная цена (в реальности получать с биржи)
            estimated_price = 45000.0  # Заглушка

            # Размер в базовой валюте
            position_size = position_value / estimated_price

            return max(0.001, position_size)  # Минимальный размер

        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            return 0.0

    async def stop(self):
        """Остановка процессора сигналов"""
        logger.info("⚡ Остановка процессора сигналов")
        self.pending_signals.clear()