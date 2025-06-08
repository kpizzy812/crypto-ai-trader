# main.py - PRODUCTION READY VERSION
"""
Главная точка входа - готовая к продакшену версия
"""
import asyncio
import uvicorn
import argparse
import sys
import traceback
from pathlib import Path
from loguru import logger

from config.settings import Settings
from config.trading_config import TradingConfig
from utils.logger import setup_logger


async def run_real_trading():
    """Запуск реальной торговли в testnet"""
    setup_logger("INFO", "logs/real_trading.log")

    logger.info("🤖 === ЗАПУСК РЕАЛЬНОЙ ТОРГОВЛИ (TESTNET) ===")

    settings = Settings()
    trading_config = TradingConfig()

    # Принудительно testnet для безопасности
    settings.bybit_testnet = True
    settings.binance_testnet = True

    # Проверка обязательных настроек
    if not _validate_settings(settings):
        logger.error("❌ Некорректные настройки. Проверьте .env файл")
        return False

    try:
        from core.engine.trading_engine import TradingEngine

        logger.info("🚀 Инициализация торгового движка...")
        engine = TradingEngine(settings, trading_config)

        # Инициализация и проверка подключений
        await engine.initialize()

        # Проверка подключений к биржам
        exchanges = await engine.exchange_manager.get_connected_exchanges()
        if not exchanges:
            logger.error("❌ Нет подключений к биржам. Проверьте API ключи")
            return False

        logger.info(f"✅ Подключены биржи: {exchanges}")

        # Проверка балансов
        balance_summary = await engine.exchange_manager.get_balance_summary()
        for exchange, info in balance_summary.items():
            if info['connected']:
                logger.info(f"💰 {exchange}: {info['total_assets']} активов")
            else:
                logger.warning(f"⚠️ {exchange}: не подключен - {info.get('error', 'unknown')}")

        # Тест получения реальных данных
        logger.info("📡 Тестирование получения рыночных данных...")
        test_data = await engine.exchange_manager.get_market_data("BTCUSDT", "5m", 10)
        if not test_data.empty:
            current_price = test_data['close'].iloc[-1]
            logger.info(f"✅ BTC/USDT: ${current_price:,.2f}")
        else:
            logger.warning("⚠️ Не удалось получить рыночные данные")

        # Запуск торгового цикла
        logger.info("🎯 Запуск торгового цикла...")
        logger.warning("⚠️ ВНИМАНИЕ: Торговля в TESTNET режиме")

        await engine.start()

    except KeyboardInterrupt:
        logger.info("⏹️ Остановка по запросу пользователя")
        return True
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


