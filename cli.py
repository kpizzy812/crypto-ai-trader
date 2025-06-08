# cli.py - ОБНОВЛЕННАЯ ВЕРСИЯ С РЕАЛЬНЫМИ ДАННЫМИ
import click
import asyncio
import pandas as pd
from loguru import logger
from config import Settings, TradingConfig
from utils.logger import setup_logger
import traceback

# Настройка логирования
setup_logger()


@click.group()
def cli():
    """Crypto AI Trader CLI - Обновленная версия с реальными данными"""
    pass


@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Торговая пара')
@click.option('--timeframe', default='5m', help='Таймфрейм')
@click.option('--limit', default=100, help='Количество свечей')
@click.option('--real', is_flag=True, help='Использовать реальные данные с биржи')
def analyze(symbol, timeframe, limit, real):
    """Анализ рынка"""
    asyncio.run(_analyze_market(symbol, timeframe, limit, real))


@cli.command()
@click.option('--exchange', default='bybit', help='Биржа для тестирования')
def test_connection(exchange):
    """Тест подключения к бирже"""
    asyncio.run(_test_exchange_connection(exchange))


@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Торговая пара')
@click.option('--real', is_flag=True, help='Использовать реальные данные')
@click.option('--mock', is_flag=True, help='Использовать mock AI')
def ai_analyze(symbol, real, mock):
    """AI анализ рынка"""
    asyncio.run(_ai_analyze_market(symbol, real, mock))


@cli.command()
def run():
    """Запуск торгового движка"""
    asyncio.run(_run_trading_engine())


@cli.command()
def demo():
    """Запуск демо режима"""
    asyncio.run(_run_demo())


@cli.command()
@click.option('--symbols', default='BTCUSDT,ETHUSDT,SOLUSDT', help='Список символов через запятую')
def real_test(symbols):
    """Тестирование с реальными данными"""
    symbol_list = [s.strip() for s in symbols.split(',')]
    asyncio.run(_real_data_test(symbol_list))


# Реализация команд
async def _analyze_market(symbol: str, timeframe: str, limit: int, use_real: bool):
    """Анализ рынка с возможностью использования реальных данных"""
    settings = Settings()

    click.echo(f"🔍 Анализ {symbol} на таймфрейме {timeframe}")

    if use_real:
        click.echo("📡 Режим: Реальные данные с биржи")
    else:
        click.echo("🧪 Режим: Тестовые данные")

    try:
        if use_real:
            # Реальные данные с биржи
            from core.event_bus import EventBus
            from core.engine.exchange_manager import ExchangeManager

            event_bus = EventBus()
            await event_bus.start()

            try:
                exchange_manager = ExchangeManager(settings, event_bus)
                await exchange_manager.initialize()

                exchanges = await exchange_manager.get_connected_exchanges()
                if exchanges:
                    click.echo(f"✅ Подключены биржи: {exchanges}")

                    # Получение реальных данных
                    ohlcv_data = await exchange_manager.get_market_data(symbol, timeframe, limit)

                    if not ohlcv_data.empty:
                        # Анализ реальных данных
                        current_price = ohlcv_data['close'].iloc[-1]
                        volume_avg = ohlcv_data['volume'].rolling(20).mean().iloc[-1]
                        current_volume = ohlcv_data['volume'].iloc[-1]

                        click.echo(f"\n📊 Реальный анализ {symbol}:")
                        click.echo(f"💰 Текущая цена: ${current_price:,.2f}")
                        click.echo(f"📊 Объем: {current_volume:,.0f} (ср. {volume_avg:,.0f})")
                        click.echo(f"🔊 Активность: {'Высокая' if current_volume > volume_avg * 1.5 else 'Обычная'}")

                        # Технический анализ
                        from data.processors.technical_processor import TechnicalProcessor
                        processor = TechnicalProcessor()

                        config = {
                            'rsi': {'period': 14},
                            'ema_fast': {'period': 9},
                            'ema_slow': {'period': 21}
                        }

                        processed = processor.process_ohlcv(ohlcv_data, config)
                        current = processed.iloc[-1]

                        if 'rsi' in current and not pd.isna(current['rsi']):
                            click.echo(f"📈 RSI: {current['rsi']:.2f}")

                        # Отображение последних свечей
                        click.echo(f"\n📈 Последние 5 свечей:")
                        recent_data = ohlcv_data.tail(5)
                        for idx, row in recent_data.iterrows():
                            direction = "🟢" if row['close'] > row['open'] else "🔴"
                            click.echo(
                                f"{direction} {idx.strftime('%H:%M')} | O: {row['open']:.2f} H: {row['high']:.2f} L: {row['low']:.2f} C: {row['close']:.2f}")
                    else:
                        click.echo("❌ Не удалось получить реальные данные")
                else:
                    click.echo("⚠️ Нет подключенных бирж. Проверьте API ключи в .env")

                await exchange_manager.stop()

            finally:
                await event_bus.stop()
        else:
            # Тестовые данные
            from utils.helpers import create_sample_data
            ohlcv_data = create_sample_data(symbol, periods=limit)

            current_price = ohlcv_data['close'].iloc[-1]
            volume_avg = ohlcv_data['volume'].rolling(20).mean().iloc[-1]
            current_volume = ohlcv_data['volume'].iloc[-1]

            click.echo(f"\n📊 Тестовый анализ {symbol}:")
            click.echo(f"💰 Цена: ${current_price:,.2f}")
            click.echo(f"📊 Объем: {current_volume:,.0f} (ср. {volume_avg:,.0f})")

    except ImportError:
        click.echo("❌ Модули не найдены")
        click.echo("💡 Создайте недостающие файлы из артефактов")
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}")
        if logger.level <= 10:  # DEBUG level
            click.echo(f"Детали: {traceback.format_exc()}")


