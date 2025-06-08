# main.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""
Главная точка входа с тестированием реальных данных
"""
import asyncio
import uvicorn
from loguru import logger
from config.settings import Settings
from config.trading_config import TradingConfig
from utils.logger import setup_logger
import sys
import traceback
import pandas as pd


async def run_real_data_test():
    """Тестирование с реальными данными с бирж"""
    setup_logger("INFO", "logs/real_test.log")

    logger.info("🌐 === ТЕСТИРОВАНИЕ С РЕАЛЬНЫМИ ДАННЫМИ ===")

    settings = Settings()
    trading_config = TradingConfig()

    # Принудительно testnet для безопасности
    settings.bybit_testnet = True
    settings.binance_testnet = True

    try:
        from core.engine.trading_engine import TradingEngine

        logger.info("🔧 Инициализация торгового движка...")
        engine = TradingEngine(settings, trading_config)

        # Инициализация (но не запуск торгового цикла)
        await engine.initialize()

        logger.info(f"🔌 Подключенные биржи: {await engine.exchange_manager.get_connected_exchanges()}")

        # Тестируем несколько пар
        test_symbols = ["BTCUSDT", "ETHUSDT"]
        results = {}

        for symbol in test_symbols:
            logger.info(f"📊 Тестирование {symbol}...")
            result = await engine.test_real_analysis(symbol)

            if result:
                results[symbol] = result
                logger.info(f"✅ {symbol} анализ завершен:")
                logger.info(f"   📈 Цена: ${result['current_price']:,.2f}")
                logger.info(f"   📊 Изменение: {result['price_change_24h']:+.2f}%")
                logger.info(f"   🤖 Рекомендация: {result['analysis']['action']}")
                logger.info(f"   💪 Уверенность: {result['analysis']['confidence']:.1%}")
            else:
                logger.warning(f"⚠️ Не удалось проанализировать {symbol}")

        # Дополнительное тестирование торгового цикла
        logger.info("🔄 Тестирование торгового цикла...")

        # Запуск одного цикла анализа
        for trading_pair in trading_config.trading_pairs[:3]:  # Только первые 3
            if trading_pair.enabled:
                await engine.market_analyzer.analyze_symbol(trading_pair.symbol)

        logger.info("🎉 Тестирование с реальными данными завершено!")

        # Корректная остановка
        await engine.stop()

        return results

    except Exception as e:
        logger.error(f"❌ Ошибка в тестировании: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


async def run_demo_mode():
    """Демо режим с улучшенной обработкой ошибок"""
    setup_logger("INFO", "logs/demo.log")

    logger.info("🎯 ДЕМО режим - Модульная архитектура")
    logger.info("🧩 Тестирование компонентов по отдельности")

    settings = Settings()
    trading_config = TradingConfig()

    # Принудительно testnet
    settings.bybit_testnet = True
    settings.binance_testnet = True

    try:
        logger.info("📊 === НАЧАЛО ДЕМО ТЕСТИРОВАНИЯ ===")

        # 1. Тест базовых импортов
        logger.info("🔍 Тестирование базовых импортов...")
        await test_imports()

        # 2. Тест создания тестовых данных
        logger.info("📈 Тестирование генерации данных...")
        await test_data_generation()

        # 3. Тест технических индикаторов
        logger.info("⚙️ Тестирование технических индикаторов...")
        await test_technical_indicators()

        # 4. Тест AI анализатора (mock)
        logger.info("🤖 Тестирование AI анализатора...")
        await test_ai_analyzer()

        # 5. Тест стратегий
        logger.info("🎯 Тестирование стратегий...")
        await test_strategies()

        logger.info("🎉 Все базовые компоненты работают корректно!")
        logger.info("ℹ️ Для полного тестирования добавьте API ключи в .env")

    except Exception as e:
        logger.error(f"❌ Ошибка в демо: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")


async def test_imports():
    """Тест базовых импортов"""
    try:
        from config import Settings, TradingConfig
        from utils.helpers import create_sample_data
        from ai.mock_analyzer import MockAIAnalyzer
        from data.processors.technical_processor import TechnicalProcessor
        from trading.strategies.simple_momentum import SimpleMomentumStrategy
        logger.info("✅ Все базовые импорты успешны")
    except Exception as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        raise


async def test_data_generation():
    """Тест генерации тестовых данных"""
    try:
        from utils.helpers import create_sample_data

        # Создаем тестовые данные
        data = create_sample_data("BTCUSDT", periods=50)

        if not data.empty and len(data) > 0:
            logger.info(f"✅ Сгенерировано {len(data)} свечей тестовых данных")
            logger.info(f"Ценовой диапазон: ${data['low'].min():.2f} - ${data['high'].max():.2f}")
        else:
            raise ValueError("Пустые данные")

    except Exception as e:
        logger.error(f"❌ Ошибка генерации данных: {e}")
        raise


async def test_technical_indicators():
    """Тест технических индикаторов"""
    try:
        from data.processors.technical_processor import TechnicalProcessor
        from utils.helpers import create_sample_data

        processor = TechnicalProcessor()
        data = create_sample_data("BTCUSDT", periods=50)

        # Тестируем основные индикаторы
        config = {
            'rsi': {'period': 14},
            'ema_fast': {'period': 9},
            'ema_slow': {'period': 21},
            'volume_sma': {'period': 20}
        }

        processed = processor.process_ohlcv(data, config)

        if 'rsi' in processed.columns:
            logger.info(f"✅ RSI рассчитан. Последнее значение: {processed['rsi'].iloc[-1]:.2f}")

        if 'ema_fast' in processed.columns and 'ema_slow' in processed.columns:
            logger.info(
                f"✅ EMA рассчитаны. Fast: {processed['ema_fast'].iloc[-1]:.2f}, Slow: {processed['ema_slow'].iloc[-1]:.2f}")

    except Exception as e:
        logger.error(f"❌ Ошибка технических индикаторов: {e}")
        raise


async def test_ai_analyzer():
    """Тест AI анализатора"""
    try:
        from ai.mock_analyzer import MockAIAnalyzer
        from utils.helpers import create_sample_data

        analyzer = MockAIAnalyzer()
        data = create_sample_data("BTCUSDT", periods=50)

        analysis = await analyzer.analyze_market(data, "BTCUSDT")

        logger.info(f"✅ AI анализ завершен:")
        logger.info(f"   Действие: {analysis.get('action', 'N/A')}")
        logger.info(f"   Уверенность: {analysis.get('confidence', 0):.1%}")
        logger.info(f"   Обоснование: {analysis.get('reasoning', 'N/A')}")

    except Exception as e:
        logger.error(f"❌ Ошибка AI анализатора: {e}")
        raise


async def test_strategies():
    """Тест торговых стратегий"""
    try:
        from trading.strategies.simple_momentum import SimpleMomentumStrategy
        from utils.helpers import create_sample_data

        config = {
            'indicators': {
                'rsi': {'period': 14},
                'ema_fast': {'period': 9},
                'ema_slow': {'period': 21},
                'volume_sma': {'period': 20}
            }
        }

        strategy = SimpleMomentumStrategy(config)
        data = create_sample_data("BTCUSDT", periods=50)

        analysis = await strategy.analyze(data, "BTCUSDT")

        logger.info(f"✅ Стратегия SimpleMomentum протестирована:")
        logger.info(f"   Рекомендация: {analysis.get('recommendation', 'N/A')}")
        logger.info(f"   Моментум скор: {analysis.get('momentum_score', 0):.2f}")
        logger.info(f"   Уверенность: {analysis.get('confidence', 0):.1%}")

    except Exception as e:
        logger.error(f"❌ Ошибка тестирования стратегий: {e}")
        raise


async def run_component_test(component: str = None):
    """Тестирование отдельных компонентов с улучшенной обработкой"""
    setup_logger("DEBUG", "logs/component_test.log")

    settings = Settings()
    trading_config = TradingConfig()

    logger.info(f"🧪 Тестирование компонента: {component or 'all'}")

    try:
        if component == 'exchanges' or not component:
            await test_exchange_manager(settings)

        if component == 'analyzer' or not component:
            await test_market_analyzer(trading_config)

        if component == 'strategies' or not component:
            await test_strategy_manager(trading_config)

        logger.info("✅ Все тесты компонентов завершены")

    except Exception as e:
        logger.error(f"❌ Ошибка тестирования компонентов: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")


async def test_exchange_manager(settings: Settings):
    """Тест Exchange Manager с улучшенной обработкой"""
    logger.info("🔌 === ТЕСТ EXCHANGE MANAGER ===")

    try:
        from core.event_bus import EventBus
        from core.engine.exchange_manager import ExchangeManager

        event_bus = EventBus()
        await event_bus.start()

        exchange_manager = ExchangeManager(settings, event_bus)

        try:
            # Попытка инициализации (может упасть из-за API ключей)
            await exchange_manager.initialize()

            exchanges = await exchange_manager.get_connected_exchanges()
            logger.info(f"✅ Подключенные биржи: {exchanges}")

            if exchanges:
                # Тестируем получение данных только если есть подключения
                data = await exchange_manager.get_market_data("BTCUSDT", "5m", 10)
                logger.info(f"✅ Получено {len(data)} свечей для BTCUSDT")
            else:
                logger.warning("⚠️ Нет подключенных бирж (проверьте API ключи в .env)")

        except Exception as inner_e:
            logger.warning(f"⚠️ Ошибка подключения к биржам: {inner_e}")
            logger.info("ℹ️ Это нормально если API ключи не настроены")

        finally:
            await exchange_manager.stop()
            await event_bus.stop()

    except ImportError as e:
        logger.error(f"❌ Ошибка импорта модулей exchange_manager: {e}")
        logger.info("ℹ️ Убедитесь что все файлы созданы из артефактов")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка в test_exchange_manager: {e}")


async def test_market_analyzer(trading_config: TradingConfig):
    """Тест Market Analyzer"""
    logger.info("📊 === ТЕСТ MARKET ANALYZER ===")

    try:
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

    except ImportError as e:
        logger.error(f"❌ Ошибка импорта market_analyzer: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка в test_market_analyzer: {e}")


async def test_strategy_manager(trading_config: TradingConfig):
    """Тест Strategy Manager"""
    logger.info("🎯 === ТЕСТ STRATEGY MANAGER ===")

    try:
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
            if strategies:
                result = await strategy_manager.toggle_strategy(strategies[0], False)
                logger.info(f"✅ Стратегия переключена: {result}")

        finally:
            await strategy_manager.stop()
            await event_bus.stop()

    except ImportError as e:
        logger.error(f"❌ Ошибка импорта strategy_manager: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка в test_strategy_manager: {e}")


async def run_bot_mode():
    """Запуск полноценного торгового бота"""
    setup_logger("INFO", "logs/bot.log")

    logger.info("🤖 === ЗАПУСК ТОРГОВОГО БОТА ===")

    settings = Settings()
    trading_config = TradingConfig()

    try:
        from core.engine.trading_engine import TradingEngine

        engine = TradingEngine(settings, trading_config)

        # Запуск торгового цикла
        await engine.start()

    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")


async def run_api_mode():
    """Запуск API сервера"""
    setup_logger("INFO", "logs/api.log")

    logger.info("🌐 === ЗАПУСК API СЕРВЕРА ===")

    try:
        from api.main import app

        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )

        server = uvicorn.Server(config)
        await server.serve()

    except Exception as e:
        logger.error(f"❌ Ошибка запуска API: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")


async def main():
    """Главная функция с улучшенной обработкой ошибок"""
    import argparse

    parser = argparse.ArgumentParser(description='Crypto AI Trading Bot v2.2 (Real Data)')
    parser.add_argument('--mode', choices=['bot', 'api', 'both', 'demo', 'test', 'real-test'],
                        default='demo', help='Режим запуска')
    parser.add_argument('--component', choices=['exchanges', 'analyzer', 'strategies'],
                        help='Тест отдельного компонента')
    args = parser.parse_args()

    try:
        if args.mode == 'demo':
            await run_demo_mode()
        elif args.mode == 'test':
            await run_component_test(args.component)
        elif args.mode == 'real-test':
            await run_real_data_test()
        elif args.mode == 'bot':
            await run_bot_mode()
        elif args.mode == 'api':
            await run_api_mode()
        elif args.mode == 'both':
            # Запуск в параллельных задачах
            bot_task = asyncio.create_task(run_bot_mode())
            api_task = asyncio.create_task(run_api_mode())

            await asyncio.gather(bot_task, api_task)
        else:
            logger.info(f"Режим {args.mode} будет реализован после исправления ошибок")
            logger.info("Сначала запустите: python main.py --mode demo")

    except KeyboardInterrupt:
        logger.info("⏹️ Остановлено пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)