async def run_comprehensive_test():
    """Комплексное тестирование всех систем"""
    setup_logger("DEBUG", "logs/comprehensive_test.log")

    logger.info("🧪 === КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ СИСТЕМ ===")

    settings = Settings()
    trading_config = TradingConfig()

    # Принудительно testnet
    settings.bybit_testnet = True
    settings.binance_testnet = True

    test_results = {
        'exchange_connections': False,
        'market_data': False,
        'ai_analysis': False,
        'strategies': False,
        'risk_management': False,
        'backtesting': False
    }

    try:
        # 1. Тест подключений к биржам
        logger.info("🔌 === ТЕСТ ПОДКЛЮЧЕНИЙ К БИРЖАМ ===")
        test_results['exchange_connections'] = await _test_exchange_connections(settings)

        # 2. Тест получения рыночных данных
        logger.info("📡 === ТЕСТ ПОЛУЧЕНИЯ ДАННЫХ ===")
        test_results['market_data'] = await _test_market_data(settings)

        # 3. Тест AI анализа
        logger.info("🤖 === ТЕСТ AI АНАЛИЗА ===")
        test_results['ai_analysis'] = await _test_ai_analysis()

        # 4. Тест стратегий
        logger.info("🎯 === ТЕСТ СТРАТЕГИЙ ===")
        test_results['strategies'] = await _test_strategies(trading_config)

        # 5. Тест риск-менеджмента
        logger.info("⚠️ === ТЕСТ РИСК-МЕНЕДЖМЕНТА ===")
        test_results['risk_management'] = await _test_risk_management(trading_config)

        # 6. Тест бэктестинга
        logger.info("📊 === ТЕСТ БЭКТЕСТИНГА ===")
        test_results['backtesting'] = await _test_backtesting()

        # Итоговый отчет
        logger.info("\n🎉 === ИТОГОВЫЙ ОТЧЕТ ===")
        total_tests = len(test_results)
        passed_tests = sum(test_results.values())

        for test_name, result in test_results.items():
            status = "✅ ПРОЙДЕН" if result else "❌ НЕ ПРОЙДЕН"
            logger.info(f"   {test_name}: {status}")

        logger.info(f"\n📊 Результат: {passed_tests}/{total_tests} тестов пройдено")

        if passed_tests == total_tests:
            logger.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к торговле")
            return True
        else:
            logger.warning(f"⚠️ {total_tests - passed_tests} тестов не пройдено")
            return False

    except Exception as e:
        logger.error(f"❌ Критическая ошибка тестирования: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


async def run_integrated_backtest():
    """Запуск интегрированного бэктестинга"""
    setup_logger("INFO", "logs/integrated_backtest.log")

    logger.info("📊 === ЗАПУСК ИНТЕГРИРОВАННОГО БЭКТЕСТИНГА ===")

    try:
        from scripts.integrated_backtest import run_integrated_backtest as run_backtest
        await run_backtest()
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка бэктестинга: {e}")
        return False


async def run_api_server():
    """Запуск API сервера"""
    setup_logger("INFO", "logs/api_server.log")

    logger.info("🌐 === ЗАПУСК API СЕРВЕРА ===")

    try:
        from api.main import app

        # Настройка и запуск сервера
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True
        )

        server = uvicorn.Server(config)

        logger.info("🚀 API сервер запущен на http://localhost:8000")
        logger.info("📊 Dashboard доступен по адресу: http://localhost:8000")

        await server.serve()

    except Exception as e:
        logger.error(f"❌ Ошибка запуска API сервера: {e}")
        return False