async def _test_exchange_connection(exchange: str):
    """Тест подключения к бирже с улучшенной обработкой"""
    settings = Settings()

    try:
        from core.event_bus import EventBus
        from core.engine.exchange_manager import ExchangeManager

        event_bus = EventBus()
        await event_bus.start()

        try:
            exchange_manager = ExchangeManager(settings, event_bus)
            await exchange_manager.initialize()

            exchanges = await exchange_manager.get_connected_exchanges()

            if exchanges:
                click.echo(f"✅ Подключение успешно!")
                click.echo(f"🔌 Подключенные биржи: {exchanges}")

                # Тест получения данных
                try:
                    data = await exchange_manager.get_market_data("BTCUSDT", "5m", 5)
                    if not data.empty:
                        current_price = data['close'].iloc[-1]
                        click.echo(f"📊 BTC/USDT: ${current_price:,.2f}")
                    else:
                        click.echo("⚠️ Не удалось получить тестовые данные")
                except Exception as e:
                    click.echo(f"⚠️ Не удалось получить рыночные данные: {e}")
            else:
                click.echo(f"❌ Ошибка подключения к биржам")
                click.echo("💡 Проверьте API ключи в .env файле")

            await exchange_manager.stop()

        finally:
            await event_bus.stop()

    except ImportError:
        click.echo("❌ Модуль exchange_manager не найден")
        click.echo("💡 Создайте файл из артефакта 'Исправленный Exchange Manager'")
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}")


