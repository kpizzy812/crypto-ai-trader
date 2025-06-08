# main.py - Модульная версия
"""
Главная точка входа с модульным торговым движком
"""
import asyncio
import uvicorn
from loguru import logger
from config.settings import Settings
from config.trading_config import TradingConfig
from core.engine.trading_engine import TradingEngine  # Используем модульный движок
from utils.logger import setup_logger
from api.main import app

# Глобальная переменная для движка
trading_engine = None


async def run_trading_bot():
    """Запуск торгового бота с модульной архитектурой"""
    global trading_engine

    setup_logger("INFO", "logs/trading_bot.log")

    settings = Settings()
    trading_config = TradingConfig()

    logger.info("🤖 Запуск Crypto AI Trading Bot v2.1 (Modular)")
    logger.info("🧩 Режим: Модульная архитектура")

    # Создание модульного движка
    trading_engine = TradingEngine(settings, trading_config)

    try:
        await trading_engine.start()

    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        raise
    finally:
        if trading_engine:
            await trading_engine.stop()


async def run_web_api():
    """Запуск веб API"""
    global trading_engine

    if trading_engine:
        app.state.trading_engine = trading_engine

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_demo_mode():
    """Демо режим с модульной архитектурой"""
    setup_logger("INFO", "logs/demo.log")

    logger.info("🎯 ДЕМО режим - Модульная архитектура")
    logger.info("🧩 Тестирование всех компонентов по отдельности")

    settings = Settings()
    trading_config = TradingConfig()

    # Принудительно testnet
    settings.bybit_testnet = True
    settings.binance_testnet = True

    engine = TradingEngine(settings, trading_config)

    try:
        logger.info("🚀 Инициализация модульных компонентов...")
        await engine.initialize()

        logger.info("📊 === ТЕСТ КОМПОНЕНТОВ ===")

        # 1. Тест Exchange Manager
        logger.info("🔌 Тестирование Exchange Manager...")
        exchanges = await engine.exchange_manager.get_connected_exchanges()
        logger.info(f"✅ Подключенные биржи: {exchanges}")

        # 2. Тест Market Analyzer
        logger.info("📊 Тестирование Market Analyzer...")
        await engine.market_analyzer.analyze_symbol("BTCUSDT")
        logger.info("✅ Анализ рынка выполнен")

        # 3. Тест Strategy Manager
        logger.info("🎯 Тестирование Strategy Manager...")
        active_strategies = await engine.strategy_manager.get_active_strategies()
        logger.info(f"✅ Активные стратегии: {active_strategies}")

        # 4. Тест Position Manager
        logger.info("📈 Тестирование Position Manager...")
        position_stats = await engine.position_manager.get_position_statistics()
        logger.info(f"✅ Статистика позиций: {position_stats}")

        # 5. Тест системного статуса
        logger.info("📊 Тестирование системного статуса...")
        status = await engine.get_system_status()
        logger.info(f"✅ Статус системы: {status['status']}")

        logger.info("🎉 Все компоненты работают корректно!")

        # Демо торгового цикла
        logger.info("🔄 Демо торгового цикла (30 секунд)...")
        await asyncio.sleep(30)

    except Exception as e:
        logger.error(f"❌ Ошибка в демо: {e}")
    finally:
        await engine.stop()


async def main():
    """Главная функция с выбором режима"""
    import argparse

    parser = argparse.ArgumentParser(description='Crypto AI Trading Bot v2.1 (Modular)')
    parser.add_argument('--mode', choices=['bot', 'api', 'both', 'demo', 'test'],
                        default='demo', help='Режим запуска')
    parser.add_argument('--testnet', action='store_true',
                        help='Принудительно использовать testnet')
    parser.add_argument('--component', choices=['exchanges', 'analyzer', 'strategies', 'positions'],
                        help='Тест отдельного компонента')
    args = parser.parse_args()

    if args.mode == 'demo':
        await run_demo_mode()
    elif args.mode == 'test':
        await run_component_test(args.component)
    elif args.mode == 'bot':
        await run_trading_bot()
    elif args.mode == 'api':
        await run_web_api()
    else:  # both
        await asyncio.gather(
            run_trading_bot(),
            run_web_api()
        )