async def run_position_live_test():
    """Тестирование открытия реальной позиции с минимальной суммой"""
    setup_logger("INFO", "logs/live_position_test.log")

    logger.info("💰 === ТЕСТ РЕАЛЬНОЙ ПОЗИЦИИ (МИНИМАЛЬНАЯ СУММА) ===")
    logger.warning("⚠️ ВНИМАНИЕ: Будет открыта реальная позиция в testnet!")

    # Подтверждение от пользователя
    try:
        confirmation = input("Продолжить? (yes/no): ").lower()
        if confirmation != 'yes':
            logger.info("❌ Тест отменен пользователем")
            return False
    except KeyboardInterrupt:
        logger.info("❌ Тест прерван")
        return False

    settings = Settings()
    trading_config = TradingConfig()

    # Принудительно testnet
    settings.bybit_testnet = True
    settings.binance_testnet = True

    try:
        from core.engine.trading_engine import TradingEngine

        engine = TradingEngine(settings, trading_config)
        await engine.initialize()

        exchanges = await engine.exchange_manager.get_connected_exchanges()
        if not exchanges:
            logger.error("❌ Нет подключений к биржам")
            return False

        # Получаем баланс
        balance_summary = await engine.exchange_manager.get_balance_summary()
        exchange_name = exchanges[0]
        exchange_balance = balance_summary[exchange_name]

        if not exchange_balance['connected']:
            logger.error(f"❌ {exchange_name} не подключен")
            return False

        # Проверяем наличие USDT
        usdt_balance = 0
        for asset, data in exchange_balance['balances'].items():
            if asset == 'USDT':
                usdt_balance = float(data['free'])
                break

        logger.info(f"💰 Доступно USDT: ${usdt_balance:.2f}")

        if usdt_balance < 10:
            logger.error("❌ Недостаточно USDT для теста (минимум $10)")
            logger.info("💡 Получите тестовые средства на testnet")
            return False

        # Получаем текущую цену
        market_data = await engine.exchange_manager.get_market_data("BTCUSDT", "5m", 1)
        if market_data.empty:
            logger.error("❌ Не удалось получить цену BTC")
            return False

        current_price = float(market_data['close'].iloc[-1])
        logger.info(f"📈 Текущая цена BTC/USDT: ${current_price:,.2f}")

        # Рассчитываем минимальное количество (примерно $5)
        test_amount = 5.0  # $5
        quantity = test_amount / current_price

        # Округляем до минимального размера лота
        quantity = round(quantity, 6)  # Обычно минимум 0.000001 BTC

        logger.info(f"📊 Планируемая позиция: {quantity} BTC (~${test_amount:.2f})")

        # Размещаем тестовый ордер
        logger.info("📝 Размещение тестового ордера...")

        try:
            order_result = await engine.exchange_manager.place_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=quantity,
                strategy="live_test"
            )

            if order_result:
                logger.info(f"✅ Ордер размещен: {order_result.order.id}")
                logger.info(f"📊 Статус: {order_result.order.status}")

                # Ждем немного и проверяем статус
                await asyncio.sleep(5)

                # Получаем обновленную информацию об ордере
                updated_order = await engine.exchanges[exchange_name].get_order(
                    order_result.order.id,
                    "BTCUSDT"
                )

                if updated_order:
                    logger.info(f"📊 Финальный статус: {updated_order.status}")

                    if updated_order.status == 'filled':
                        logger.info("🎉 ТЕСТОВАЯ ПОЗИЦИЯ УСПЕШНО ОТКРЫТА!")
                        logger.info(f"💰 Исполнено по цене: ${updated_order.price}")

                        # Сразу же закрываем позицию
                        logger.info("🔄 Закрытие тестовой позиции...")

                        close_order = await engine.exchange_manager.place_order(
                            symbol="BTCUSDT",
                            side="sell",
                            order_type="market",
                            quantity=quantity,
                            strategy="live_test_close"
                        )

                        if close_order:
                            logger.info("✅ Позиция закрыта")
                            logger.info("🎉 ТЕСТ РЕАЛЬНОЙ ТОРГОВЛИ УСПЕШНО ЗАВЕРШЕН!")
                            return True
                        else:
                            logger.warning("⚠️ Не удалось автоматически закрыть позицию")
                            logger.warning("💡 Закройте позицию вручную через интерфейс биржи")
                    else:
                        logger.warning(f"⚠️ Ордер не исполнен: {updated_order.status}")
                else:
                    logger.warning("⚠️ Не удалось получить статус ордера")
            else:
                logger.error("❌ Не удалось разместить ордер")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка размещения ордера: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ Критическая ошибка теста: {e}")
        return False

    finally:
        try:
            await engine.stop()
        except:
            pass


# Вспомогательные функции для тестирования
async def _test_exchange_connections(settings: Settings) -> bool:
    """Тест подключений к биржам"""
    try:
        from core.event_bus import EventBus
        from core.engine.exchange_manager import ExchangeManager

        event_bus = EventBus()
        await event_bus.start()

        exchange_manager = ExchangeManager(settings, event_bus)
        await exchange_manager.initialize()

        exchanges = await exchange_manager.get_connected_exchanges()
        connection_status = await exchange_manager.get_connection_status()

        logger.info(f"📊 Подключенные биржи: {exchanges}")
        logger.info(f"📊 Статус подключений: {connection_status}")

        # Тест подключений
        test_results = await exchange_manager.test_all_connections()

        for exchange, status in test_results.items():
            if status:
                logger.info(f"✅ {exchange}: подключение работает")
            else:
                logger.warning(f"⚠️ {exchange}: проблемы с подключением")

        await exchange_manager.stop()
        await event_bus.stop()

        return len(exchanges) > 0

    except Exception as e:
        logger.error(f"❌ Ошибка теста подключений: {e}")
        return False


