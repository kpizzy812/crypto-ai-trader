# core/engine/trading_engine.py
"""
Основной торговый движок - только оркестрация компонентов
"""
import asyncio
from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime

from config.settings import Settings
from config.trading_config import TradingConfig
from core.event_bus import EventBus, Event, EventType
from core.portfolio import Portfolio
from risk.risk_manager import RiskManager

from .exchange_manager import ExchangeManager
from .market_analyzer import MarketAnalyzer
from .signal_processor import SignalProcessor
from .position_manager import PositionManager
from .strategy_manager import StrategyManager
from .notification_manager import NotificationManager


class TradingEngine:
    """Главный оркестратор торговой системы"""

    def __init__(self, settings: Settings, trading_config: TradingConfig):
        self.settings = settings
        self.trading_config = trading_config
        self.is_running = False

        # Core компоненты
        self.event_bus = EventBus()
        self.portfolio = Portfolio()
        self.risk_manager = RiskManager(trading_config.risk, self.portfolio)

        # Специализированные менеджеры
        self.exchange_manager = ExchangeManager(settings, self.event_bus)
        self.market_analyzer = MarketAnalyzer(trading_config, self.event_bus)
        self.signal_processor = SignalProcessor(self.event_bus, self.risk_manager)
        self.position_manager = PositionManager(self.portfolio, self.event_bus)
        self.strategy_manager = StrategyManager(trading_config, self.event_bus)
        self.notification_manager = NotificationManager(settings, self.event_bus)

    async def initialize(self):
        """Инициализация всех компонентов"""
        logger.info("🚀 Инициализация торгового движка")

        # Порядок инициализации важен!
        await self.event_bus.start()
        await self.exchange_manager.initialize()
        await self.market_analyzer.initialize()
        await self.strategy_manager.initialize()
        await self.signal_processor.initialize()
        await self.position_manager.initialize()
        await self.notification_manager.initialize()

        self._subscribe_to_events()
        logger.info("🎉 Торговый движок готов к работе")

    def _subscribe_to_events(self):
        """Подписка на ключевые события"""
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal_generated)
        self.event_bus.subscribe(EventType.POSITION_CLOSED, self._on_position_closed)
        self.event_bus.subscribe(EventType.RISK_ALERT, self._on_risk_alert)

    async def start(self):
        """Запуск торгового цикла"""
        if self.is_running:
            logger.warning("Движок уже запущен")
            return

        await self.initialize()
        self.is_running = True

        logger.info("🎯 Запуск торгового цикла")

        try:
            while self.is_running:
                await self._trading_cycle()
                await asyncio.sleep(30)  # Основной цикл каждые 30 секунд

        except KeyboardInterrupt:
            logger.info("⏹️ Получен сигнал остановки")
        finally:
            await self.stop()

    async def _trading_cycle(self):
        """Основной торговый цикл"""
        try:
            # Получение данных и анализ
            for trading_pair in self.trading_config.trading_pairs:
                if trading_pair.enabled:
                    await self.market_analyzer.analyze_symbol(trading_pair.symbol)

        except Exception as e:
            logger.error(f"❌ Ошибка в торговом цикле: {e}")

    async def stop(self):
        """Остановка всех компонентов"""
        logger.info("🛑 Остановка торгового движка")
        self.is_running = False

        # Остановка в обратном порядке
        await self.notification_manager.stop()
        await self.position_manager.stop()
        await self.signal_processor.stop()
        await self.strategy_manager.stop()
        await self.market_analyzer.stop()
        await self.exchange_manager.stop()
        await self.event_bus.stop()

        logger.info("✅ Торговый движок остановлен")

    # Event handlers
    async def _on_signal_generated(self, event: Event):
        """Обработка торгового сигнала"""
        logger.info(f"📊 Сигнал: {event.data}")

    async def _on_position_closed(self, event: Event):
        """Обработка закрытой позиции"""
        data = event.data
        pnl_emoji = "🟢" if data['pnl'] > 0 else "🔴" if data['pnl'] < 0 else "⚪"
        logger.info(f"{pnl_emoji} Позиция закрыта: {data['symbol']} PnL: {data['pnl']}")

    async def _on_risk_alert(self, event: Event):
        """Обработка риск-алерта"""
        logger.warning(f"⚠️ РИСК АЛЕРТ: {event.data}")

    async def get_system_status(self):
        """Получение статуса системы"""
        portfolio_stats = await self.portfolio.get_portfolio_stats()
        risk_metrics = await self.risk_manager.get_risk_metrics()

        return {
            'status': 'running' if self.is_running else 'stopped',
            'exchanges': await self.exchange_manager.get_connected_exchanges(),
            'active_strategies': await self.strategy_manager.get_active_strategies(),
            'portfolio': {
                'total_value': float(portfolio_stats['total_value']),
                'available': float(portfolio_stats['available_balance']),
                'pnl': float(portfolio_stats['total_pnl'])
            },
            'risk': {
                'score': risk_metrics.risk_score,
                'drawdown': float(risk_metrics.current_drawdown)
            },
            'positions_count': len(self.portfolio.positions)
        }