async def run_component_test(component: str = None):
    """Тестирование отдельных компонентов"""
    setup_logger("DEBUG", "logs/component_test.log")

    settings = Settings()
    trading_config = TradingConfig()

    logger.info(f"🧪 Тестирование компонента: {component or 'all'}")

    if component == 'exchanges' or not component:
        await test_exchange_manager(settings)

    if component == 'analyzer' or not component:
        await test_market_analyzer(trading_config)

    if component == 'strategies' or not component:
        await test_strategy_manager(trading_config)

    if component == 'positions' or not component:
        await test_position_manager()


async def test_exchange_manager(settings: Settings):
    """Тест Exchange Manager"""
    logger.info("🔌 === ТЕСТ EXCHANGE MANAGER ===")

    from core.event_bus import EventBus
    from core.engine.exchange_manager import ExchangeManager

    event_bus = EventBus()
    await event_bus.start()

    exchange_manager = ExchangeManager(settings, event_bus)

    try:
        await exchange_manager.initialize()

        # Тест получения данных
        data = await exchange_manager.get_market_data("BTCUSDT", "5m", 10)
        logger.info(f"✅ Получено {len(data)} свечей для BTCUSDT")

        exchanges = await exchange_manager.get_connected_exchanges()
        logger.info(f"✅ Подключенные биржи: {exchanges}")

    finally:
        await exchange_manager.stop()
        await event_bus.stop()


async def test_market_analyzer(trading_config: TradingConfig):
    """Тест Market Analyzer"""
    logger.info("📊 === ТЕСТ MARKET ANALYZER ===")

    from core.event_bus import EventBus
    from core.engine.market_analyzer import MarketAnalyzer

    event_bus = EventBus()
    await event_bus.start()

    analyzer = MarketAnalyzer(trading_config, event_bus)

    try:
        await analyzer.initialize()
        await analyzer.analyze_symbol("BTCUSDT")

        # Проверка кэша
        cached = analyzer.get_cached_analysis("BTCUSDT")
        if cached:
            logger.info(f"✅ Анализ кэширован: {cached['ai_analysis']['action']}")

    finally:
        await analyzer.stop()
        await event_bus.stop()


async def test_strategy_manager(trading_config: TradingConfig):
    """Тест Strategy Manager"""
    logger.info("🎯 === ТЕСТ STRATEGY MANAGER ===")

    from core.event_bus import EventBus
    from core.engine.strategy_manager import StrategyManager

    event_bus = EventBus()
    await event_bus.start()

    strategy_manager = StrategyManager(trading_config, event_bus)

    try:
        await strategy_manager.initialize()

        strategies = await strategy_manager.get_active_strategies()
        logger.info(f"✅ Активных стратегий: {len(strategies)}")

        # Тест переключения стратегии
        result = await strategy_manager.toggle_strategy("SimpleMomentum", False)
        logger.info(f"✅ Стратегия выключена: {result}")

    finally:
        await strategy_manager.stop()
        await event_bus.stop()


async def test_position_manager():
    """Тест Position Manager"""
    logger.info("📈 === ТЕСТ POSITION MANAGER ===")

    from core.event_bus import EventBus
    from core.portfolio import Portfolio
    from core.engine.position_manager import PositionManager

    event_bus = EventBus()
    await event_bus.start()

    portfolio = Portfolio()
    position_manager = PositionManager(portfolio, event_bus)

    try:
        await position_manager.initialize()

        stats = await position_manager.get_position_statistics()
        logger.info(f"✅ Статистика позиций: {stats}")

    finally:
        await position_manager.stop()
        await event_bus.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        raise