async def _test_market_data(settings: Settings) -> bool:
    """Тест получения рыночных данных"""
    try:
        from core.event_bus import EventBus
        from core.engine.exchange_manager import ExchangeManager

        event_bus = EventBus()
        await event_bus.start()

        exchange_manager = ExchangeManager(settings, event_bus)
        await exchange_manager.initialize()

        # Тестируем получение данных для разных символов
        test_symbols = ["BTCUSDT", "ETHUSDT"]
        success_count = 0

        for symbol in test_symbols:
            try:
                data = await exchange_manager.get_market_data(symbol, "5m", 10)
                if not data.empty and len(data) > 0:
                    current_price = data['close'].iloc[-1]
                    logger.info(f"✅ {symbol}: ${current_price:,.2f} ({len(data)} свечей)")
                    success_count += 1
                else:
                    logger.warning(f"⚠️ {symbol}: пустые данные")
            except Exception as e:
                logger.warning(f"⚠️ {symbol}: ошибка - {e}")

        await exchange_manager.stop()
        await event_bus.stop()

        return success_count > 0

    except Exception as e:
        logger.error(f"❌ Ошибка теста данных: {e}")
        return False


async def _test_ai_analysis() -> bool:
    """Тест AI анализа"""
    try:
        from ai.mock_analyzer import MockAIAnalyzer
        from utils.helpers import create_sample_data

        analyzer = MockAIAnalyzer()
        test_data = create_sample_data("BTCUSDT", periods=50)

        analysis = await analyzer.analyze_market(test_data, "BTCUSDT")

        required_fields = ['action', 'confidence', 'reasoning']
        if all(field in analysis for field in required_fields):
            logger.info(f"✅ AI анализ: {analysis['action']} (уверенность: {analysis['confidence']:.1%})")
            return True
        else:
            logger.error(f"❌ AI анализ: отсутствуют поля {required_fields}")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка теста AI: {e}")
        return False


async def _test_strategies(trading_config: TradingConfig) -> bool:
    """Тест торговых стратегий"""
    try:
        from trading.strategies.simple_momentum import SimpleMomentumStrategy
        from utils.helpers import create_sample_data

        # Тест SimpleMomentum
        config = {
            'indicators': trading_config.technical_indicators,
            'position_size_percent': 2.0
        }

        strategy = SimpleMomentumStrategy(config)
        test_data = create_sample_data("BTCUSDT", periods=100)

        analysis = await strategy.analyze(test_data, "BTCUSDT")

        if 'recommendation' in analysis:
            logger.info(
                f"✅ SimpleMomentum: {analysis['recommendation']} (уверенность: {analysis.get('confidence', 0):.1%})")
            return True
        else:
            logger.error("❌ SimpleMomentum: нет рекомендации")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка теста стратегий: {e}")
        return False


async def _test_risk_management(trading_config: TradingConfig) -> bool:
    """Тест риск-менеджмента"""
    try:
        from risk.risk_manager import RiskManager
        from core.portfolio import Portfolio
        from decimal import Decimal

        portfolio = Portfolio(Decimal("10000"))
        risk_manager = RiskManager(trading_config.risk, portfolio)

        # Тест проверки риска позиции
        risk_ok = await risk_manager.check_position_risk(
            symbol="BTCUSDT",
            side="buy",
            entry_price=Decimal("45000"),
            quantity=Decimal("0.002")  # ~$90
        )

        # Тест расчета метрик
        metrics = await risk_manager.get_risk_metrics()

        if hasattr(metrics, 'risk_score') and 0 <= metrics.risk_score <= 100:
            logger.info(f"✅ Risk Manager: риск-скор {metrics.risk_score}/100")
            logger.info(f"✅ Проверка позиции: {'разрешена' if risk_ok else 'запрещена'}")
            return True
        else:
            logger.error("❌ Risk Manager: некорректные метрики")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка теста риск-менеджмента: {e}")
        return False


