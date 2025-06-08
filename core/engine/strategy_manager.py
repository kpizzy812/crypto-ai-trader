# core/engine/strategy_manager.py
"""
Управление торговыми стратегиями
"""
from typing import List, Dict
from loguru import logger

from config.trading_config import TradingConfig
from core.event_bus import EventBus, Event, EventType
from trading.strategies.simple_momentum import SimpleMomentumStrategy
from trading.strategies.ai_driven import AIDrivenStrategy


class StrategyManager:
    """Менеджер торговых стратегий"""

    def __init__(self, trading_config: TradingConfig, event_bus: EventBus):
        self.trading_config = trading_config
        self.event_bus = event_bus
        self.strategies = []

    async def initialize(self):
        """Инициализация стратегий"""
        logger.info("🎯 Инициализация стратегий")

        await self._initialize_momentum_strategy()
        await self._initialize_ai_strategy()

        logger.info(f"✅ Инициализировано стратегий: {len(self.strategies)}")

        # Подписка на события анализа для запуска стратегий
        self.event_bus.subscribe(EventType.AI_ANALYSIS_COMPLETE, self._on_analysis_complete)

    async def _initialize_momentum_strategy(self):
        """Инициализация моментум стратегии"""
        try:
            momentum_config = {
                'indicators': self.trading_config.technical_indicators,
                'position_size_percent': self.trading_config.risk.max_position_size_percent,
                'confidence_threshold': 0.6
            }

            momentum_strategy = SimpleMomentumStrategy(momentum_config)
            momentum_strategy.active = True  # Активна по умолчанию
            self.strategies.append(momentum_strategy)

            logger.info("✅ SimpleMomentum стратегия инициализирована")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Momentum стратегии: {e}")

    async def _initialize_ai_strategy(self):
        """Инициализация AI стратегии"""
        try:
            ai_config = {
                'min_confidence': 0.7,
                'use_news': True,
                'risk_multiplier': 1.0,
                'technical_indicators': self.trading_config.technical_indicators
            }

            ai_strategy = AIDrivenStrategy(ai_config, self.event_bus)
            ai_strategy.active = False  # Включается вручную
            self.strategies.append(ai_strategy)

            logger.info("✅ AI-Driven стратегия инициализирована")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AI стратегии: {e}")

    async def _on_analysis_complete(self, event: Event):
        """Обработка завершенного анализа - запуск стратегий"""
        data = event.data
        symbol = data['symbol']
        analysis = data['analysis']
        technical_data = data.get('technical_data', {})

        # Запуск всех активных стратегий
        for strategy in self.strategies:
            if not strategy.active:
                continue

            try:
                await self._run_strategy(strategy, symbol, analysis, technical_data)
            except Exception as e:
                logger.error(f"❌ Ошибка в стратегии {strategy.name} для {symbol}: {e}")

    async def _run_strategy(self, strategy, symbol: str, analysis: Dict, technical_data: Dict):
        """Запуск отдельной стратегии"""

        try:
            # Создаем DataFrame из технических данных для стратегии
            import pandas as pd

            # В реальности здесь должны быть полные данные, а не одна строка
            # Это упрощенная версия
            mock_data = pd.DataFrame([technical_data])

            # Анализ стратегии
            strategy_analysis = await strategy.analyze(mock_data, symbol)

            # Проверка условий входа
            if await strategy.should_enter(strategy_analysis):
                # Генерация сигнала от стратегии
                await self._generate_strategy_signal(strategy, symbol, strategy_analysis)

            # Проверка условий выхода (если есть открытые позиции)
            await self._check_exit_conditions(strategy, symbol, strategy_analysis)

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения стратегии {strategy.name}: {e}")

    async def _generate_strategy_signal(self, strategy, symbol: str, analysis: Dict):
        """Генерация сигнала от стратегии"""

        signal_data = {
            'symbol': symbol,
            'strategy': strategy.name,
            'action': analysis.get('recommendation', 'HOLD'),
            'confidence': analysis.get('confidence', 0),
            'analysis': analysis,
            'source': 'strategy'
        }

        # Публикация события стратегического сигнала
        await self.event_bus.publish(Event(
            type=EventType.SIGNAL_GENERATED,
            data=signal_data,
            source=f"Strategy_{strategy.name}"
        ))

        logger.info(f"📈 Стратегия {strategy.name}: {symbol} {analysis.get('recommendation', 'HOLD')}")

    async def _check_exit_conditions(self, strategy, symbol: str, analysis: Dict):
        """Проверка условий выхода для стратегии"""

        # Здесь должна быть проверка открытых позиций
        # В упрощенной версии пропускаем
        pass

    async def get_active_strategies(self) -> List[str]:
        """Получение списка активных стратегий"""
        return [strategy.name for strategy in self.strategies if strategy.active]

    async def toggle_strategy(self, strategy_name: str, active: bool) -> bool:
        """Включение/выключение стратегии"""
        for strategy in self.strategies:
            if strategy.name == strategy_name:
                strategy.active = active
                logger.info(f"🎯 Стратегия {strategy_name}: {'включена' if active else 'выключена'}")
                return True

        logger.warning(f"⚠️ Стратегия {strategy_name} не найдена")
        return False

    async def get_strategy_config(self, strategy_name: str) -> Dict:
        """Получение конфигурации стратегии"""
        for strategy in self.strategies:
            if strategy.name == strategy_name:
                return strategy.config
        return {}

    async def update_strategy_config(self, strategy_name: str, new_config: Dict) -> bool:
        """Обновление конфигурации стратегии"""
        for strategy in self.strategies:
            if strategy.name == strategy_name:
                strategy.config.update(new_config)
                logger.info(f"🎯 Конфигурация стратегии {strategy_name} обновлена")
                return True
        return False

    async def stop(self):
        """Остановка всех стратегий"""
        logger.info("🎯 Остановка стратегий")

        for strategy in self.strategies:
            strategy.active = False

        self.strategies.clear()