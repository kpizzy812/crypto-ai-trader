# utils/logger.py
from loguru import logger
import sys


def setup_logger(level: str = "INFO", log_file: str = None):
    """Настройка логирования"""
    import os

    # Удаляем стандартный обработчик
    logger.remove()

    # Консольный вывод
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )

    # Файловый вывод (если указан)
    if log_file:
        # Создаем директорию для логов если её нет
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        logger.add(
            log_file,
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="7 days"
        )

    return logger