async def _test_backtesting() -> bool:
    """Тест системы бэктестинга"""
    try:
        from backtest.backtester import Backtester
        from trading.strategies.simple_momentum import SimpleMomentumStrategy
        from utils.helpers import create_sample_data

        backtester = Backtester(initial_capital=10000)

        strategy_config = {
            'indicators': {
                'rsi': {'period': 14},
                'ema_fast': {'period': 9},
                'ema_slow': {'period': 21}
            }
        }

        strategy = SimpleMomentumStrategy(strategy_config)
        test_data = {"BTCUSDT": create_sample_data("BTCUSDT", periods=200)}

        result = await backtester.run(strategy, test_data)

        if result and hasattr(result, 'total_return_percent'):
            logger.info(f"✅ Бэктест: доходность {result.total_return_percent:.2f}%, сделок {result.total_trades}")
            return True
        else:
            logger.error("❌ Бэктест: некорректный результат")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка теста бэктестинга: {e}")
        return False


def _validate_settings(settings: Settings) -> bool:
    """Валидация настроек"""
    issues = []

    # Проверка API ключей (хотя бы одна биржа)
    if not ((settings.bybit_api_key and settings.bybit_api_secret) or
            (settings.binance_api_key and settings.binance_api_secret)):
        issues.append("Не настроены API ключи ни для одной биржи")

    # Проверка testnet режима
    if not settings.bybit_testnet and settings.bybit_api_key:
        issues.append("⚠️ ВНИМАНИЕ: Bybit не в testnet режиме!")

    if not settings.binance_testnet and settings.binance_api_key:
        issues.append("⚠️ ВНИМАНИЕ: Binance не в testnet режиме!")

    if issues:
        for issue in issues:
            logger.error(f"❌ {issue}")
        return False

    return True


async def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Crypto AI Trading Bot - Production Ready')
    parser.add_argument('--mode',
                        choices=['trading', 'test', 'backtest', 'api', 'both', 'live-test'],
                        default='test',
                        help='Режим запуска')
    parser.add_argument('--symbols',
                        default='BTCUSDT,ETHUSDT',
                        help='Торговые пары через запятую')
    parser.add_argument('--force-mainnet',
                        action='store_true',
                        help='ОПАСНО: Принудительно использовать mainnet')

    args = parser.parse_args()

    # Проверка безопасности
    if args.force_mainnet:
        logger.critical("⚠️ ВНИМАНИЕ: Запрос использования MAINNET!")
        try:
            confirmation = input("Вы уверены? Введите 'YES' для подтверждения: ")
            if confirmation != 'YES':
                logger.info("❌ Запуск отменен")
                return
        except KeyboardInterrupt:
            logger.info("❌ Запуск прерван")
            return

    try:
        if args.mode == 'test':
            success = await run_comprehensive_test()
            sys.exit(0 if success else 1)

        elif args.mode == 'trading':
            success = await run_real_trading()
            sys.exit(0 if success else 1)

        elif args.mode == 'backtest':
            success = await run_integrated_backtest()
            sys.exit(0 if success else 1)

        elif args.mode == 'api':
            await run_api_server()

        elif args.mode == 'live-test':
            success = await run_position_live_test()
            sys.exit(0 if success else 1)

        elif args.mode == 'both':
            # Запуск торговли и API параллельно
            trading_task = asyncio.create_task(run_real_trading())
            api_task = asyncio.create_task(run_api_server())

            done, pending = await asyncio.wait(
                [trading_task, api_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Отменяем оставшиеся задачи
            for task in pending:
                task.cancel()

        else:
            logger.error(f"❌ Неизвестный режим: {args.mode}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("👋 Остановлено пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Программа остановлена")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)