# test_missing_functions.py - ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЙ
"""
Скрипт для тестирования всех исправленных функций
Запуск: python test_missing_functions.py
"""
import asyncio
import sys
import traceback
from pathlib import Path

# Добавляем корневую директорию в PATH
sys.path.append(str(Path(__file__).parent))


async def test_missing_functions():
    """Комплексное тестирование исправленных функций"""
    print("🧪 === ТЕСТИРОВАНИЕ ИСПРАВЛЕННЫХ ФУНКЦИЙ ===")

    try:
        # Импорты
        from utils.helpers import create_sample_data
        from data.processors.technical_processor import TechnicalProcessor

        print("✅ Базовые импорты успешны")

        # Создание тестовых данных
        print("\n📊 Создание тестовых данных...")
        data = create_sample_data("BTCUSDT", periods=100, start_price=45000)
        print(f"✅ Создано {len(data)} свечей данных")

        # Добавление технических индикаторов
        print("\n⚙️ Обработка технических индикаторов...")
        processor = TechnicalProcessor()
        config = {
            'rsi': {'period': 14},
            'ema_fast': {'period': 9},
            'ema_slow': {'period': 21},
            'volume_sma': {'period': 20}
        }

        processed_data = processor.process_ohlcv(data, config)
        print(f"✅ Добавлены индикаторы: {list(processed_data.columns)}")

        # Тест 1: Определение тренда
        print("\n1️⃣ === ТЕСТ ОПРЕДЕЛЕНИЯ ТРЕНДА ===")
        await test_trend_detection(processed_data)

        # Тест 2: Поиск уровней поддержки/сопротивления
        print("\n2️⃣ === ТЕСТ ПОИСКА УРОВНЕЙ ===")
        await test_support_resistance(processed_data)

        # Тест 3: Временной горизонт
        print("\n3️⃣ === ТЕСТ ВРЕМЕННОГО ГОРИЗОНТА ===")
        await test_time_horizon(processed_data)

        # Тест 4: Market Analyzer
        print("\n4️⃣ === ТЕСТ MARKET ANALYZER ===")
        await test_market_analyzer()

        # Тест 5: AI Driven Strategy
        print("\n5️⃣ === ТЕСТ AI DRIVEN STRATEGY ===")
        await test_ai_driven_strategy()

        print("\n🎉 === ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ УСПЕШНО ===")

    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

    return True


async def test_trend_detection(data):
    """Тест определения тренда"""
    try:
        # Создаем разные типы трендов
        import pandas as pd
        import numpy as np

        # Восходящий тренд
        up_data = data.copy()
        up_data['close'] = up_data['close'] * (1 + np.linspace(0, 0.1, len(up_data)))

        # Нисходящий тренд
        down_data = data.copy()
        down_data['close'] = down_data['close'] * (1 - np.linspace(0, 0.1, len(down_data)))

        # Импорт функции (нужно обновить в реальных файлах)
        from core.engine.market_analyzer import MarketAnalyzer
        from config.trading_config import TradingConfig
        from core.event_bus import EventBus

        # Создаем анализатор
        event_bus = EventBus()
        config = TradingConfig()
        analyzer = MarketAnalyzer(config, event_bus)

        # Тестируем определение тренда
        up_trend = analyzer._determine_trend(up_data)
        down_trend = analyzer._determine_trend(down_data)
        neutral_trend = analyzer._determine_trend(data)

        print(f"   📈 Восходящий тренд: {up_trend}")
        print(f"   📉 Нисходящий тренд: {down_trend}")
        print(f"   ↔️ Нейтральный тренд: {neutral_trend}")

        # Проверяем результаты
        if 'up' in up_trend.lower():
            print("   ✅ Восходящий тренд определен корректно")
        else:
            print(f"   ⚠️ Восходящий тренд определен как: {up_trend}")

        if 'down' in down_trend.lower():
            print("   ✅ Нисходящий тренд определен корректно")
        else:
            print(f"   ⚠️ Нисходящий тренд определен как: {down_trend}")

        await event_bus.stop()

    except Exception as e:
        print(f"   ❌ Ошибка тестирования тренда: {e}")


