#!/usr/bin/env python3
"""
Скрипт для быстрого создания всех файлов проекта
Запустите этот файл в PyCharm: Right Click → Run 'create_files'
"""

import os
from pathlib import Path

# Словарь: путь к файлу → содержимое
FILES_CONTENT = {
    "requirements.txt": """ccxt>=4.2.0
pandas>=2.0.0
numpy>=1.24.0
python-dotenv>=1.0.0
click>=8.1.0
pydantic>=2.5.0
aiohttp>=3.9.0
asyncio-mqtt>=0.13.0
redis>=5.0.0
psycopg2-binary>=2.9.0
sqlalchemy>=2.0.0
loguru>=0.7.0
pyyaml>=6.0
requests>=2.31.0""",

    "requirements-dev.txt": """# Разработка и тестирование
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
black>=23.7.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.5.0

# Дополнительные инструменты
ipython>=8.14.0
jupyter>=1.0.0
pre-commit>=3.3.0""",

    ".env.example": """# Общие настройки
APP_NAME="Crypto AI Trader"
DEBUG=false
LOG_LEVEL="INFO"

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# База данных
DATABASE_URL="sqlite:///./crypto_trader.db"
REDIS_URL="redis://localhost:6379"

# Bybit API (Testnet)
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_API_SECRET=your_bybit_api_secret_here
BYBIT_TESTNET=true

# Binance API (Testnet)
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
BINANCE_TESTNET=true""",

    ".gitignore": """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
logs/
*.db
secrets/
!secrets/.env.example
data/historical/
backtest_results/
*.pid""",

    "config/__init__.py": """from .settings import Settings
from .trading_config import TradingConfig

__all__ = ['Settings', 'TradingConfig']""",

    "config/settings.py": """from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Общие настройки
    app_name: str = "Crypto AI Trader"
    debug: bool = False
    log_level: str = "INFO"

    # API настройки
    openai_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None

    # База данных
    database_url: str = "sqlite:///./crypto_trader.db"
    redis_url: str = "redis://localhost:6379"

    # Биржи
    bybit_api_key: Optional[str] = None
    bybit_api_secret: Optional[str] = None
    bybit_testnet: bool = True

    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    binance_testnet: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()""",

    "config/trading_config.py": """from pydantic import BaseModel
from typing import Dict, List
from decimal import Decimal

class RiskConfig(BaseModel):
    max_position_size_percent: float = 2.0  # % от депозита на сделку
    max_daily_loss_percent: float = 5.0     # % максимальной дневной просадки
    max_drawdown_percent: float = 15.0      # % максимальной общей просадки
    stop_loss_percent: float = 2.0          # % стоп-лосс
    take_profit_percent: float = 4.0        # % тейк-профит

class TradingPair(BaseModel):
    symbol: str
    min_quantity: Decimal
    tick_size: Decimal
    enabled: bool = True

class TradingConfig(BaseModel):
    # Торгуемые пары
    trading_pairs: List[TradingPair] = [
        TradingPair(symbol="BTCUSDT", min_quantity=Decimal("0.001"), tick_size=Decimal("0.1")),
        TradingPair(symbol="ETHUSDT", min_quantity=Decimal("0.01"), tick_size=Decimal("0.01")),
        TradingPair(symbol="SOLUSDT", min_quantity=Decimal("0.1"), tick_size=Decimal("0.001")),
    ]

    # Таймфреймы для анализа
    timeframes: List[str] = ["5m", "15m", "1h", "4h"]
    primary_timeframe: str = "15m"

    # Риск-менеджмент
    risk: RiskConfig = RiskConfig()

    # Индикаторы
    technical_indicators: Dict[str, Dict] = {
        "rsi": {"period": 14, "overbought": 70, "oversold": 30},
        "ema_fast": {"period": 9},
        "ema_slow": {"period": 21},
        "volume_sma": {"period": 20}
    }""",

    "cli.py": """import click
import asyncio
from loguru import logger
from config import Settings, TradingConfig
from utils.logger import setup_logger

# Настройка логирования
setup_logger()

@click.group()
def cli():
    \"\"\"Crypto AI Trader CLI\"\"\"
    pass

@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Торговая пара')
@click.option('--timeframe', default='5m', help='Таймфрейм')
@click.option('--limit', default=100, help='Количество свечей')
def analyze(symbol, timeframe, limit):
    \"\"\"Анализ рынка\"\"\"
    asyncio.run(_analyze_market(symbol, timeframe, limit))

@cli.command()
@click.option('--exchange', default='bybit', help='Биржа для тестирования')
def test_connection(exchange):
    \"\"\"Тест подключения к бирже\"\"\"
    asyncio.run(_test_exchange_connection(exchange))

@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Торговая пара')
@click.option('--mock', is_flag=True, help='Использовать mock AI')
def ai_analyze(symbol, mock):
    \"\"\"AI анализ рынка\"\"\"
    asyncio.run(_ai_analyze_market(symbol, mock))

@cli.command()
def run():
    \"\"\"Запуск торгового движка\"\"\"
    asyncio.run(_run_trading_engine())

# Базовые реализации команд (будут расширены позже)
async def _analyze_market(symbol: str, timeframe: str, limit: int):
    click.echo(f"🔍 Анализ {symbol} на {timeframe} (Phase 0 - базовая версия)")
    click.echo("📝 Для полного функционала создайте остальные модули из артефактов")

async def _test_exchange_connection(exchange: str):
    click.echo(f"🔌 Тест подключения к {exchange}")
    click.echo("📝 Для полного функционала создайте exchange_collector.py")

async def _ai_analyze_market(symbol: str, mock: bool):
    click.echo(f"🤖 AI анализ {symbol} (Mock режим: {mock})")
    click.echo("📝 Для полного функционала создайте mock_analyzer.py")

async def _run_trading_engine():
    click.echo("🚀 Запуск торгового движка (Phase 0)")
    click.echo("📝 Для полного функционала создайте engine.py")

if __name__ == "__main__":
    cli()""",

    "main.py": """\"\"\"
Главная точка входа в приложение
\"\"\"
import asyncio
from loguru import logger

async def main():
    \"\"\"Главная функция\"\"\"
    logger.info("Запуск Crypto AI Trading Bot")
    logger.info("Phase 0 - Базовая версия")
    logger.info("Для полного функционала создайте все модули из артефактов")

    # Здесь будет полная реализация после создания всех файлов
    print("🤖 Crypto AI Trading Bot")
    print("📋 Используйте CLI для работы: python cli.py --help")

if __name__ == "__main__":
    asyncio.run(main())""",

    # Основные __init__.py файлы
    "core/__init__.py": "",
    "data/__init__.py": "",
    "ai/__init__.py": "",
    "utils/__init__.py": "",
    "trading/__init__.py": "",
    "risk/__init__.py": "",
    "notifications/__init__.py": "",
    "backtest/__init__.py": "",
    "api/__init__.py": "",
    "bot/__init__.py": "",
    "tests/__init__.py": "",
    "data/collectors/__init__.py": "",
    "data/processors/__init__.py": "",
    "data/storage/__init__.py": "",

    "README.md": """# 🤖 Crypto AI Trading Bot

## 📋 Phase 0 - Базовая структура проекта

Это базовая структура для AI торгового бота. 

### 🚀 Быстрый старт:

1. **Создайте остальные файлы** из артефактов Claude
2. **Настройте виртуальное окружение:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\\Scripts\\activate  # Windows
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Настройте конфигурацию:**
   ```bash
   cp .env.example .env
   # Отредактируйте .env с вашими API ключами
   ```

5. **Тест CLI:**
   ```bash
   python cli.py --help
   ```

### 📁 Следующие файлы нужно создать:

Из артефакта "Phase 0 - Стартовый код":
- `core/exceptions.py`
- `core/engine.py`  
- `data/collectors/exchange_collector.py`
- `ai/mock_analyzer.py`
- `utils/logger.py`

Из артефакта "Дополнительные файлы":
- `data/processors/technical_processor.py`
- `trading/strategies/base_strategy.py`
- `trading/strategies/simple_momentum.py`
- `tests/test_basic.py`

### ⚠️ Важно:
- Используйте только testnet API ключи
- Никогда не давайте права на вывод средств
- Начинайте с малых сумм для тестирования

🎯 **Цель Phase 0:** Создать рабочую основу для дальнейшего развития AI торгового бота."""
}


