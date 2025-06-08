# ИСПРАВЛЕНИЕ: main.py - полная версия
"""
Главная точка входа в приложение
"""
import asyncio
import uvicorn
from loguru import logger
from config.settings import Settings
from config.trading_config import TradingConfig
from core.engine import TradingEngine
from utils.logger import setup_logger
from api.main import app


async def run_trading_bot():
    """Запуск торгового бота"""
    # Настройка логирования
    setup_logger("INFO", "logs/trading_bot.log")

    # Загрузка конфигурации
    settings = Settings()
    trading_config = TradingConfig()

    logger.info("Запуск Crypto AI Trading Bot")

    # Создание и запуск торгового движка
    engine = TradingEngine(settings, trading_config)

    try:
        await engine.start()
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        await engine.stop()


async def run_web_api():
    """Запуск веб API"""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Главная функция - запуск и бота и API"""
    import argparse

    parser = argparse.ArgumentParser(description='Crypto AI Trading Bot')
    parser.add_argument('--mode', choices=['bot', 'api', 'both'],
                        default='both', help='Режим запуска')
    args = parser.parse_args()

    if args.mode == 'bot':
        await run_trading_bot()
    elif args.mode == 'api':
        await run_web_api()
    else:  # both
        # Запуск обоих компонентов параллельно
        await asyncio.gather(
            run_trading_bot(),
            run_web_api()
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")