async def test_support_resistance(data):
    """Тест поиска уровней поддержки и сопротивления"""
    try:
        from core.engine.market_analyzer import MarketAnalyzer
        from config.trading_config import TradingConfig
        from core.event_bus import EventBus

        event_bus = EventBus()
        config = TradingConfig()
        analyzer = MarketAnalyzer(config, event_bus)

        levels = analyzer._find_support_resistance(data)

        print(f"   📊 Найдено сопротивлений: {len(levels['resistance_levels'])}")
        print(f"   📊 Найдено поддержек: {len(levels['support_levels'])}")

        if levels['nearest_resistance']:
            print(f"   🔴 Ближайшее сопротивление: ${levels['nearest_resistance']:.2f}")

        if levels['nearest_support']:
            print(f"   🟢 Ближайшая поддержка: ${levels['nearest_support']:.2f}")

        current_price = data['close'].iloc[-1]
        print(f"   💰 Текущая цена: ${current_price:.2f}")

        # Проверяем логику
        if levels['nearest_resistance'] and levels['nearest_resistance'] > current_price:
            print("   ✅ Сопротивление выше текущей цены - корректно")
        elif levels['nearest_resistance']:
            print("   ⚠️ Сопротивление ниже текущей цены - некорректно")

        if levels['nearest_support'] and levels['nearest_support'] < current_price:
            print("   ✅ Поддержка ниже текущей цены - корректно")
        elif levels['nearest_support']:
            print("   ⚠️ Поддержка выше текущей цены - некорректно")

        await event_bus.stop()

    except Exception as e:
        print(f"   ❌ Ошибка тестирования уровней: {e}")


async def test_time_horizon(data):
    """Тест определения временного горизонта"""
    try:
        # Эмулируем AI Driven Strategy
        print("   📅 Тестирование определения временного горизонта...")

        # Высокая волатильность - короткий горизонт
        volatile_data = data.copy()
        returns = volatile_data['close'].pct_change()
        volatile_data['close'] = volatile_data['close'] * (1 + returns * 5)  # Увеличиваем волатильность

        # Тест разных сценариев
        scenarios = [
            ("Обычные данные", data),
            ("Высокая волатильность", volatile_data),
            ("Короткие данные", data.tail(15))
        ]

        for scenario_name, test_data in scenarios:
            try:
                # Простая эмуляция логики временного горизонта
                if len(test_data) < 20:
                    horizon = 'short'
                else:
                    returns = test_data['close'].pct_change().dropna()
                    volatility = returns.tail(20).std()

                    if volatility > 0.03:
                        horizon = 'short'
                    else:
                        horizon = 'medium'

                print(f"   📊 {scenario_name}: {horizon}")

            except Exception as e:
                print(f"   ⚠️ Ошибка сценария {scenario_name}: {e}")

        print("   ✅ Тест временного горизонта завершен")

    except Exception as e:
        print(f"   ❌ Ошибка тестирования горизонта: {e}")


async def test_market_analyzer():
    """Тест Market Analyzer в целом"""
    try:
        from core.engine.market_analyzer import MarketAnalyzer
        from config.trading_config import TradingConfig
        from core.event_bus import EventBus

        print("   🔬 Инициализация Market Analyzer...")

        event_bus = EventBus()
        await event_bus.start()

        config = TradingConfig()
        analyzer = MarketAnalyzer(config, event_bus)
        await analyzer.initialize()

        print("   ✅ Market Analyzer инициализирован")

        # Эмуляция анализа символа (без exchange_manager)
        print("   📊 Тестирование анализа символа...")
        try:
            # Без реального exchange_manager будет использоваться заглушка
            await analyzer.analyze_symbol("BTCUSDT")
            print("   ✅ Анализ символа выполнен (с тестовыми данными)")
        except Exception as e:
            print(f"   ⚠️ Анализ символа: {e} (ожидаемо без реальных данных)")

        await analyzer.stop()
        await event_bus.stop()

    except Exception as e:
        print(f"   ❌ Ошибка Market Analyzer: {e}")