async def _ai_analyze_market(symbol: str, use_real: bool, mock: bool):
    """AI анализ рынка с обработкой ошибок"""
    try:
        if use_real:
            click.echo(f"🌐🤖 Реальный AI анализ {symbol}")

            # Получение реальных данных
            settings = Settings()
            from core.event_bus import EventBus
            from core.engine.exchange_manager import ExchangeManager

            event_bus = EventBus()
            await event_bus.start()

            try:
                exchange_manager = ExchangeManager(settings, event_bus)
                await exchange_manager.initialize()

                exchanges = await exchange_manager.get_connected_exchanges()
                if exchanges:
                    ohlcv_data = await exchange_manager.get_market_data(symbol, "5m", 100)

                    if not ohlcv_data.empty:
                        current_price = ohlcv_data['close'].iloc[-1]
                        price_change = (ohlcv_data['close'].iloc[-1] - ohlcv_data['close'].iloc[0]) / \
                                       ohlcv_data['close'].iloc[0] * 100

                        # AI анализ
                        if mock:
                            from ai.mock_analyzer import MockAIAnalyzer
                            analyzer = MockAIAnalyzer()
                        else:
                            from ai.openai_analyzer import OpenAIAnalyzer
                            analyzer = OpenAIAnalyzer()

                        analysis = await analyzer.analyze_market(ohlcv_data, symbol)

                        # Отображение результатов
                        click.echo(f"\n🎯 AI Анализ {symbol}:")
                        click.echo(f"📈 Цена: ${current_price:,.2f}")
                        click.echo(f"📊 Изменение: {price_change:+.2f}%")
                        click.echo(f"🤖 Рекомендация: {analysis['action']}")
                        click.echo(f"💪 Уверенность: {analysis['confidence']:.1%}")
                        click.echo(f"💭 Обоснование: {analysis['reasoning']}")
                    else:
                        click.echo("❌ Не удалось получить реальные данные")
                else:
                    click.echo("⚠️ Нет подключений к биржам")

                await exchange_manager.stop()

            finally:
                await event_bus.stop()
        else:
            # Тестовые данные
            from utils.helpers import create_sample_data
            from ai.mock_analyzer import MockAIAnalyzer

            ohlcv_data = create_sample_data(symbol, periods=100)
            analyzer = MockAIAnalyzer()

            click.echo(f"🧪🤖 Тестовый AI анализ {symbol}")
            analysis = await analyzer.analyze_market(ohlcv_data, symbol)

            # Отображение результатов
            click.echo(f"\n🎯 AI Анализ {symbol}:")
            click.echo(f"📈 Рекомендация: {analysis['action']}")
            click.echo(f"💪 Сила сигнала: {analysis['signal_strength']:.2f}")
            click.echo(f"🎯 Уверенность: {analysis['confidence']:.1%}")
            click.echo(f"⚠️ Уровень риска: {analysis['risk_level']}")
            click.echo(f"💭 Обоснование: {analysis['reasoning']}")

        # Рекомендации по риск-менеджменту
        if analysis['confidence'] > 0.7 and analysis['action'] != 'HOLD':
            click.echo(f"\n✅ Сигнал достаточно уверенный для торговли")
        else:
            click.echo(f"\n⚠️ Сигнал неуверенный, рекомендуется воздержаться от торговли")

    except ImportError as e:
        click.echo(f"❌ Ошибка импорта: {e}")
        click.echo("💡 Убедитесь что созданы все необходимые файлы")
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}")


async def _real_data_test(symbols: list):
    """Комплексное тестирование с реальными данными"""
    click.echo("🌐 === КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ С РЕАЛЬНЫМИ ДАННЫМИ ===")

    try:
        # Импорт функции из main.py
        from main import run_real_data_test

        # Запуск тестирования
        results = await run_real_data_test()

        if results:
            click.echo("\n🎉 === РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ===")
            for symbol, result in results.items():
                click.echo(f"\n📊 {symbol}:")
                click.echo(f"   💰 Цена: ${result['current_price']:,.2f}")
                click.echo(f"   📈 Изменение: {result['price_change_24h']:+.2f}%")
                click.echo(f"   🤖 AI: {result['analysis']['action']}")
                click.echo(f"   💪 Уверенность: {result['analysis']['confidence']:.1%}")
        else:
            click.echo("❌ Тестирование не дало результатов")

    except Exception as e:
        click.echo(f"❌ Ошибка тестирования: {e}")


async def _run_trading_engine():
    """Запуск торгового движка"""
    click.echo("🚀 Запуск торгового движка...")
    click.echo("⚠️ Используется testnet режим для безопасности")

    try:
        # Пытаемся запустить полный движок
        from main import run_bot_mode
        await run_bot_mode()
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}")


async def _run_demo():
    """Запуск демо режима"""
    click.echo("🎯 Запуск демо режима...")

    try:
        # Импортируем и запускаем демо из main
        from main import run_demo_mode
        await run_demo_mode()

    except ImportError:
        click.echo("❌ Модуль main не найден или поврежден")
        click.echo("💡 Обновите main.py из артефакта")
    except Exception as e:
        click.echo(f"❌ Ошибка демо режима: {e}")


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        click.echo(f"💥 Критическая ошибка CLI: {e}")
        logger.error(f"CLI error: {e}")
        logger.error(traceback.format_exc())