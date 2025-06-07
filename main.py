# main.py
"""
Главная точка входа в приложение
"""
import asyncio
from loguru import logger
from config import Settings, TradingConfig
from core import TradingEngine
from utils.logger import setup_logger

async def main():
    """Главная функция"""
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

if __name__ == "__main__":
    asyncio.run(main())