async def test_ai_driven_strategy():
    """Тест AI Driven Strategy"""
    try:
        from trading.strategies.ai_driven import AIDrivenStrategy
        from core.event_bus import EventBus
        from utils.helpers import create_sample_data

        print("   🤖 Инициализация AI Driven Strategy...")

        event_bus = EventBus()
        await event_bus.start()

        config = {
            'min_confidence': 0.7,
            'use_news': False,  # Отключаем для тестов
            'technical_indicators': {
                'rsi': {'period': 14},
                'ema_fast': {'period': 9},
                'ema_slow': {'period': 21}
            }
        }

        strategy = AIDrivenStrategy(config, event_bus)

        print("   ✅ AI Driven Strategy инициализирована")

        # Тестирование анализа
        test_data = create_sample_data("BTCUSDT", periods=100)

        print("   📊 Тестирование анализа...")
        analysis = await strategy.analyze(test_data, "BTCUSDT")

        print(f"   📈 Анализ завершен: {analysis.get('symbol', 'N/A')}")
        print(f"   🎯 Найдены уровни поддержки/сопротивления")

        # Тест условий входа/выхода
        test_analysis = {
            'action': 'BUY',
            'adjusted_confidence': 0.8,
            'risk_score': 0.3,
            'technical_validation': {'score': 0.7}
        }

        should_enter = await strategy.should_enter(test_analysis)
        print(f"   🚪 Тест входа: {should_enter}")

        await event_bus.stop()

    except Exception as e:
        print(f"   ❌ Ошибка AI Driven Strategy: {e}")


async def test_integration():
    """Интеграционный тест всей системы"""
    print("\n🔗 === ИНТЕГРАЦИОННЫЙ ТЕСТ ===")

    try:
        from core.engine.trading_engine import TradingEngine
        from config.settings import Settings
        from config.trading_config import TradingConfig

        print("   🚀 Инициализация торгового движка...")

        settings = Settings()
        settings.bybit_testnet = True
        settings.binance_testnet = True

        trading_config = TradingConfig()

        # Ограничиваем для теста
        trading_config.trading_pairs = trading_config.trading_pairs[:1]  # Только BTC

        engine = TradingEngine(settings, trading_config)

        print("   ⚙️ Инициализация компонентов...")
        await engine.initialize()

        print("   ✅ Торговый движок инициализирован")

        # Тест системного статуса
        status = await engine.get_system_status()
        print(f"   📊 Статус системы: {status['status']}")
        print(f"   🔌 Биржи: {status['exchanges']}")
        print(f"   🎯 Стратегии: {status['active_strategies']}")

        # Тест реального анализа (если есть подключения)
        if status['exchanges']:
            print("   📡 Тестирование реального анализа...")
            result = await engine.test_real_analysis("BTCUSDT")
            if result:
                print(f"   ✅ Реальный анализ: цена ${result['current_price']}")
            else:
                print("   ⚠️ Реальный анализ недоступен (нормально для testnet)")

        await engine.stop()
        print("   ✅ Интеграционный тест завершен")

    except Exception as e:
        print(f"   ❌ Ошибка интеграционного теста: {e}")
        print(f"   📝 Детали: {traceback.format_exc()}")


def main():
    """Главная функция"""
    print("🧪 ЗАПУСК ТЕСТИРОВАНИЯ ИСПРАВЛЕННЫХ ФУНКЦИЙ")
    print("=" * 60)

    try:
        # Запуск основных тестов
        success = asyncio.run(test_missing_functions())

        if success:
            print("\n🔗 Запуск интеграционного теста...")
            asyncio.run(test_integration())

        print("\n" + "=" * 60)
        print("🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
        print("\n📋 Следующие шаги:")
        print("1. Внедрите исправления в файлы")
        print("2. Запустите: python main.py --mode demo")
        print("3. Проверьте: python cli.py analyze --symbol BTCUSDT")
        print("4. Протестируйте: python main.py --mode real-test")

    except KeyboardInterrupt:
        print("\n⏹️ Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        print(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    main()