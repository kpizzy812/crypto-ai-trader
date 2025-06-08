# cli.py
import click
import asyncio
from loguru import logger
from config import Settings, TradingConfig
from core import TradingEngine
from data.collectors.exchange_collector import ExchangeDataCollector
from ai.mock_analyzer import MockAIAnalyzer
from utils.logger import setup_logger

# Настройка логирования
setup_logger()


@click.group()
def cli():
    """Crypto AI Trader CLI"""
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


# Реализация команд
async def _analyze_market(symbol: str, timeframe: str, limit: int):
    """Анализ рынка"""
    settings = Settings()
    collector = None

    try:
        # Подключение к бирже
        collector = ExchangeDataCollector(
            'bybit',
            settings.bybit_api_key,
            settings.bybit_api_secret,
            settings.bybit_testnet
        )

        logger.info(f"Анализ {symbol} на таймфрейме {timeframe}")

        # Получение данных
        ohlcv_data = await collector.get_ohlcv(symbol, timeframe, limit)
        ticker = await collector.get_ticker(symbol)

        # Простой технический анализ
        current_price = ohlcv_data['close'].iloc[-1]
        sma_20 = ohlcv_data['close'].rolling(20).mean().iloc[-1]
        volume_avg = ohlcv_data['volume'].rolling(20).mean().iloc[-1]
        current_volume = ohlcv_data['volume'].iloc[-1]

        # Результаты анализа
        click.echo(f"\n📊 Анализ {symbol}:")
        click.echo(f"💰 Текущая цена: ${current_price:,.2f}")
        click.echo(f"📈 SMA(20): ${sma_20:,.2f}")
        click.echo(f"📊 Объем: {current_volume:,.0f} (ср. {volume_avg:,.0f})")
        click.echo(f"📈 Тренд: {'↗️ Восходящий' if current_price > sma_20 else '↘️ Нисходящий'}")
        click.echo(f"🔊 Активность: {'Высокая' if current_volume > volume_avg * 1.5 else 'Обычная'}")

        # Отображение последних свечей
        click.echo(f"\n📈 Последние 5 свечей:")
        recent_data = ohlcv_data.tail(5)
        for idx, row in recent_data.iterrows():
            direction = "🟢" if row['close'] > row['open'] else "🔴"
            click.echo(
                f"{direction} {idx.strftime('%H:%M')} | O: {row['open']:.2f} H: {row['high']:.2f} L: {row['low']:.2f} C: {row['close']:.2f}")

    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        click.echo(f"❌ Ошибка: {e}")
    finally:
        # ВАЖНО: Закрываем соединение
        if collector:
            await collector.close()


async def _test_exchange_connection(exchange: str):
    """Тест подключения к бирже"""
    settings = Settings()
    collector = None

    try:
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

        success = await collector.test_connection()

        if success:
            click.echo(f"✅ Подключение к {exchange} успешно!")

            # Получение информации о рынках
            try:
                ticker = await collector.get_ticker('BTCUSDT')
                click.echo(f"📊 BTC/USDT: ${ticker['last']:,.2f}")
            except Exception as e:
                click.echo(f"⚠️  Не удалось получить тикер: {e}")
        else:
            click.echo(f"❌ Ошибка подключения к {exchange}")

    except Exception as e:
        logger.error(f"Ошибка подключения: {e}")
        click.echo(f"❌ Ошибка: {e}")
    finally:
        # ВАЖНО: Закрываем соединение
        if collector:
            await collector.close()


async def _ai_analyze_market(symbol: str, mock: bool):
    """AI анализ рынка"""
    settings = Settings()
    collector = None

    try:
        # Получение рыночных данных
        collector = ExchangeDataCollector(
            'bybit',
            settings.bybit_api_key,
            settings.bybit_api_secret,
            settings.bybit_testnet
        )

        ohlcv_data = await collector.get_ohlcv(symbol, '15m', 100)

        # AI анализ
        if mock or not settings.openai_api_key:
            analyzer = MockAIAnalyzer()
            click.echo("🤖 Использование Mock AI анализатора")
        else:
            # Здесь будет реальный OpenAI анализатор
            analyzer = MockAIAnalyzer()
            click.echo("🤖 Mock AI (OpenAI пока не подключен)")

        click.echo(f"🔍 Анализ {symbol}...")
        analysis = await analyzer.analyze_market(ohlcv_data, symbol)

        # Отображение результатов
        click.echo(f"\n🎯 AI Анализ {symbol}:")
        click.echo(f"📈 Рекомендация: {analysis['action']}")
        click.echo(f"💪 Сила сигнала: {analysis['signal_strength']:.2f}")
        click.echo(f"🎯 Уверенность: {analysis['confidence']:.1%}")
        click.echo(f"⚠️  Уровень риска: {analysis['risk_level']}")
        click.echo(f"💭 Обоснование: {analysis['reasoning']}")

        if analysis['action'] != 'HOLD':
            click.echo(f"💰 Предлагаемая цена входа: ${analysis['suggested_entry']:.2f}")

        # Рекомендации по риск-менеджменту
        if analysis['confidence'] > 0.7 and analysis['action'] != 'HOLD':
            click.echo(f"\n✅ Сигнал достаточно уверенный для торговли")
        else:
            click.echo(f"\n⚠️  Сигнал неуверенный, рекомендуется воздержаться от торговли")

    except Exception as e:
        logger.error(f"Ошибка AI анализа: {e}")
        click.echo(f"❌ Ошибка: {e}")
    finally:
        # ВАЖНО: Закрываем соединение
        if collector:
            await collector.close()


async def _run_trading_engine():
    """Запуск торгового движка"""
    settings = Settings()
    trading_config = TradingConfig()

    click.echo("🚀 Запуск торгового движка...")
    click.echo("⚠️  Phase 0: Только демонстрация, реальная торговля отключена")

    engine = TradingEngine(settings, trading_config)

    try:
        await engine.start()
    except KeyboardInterrupt:
        click.echo("\n⏹️  Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"Ошибка движка: {e}")
        click.echo(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    cli()