def create_file(file_path: str, content: str):
    """Создание файла с содержимым"""
    path = Path(file_path)

    # Создаем директории если их нет
    path.parent.mkdir(parents=True, exist_ok=True)

    # Записываем содержимое
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Создан: {file_path}")


def main():
    """Создание всех базовых файлов"""
    print("🚀 Создание базовых файлов проекта...")

    created_count = 0
    for file_path, content in FILES_CONTENT.items():
        try:
            create_file(file_path, content)
            created_count += 1
        except Exception as e:
            print(f"❌ Ошибка создания {file_path}: {e}")

    print(f"\n🎉 Создано {created_count} базовых файлов!")
    print("\n📋 Следующие шаги:")
    print("1. Удалите этот файл (create_files.py)")
    print("2. Создайте остальные .py файлы из артефактов Claude вручную")
    print("3. Настройте virtual environment в PyCharm")
    print("4. Установите зависимости: pip install -r requirements.txt")
    print("5. Скопируйте .env.example в .env и настройте API ключи")
    print("6. Тест: python cli.py --help")

    print("\n📁 Критически важные файлы для создания:")
    print("   - core/exceptions.py")
    print("   - core/engine.py")
    print("   - data/collectors/exchange_collector.py")
    print("   - ai/mock_analyzer.py")
    print("   - utils/logger.py")


if __name__ == "__main__":
    main()