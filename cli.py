# cli.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
import click
import asyncio
from loguru import logger
from config import Settings, TradingConfig
from utils.logger import setup_logger
import traceback

# Настройка логирования
setup_logger()


@click.group()
def cli():
    """Crypto AI Trader CLI - Исправленная версия"""
    pass


@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Торговая пара')
@click.option('--timeframe', default='5m', help='Таймфрейм')
@click.option('--limit', default=100, help='Количество свечей')
def analyze(symbol, timeframe, limit):
    """Анализ рынка"""
    asyncio.run(_analyze_market(symbol, timeframe, limit))


@cli.command()
@click.option('--exchange', default='bybit', help='Биржа для тестирования')
def test_connection(exchange):
    """Тест подключения к бирже"""
    asyncio.run(_test_exchange_connection(exchange))


@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Торговая пара')
@click.option('--mock', is_flag=True, help='Использовать mock AI')
def ai_analyze(symbol, mock):
    """AI анализ рынка"""
    asyncio.run(_ai_analyze_market(symbol, mock))


@cli.command()
def run():
    """Запуск торгового движка"""
    asyncio.run(_run_trading_engine())


@cli.command()
def demo():
    """Запуск демо режима"""
    asyncio.run(_run_demo())


# Реализация команд
async def _analyze_market(symbol: str, timeframe: str, limit: int):
    """Анализ рынка с улучшенной обработкой ошибок"""
    settings = Settings()

    click.echo(f"🔍 Анализ {symbol} на таймфрейме {timeframe}")

    try:
        # Попытка использования реального подключения
        from data.collectors.exchange_collector import ExchangeDataCollector

        collector = ExchangeDataCollector(
            'bybit',
            settings.bybit_api_key,
            settings.bybit_api_secret,
            settings.bybit_testnet
        )

        try:
            # Тест подключения
            if await collector.test_connection():
                click.echo("✅ Подключение к бирже успешно")

                # Получение данных
                ohlcv_data = await collector.get_ohlcv(symbol, timeframe, limit)

                if not ohlcv_data.empty:
                    # Простой технический анализ
                    current_price = ohlcv_data['close'].iloc[-1]
                    volume_avg = ohlcv_data['volume'].rolling(20).mean().iloc[-1]
                    current_volume = ohlcv_data['volume'].iloc[-1]

                    # Результаты анализа
                    click.echo(f"\n📊 Анализ {symbol}:")
                    click.echo(f"💰 Текущая цена: ${current_price:,.2f}")
                    click.echo(f"📊 Объем: {current_volume:,.0f} (ср. {volume_avg:,.0f})")
                    click.echo(f"🔊 Активность: {'Высокая' if current_volume > volume_avg * 1.5 else 'Обычная'}")

                    # Отображение последних свечей
                    click.echo(f"\n📈 Последние 5 свечей:")
                    recent_data = ohlcv_data.tail(5)
                    for idx, row in recent_data.iterrows():
                        direction = "🟢" if row['close'] > row['open'] else "🔴"
                        click.echo(
                            f"{direction} {idx.strftime('%H:%M')} | O: {row['open']:.2f} H: {row['high']:.2f} L: {row['low']:.2f} C: {row['close']:.2f}")
                else:
                    click.echo("❌ Не удалось получить данные")
            else:
                click.echo("❌ Не удалось подключиться к бирже")

        finally:
            await collector.close()

    except ImportError:
        click.echo("❌ Модуль exchange_collector не найден")
        click.echo("💡 Создайте файл из артефакта 'Исправленный Exchange Collector'")
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}")
        if logger.level <= 10:  # DEBUG level
            click.echo(f"Детали: {traceback.format_exc()}")


async def _test_exchange_connection(exchange: str):
    """Тест подключения к бирже с улучшенной обработкой"""
    settings = Settings()

    try:
        from data.collectors.exchange_collector import ExchangeDataCollector

        if exchange.lower() == 'bybit':
            collector = ExchangeDataCollector(
                'bybit',
                settings.bybit_api_key,
                settings.bybit_api_secret,
                settings.bybit_testnet
            )
        elif exchange.lower() == 'binance':
            collector = ExchangeDataCollector(
                'binance',
                settings.binance_api_key,
                settings.binance_api_secret,
                settings.binance_testnet
            )
        else:
            click.echo(f"❌ Неподдерживаемая биржа: {exchange}")
            return

        try:
            success = await collector.test_connection()

            if success:
                click.echo(f"✅ Подключение к {exchange} успешно!")

                # Получение информации о рынках
                try:
                    ticker = await collector.get_ticker('BTCUSDT')
                    if ticker and ticker.get('last'):
                        click.echo(f"📊 BTC/USDT: ${ticker['last']:,.2f}")
                    else:
                        click.echo("⚠️ Не удалось получить тикер")
                except Exception as e:
                    click.echo(f"⚠️ Не удалось получить тикер: {e}")
            else:
                click.echo(f"❌ Ошибка подключения к {exchange}")
                click.echo("💡 Проверьте API ключи в .env файле")

        finally:
            await collector.close()

    except ImportError:
        click.echo("❌ Модуль exchange_collector не найден")
        click.echo("💡 Создайте файл из артефакта 'Исправленный Exchange Collector'")
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}")


async def _ai_analyze_market(symbol: str, mock: bool):
    """AI анализ рынка с обработкой ошибок"""
    try:
        from utils.helpers import create_sample_data
        from ai.mock_analyzer import MockAIAnalyzer

        # Создаем тестовые данные
        ohlcv_data = create_sample_data(symbol, periods=100)

        if mock or True:  # Всегда используем mock пока
            analyzer = MockAIAnalyzer()
            click.echo("🤖 Использование Mock AI анализатора")

        click.echo(f"🔍 Анализ {symbol}...")
        analysis = await analyzer.analyze_market(ohlcv_data, symbol)

        # Отображение результатов
        click.echo(f"\n🎯 AI Анализ {symbol}:")
        click.echo(f"📈 Рекомендация: {analysis['action']}")
        click.echo(f"💪 Сила сигнала: {analysis['signal_strength']:.2f}")
        click.echo(f"🎯 Уверенность: {analysis['confidence']:.1%}")
        click.echo(f"⚠️ Уровень риска: {analysis['risk_level']}")
        click.echo(f"💭 Обоснование: {analysis['reasoning']}")

        if analysis['action'] != 'HOLD':
            click.echo(f"💰 Предлагаемая цена входа: ${analysis['suggested_entry']:.2f}")

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


async def _run_trading_engine():
    """Запуск торгового движка"""
    click.echo("🚀 Запуск торгового движка...")
    click.echo("⚠️ Phase 0: Только демонстрация, реальная торговля отключена")

    try:
        # Пытаемся запустить демо режим
        await _run_demo()
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
        click.echo("💡 Обновите main.py из артефакта 'Исправленный main.py'")
    except Exception as e:
        click.echo(f"❌ Ошибка демо режима: {e}")


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        click.echo(f"💥 Критическая ошибка CLI: {e}")
        logger.error(f"CLI error: {e}")
        logger.error(traceback.format_exc())