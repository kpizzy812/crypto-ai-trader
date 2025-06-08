#!/usr/bin/env python3
"""
Скрипт быстрого деплоя и проверки системы
"""
import subprocess
import sys
import os
import json
from pathlib import Path
from datetime import datetime


def print_header(text):
    """Красивый заголовок"""
    print(f"\n{'=' * 60}")
    print(f"🚀 {text}")
    print(f"{'=' * 60}")


def print_step(step, text):
    """Шаг выполнения"""
    print(f"\n{step}️⃣ {text}")


def run_command(command, description="", check=True):
    """Выполнение команды с логированием"""
    if description:
        print(f"   📋 {description}")

    print(f"   💻 {command}")

    try:
        result = subprocess.run(
            command.split() if isinstance(command, str) else command,
            capture_output=True,
            text=True,
            check=check
        )

        if result.stdout:
            print(f"   ✅ {result.stdout.strip()}")

        return result.returncode == 0, result.stdout, result.stderr

    except subprocess.CalledProcessError as e:
        print(f"   ❌ Ошибка: {e}")
        if e.stderr:
            print(f"   📝 {e.stderr}")
        return False, "", e.stderr
    except Exception as e:
        print(f"   ❌ Неожиданная ошибка: {e}")
        return False, "", str(e)


def check_python_version():
    """Проверка версии Python"""
    print_step("1", "Проверка версии Python")

    version = sys.version_info
    print(f"   📊 Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("   ❌ Требуется Python 3.11 или выше")
        return False

    print("   ✅ Версия Python подходит")
    return True


def setup_virtual_environment():
    """Настройка виртуального окружения"""
    print_step("2", "Настройка виртуального окружения")

    if not os.path.exists("venv"):
        success, _, _ = run_command("python -m venv venv", "Создание venv")
        if not success:
            return False
    else:
        print("   ℹ️ Виртуальное окружение уже существует")

    # Определяем команду активации
    if os.name == 'nt':  # Windows
        activate_cmd = "venv\\Scripts\\activate"
        pip_cmd = "venv\\Scripts\\pip"
        python_cmd = "venv\\Scripts\\python"
    else:  # Linux/Mac
        activate_cmd = "source venv/bin/activate"
        pip_cmd = "venv/bin/pip"
        python_cmd = "venv/bin/python"

    print(f"   📋 Для активации используйте: {activate_cmd}")
    return True, pip_cmd, python_cmd


def install_dependencies(pip_cmd):
    """Установка зависимостей"""
    print_step("3", "Установка зависимостей")

    # Обновляем pip
    success, _, _ = run_command(f"{pip_cmd} install --upgrade pip", "Обновление pip")
    if not success:
        print("   ⚠️ Не удалось обновить pip, продолжаем...")

    # Устанавливаем основные зависимости
    success, _, _ = run_command(f"{pip_cmd} install -r requirements.txt", "Установка requirements.txt")
    if not success:
        return False

    # Устанавливаем dev зависимости если файл существует
    if os.path.exists("requirements-dev.txt"):
        success, _, _ = run_command(f"{pip_cmd} install -r requirements-dev.txt", "Установка dev зависимостей")
        if not success:
            print("   ⚠️ Не удалось установить dev зависимости, продолжаем...")

    return True


def setup_environment_file():
    """Настройка .env файла"""
    print_step("4", "Настройка файла окружения")

    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
            print("   ✅ Создан .env из .env.example")
        else:
            # Создаем базовый .env файл
            env_content = """# Crypto AI Trading Bot Configuration
APP_NAME="Crypto AI Trader"
DEBUG=false
LOG_LEVEL="INFO"

# OpenAI API (опционально)
OPENAI_API_KEY=your_openai_api_key_here

# Telegram Bot (опционально)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# База данных
DATABASE_URL="sqlite:///./crypto_trader.db"

# Bybit API (TESTNET)
BYBIT_API_KEY=your_bybit_testnet_api_key
BYBIT_API_SECRET=your_bybit_testnet_secret
BYBIT_TESTNET=true

# Binance API (TESTNET)
BINANCE_API_KEY=your_binance_testnet_api_key
BINANCE_API_SECRET=your_binance_testnet_secret
BINANCE_TESTNET=true
"""
            with open(".env", "w") as f:
                f.write(env_content)
            print("   ✅ Создан базовый .env файл")
    else:
        print("   ℹ️ Файл .env уже существует")

    print("   ⚠️ ВАЖНО: Отредактируйте .env файл и добавьте ваши API ключи!")
    return True


def create_directories():
    """Создание необходимых директорий"""
    print_step("5", "Создание директорий")

    directories = [
        "logs",
        "data/historical",
        "backtest_results",
        "web/static",
        "web/templates"
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"   📁 {directory}")

    print("   ✅ Все директории созданы")
    return True


def run_system_tests(python_cmd):
    """Запуск системных тестов"""
    print_step("6", "Запуск системных тестов")

    # Базовый тест импортов
    test_imports = """
try:
    from config import Settings, TradingConfig
    from utils.helpers import create_sample_data
    from ai.mock_analyzer import MockAIAnalyzer
    print("✅ Базовые импорты успешны")
    exit(0)
except Exception as e:
    print(f"❌ Ошибка импорта: {e}")
    exit(1)
"""

    with open("temp_test.py", "w") as f:
        f.write(test_imports)

    try:
        success, _, stderr = run_command(f"{python_cmd} temp_test.py", "Тест импортов")
        if not success:
            print(f"   ❌ Ошибка импортов: {stderr}")
            return False
    finally:
        if os.path.exists("temp_test.py"):
            os.remove("temp_test.py")

    # Комплексный тест
    success, stdout, stderr = run_command(
        f"{python_cmd} main.py --mode test",
        "Комплексное тестирование системы",
        check=False
    )

    if "ВСЕ ТЕСТЫ ПРОЙДЕНЫ" in stdout:
        print("   🎉 Все системные тесты прошли успешно!")
        return True
    else:
        print("   ⚠️ Некоторые тесты не прошли, но система может работать")
        print("   💡 Проверьте API ключи в .env для полного функционала")
        return True  # Не блокируем установку


def create_start_scripts():
    """Создание скриптов запуска"""
    print_step("7", "Создание скриптов запуска")

    # Windows batch файл
    windows_script = """@echo off
echo Starting Crypto AI Trading Bot...
call venv\\Scripts\\activate
python main.py --mode test
pause
"""

    with open("start_test.bat", "w") as f:
        f.write(windows_script)

    # Linux/Mac shell script
    unix_script = """#!/bin/bash
echo "Starting Crypto AI Trading Bot..."
source venv/bin/activate
python main.py --mode test
"""

    with open("start_test.sh", "w") as f:
        f.write(unix_script)

    # Делаем исполняемым на Unix
    if os.name != 'nt':
        os.chmod("start_test.sh", 0o755)

    print("   ✅ Созданы скрипты запуска:")
    print("   📝 start_test.bat (Windows)")
    print("   📝 start_test.sh (Linux/Mac)")

    return True


def generate_deployment_report():
    """Генерация отчета о деплое"""
    print_step("8", "Генерация отчета")

    report = {
        "deployment_date": datetime.now().isoformat(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "project_structure": {
            "env_file": os.path.exists(".env"),
            "venv": os.path.exists("venv"),
            "logs_dir": os.path.exists("logs"),
            "requirements": os.path.exists("requirements.txt")
        },
        "next_steps": [
            "1. Отредактируйте .env файл с вашими API ключами",
            "2. Получите тестовые средства на testnet биржах",
            "3. Запустите: python main.py --mode test",
            "4. При успешном тесте: python main.py --mode trading",
            "5. Для веб-интерфейса: python main.py --mode api"
        ],
        "useful_commands": {
            "comprehensive_test": "python main.py --mode test",
            "real_trading": "python main.py --mode trading",
            "backtest": "python main.py --mode backtest",
            "api_server": "python main.py --mode api",
            "live_position_test": "python main.py --mode live-test"
        }
    }

    with open("deployment_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("   ✅ Создан deployment_report.json")
    return True


def print_final_instructions():
    """Финальные инструкции"""
    print_header("УСТАНОВКА ЗАВЕРШЕНА")

    print("""
🎉 Crypto AI Trading Bot успешно установлен!

📋 СЛЕДУЮЩИЕ ШАГИ:

1️⃣ Настройка API ключей:
   📝 Отредактируйте файл .env
   🔑 Добавьте API ключи для testnet
   ⚠️ НЕ используйте mainnet ключи!

2️⃣ Получение тестовых средств:
   🌐 Bybit Testnet: https://testnet.bybit.com
   🌐 Binance Testnet: https://testnet.binance.vision
   💰 Получите тестовые USDT для торговли

3️⃣ Первый запуск:""")

    if os.name == 'nt':
        print("   🖱️ Запустите start_test.bat")
    else:
        print("   🖱️ Запустите ./start_test.sh")

    print("""   📝 Или вручную: python main.py --mode test

4️⃣ Режимы работы:
   🧪 Тестирование: python main.py --mode test
   🤖 Торговля: python main.py --mode trading
   📊 Бэктест: python main.py --mode backtest
   🌐 API сервер: python main.py --mode api
   💰 Тест позиции: python main.py --mode live-test

5️⃣ Веб-интерфейс:
   🚀 python main.py --mode api
   🌐 Откройте: http://localhost:8000

⚠️ ВАЖНЫЕ НАПОМИНАНИЯ:
   🔒 Всегда используйте testnet для начала
   💡 Начинайте с малых сумм
   📊 Изучите результаты бэктестов
   🛡️ Настройте риск-менеджмент

📚 Документация:
   📖 README.md - основная документация
   📊 deployment_report.json - отчет о деплое
   🔧 logs/ - логи системы

🆘 При проблемах:
   1. Проверьте логи в папке logs/
   2. Убедитесь что API ключи корректны
   3. Проверьте подключение к интернету
   4. Запустите: python main.py --mode test

Удачной торговли! 🚀📈
""")


def main():
    """Главная функция деплоя"""
    print_header("CRYPTO AI TRADING BOT - БЫСТРЫЙ ДЕПЛОЙ")

    print("🤖 Добро пожаловать в систему автоматического деплоя!")
    print("📋 Этот скрипт настроит все необходимое для работы торгового бота")

    # Проверяем, что находимся в правильной директории
    if not os.path.exists("main.py"):
        print("\n❌ Ошибка: Запустите скрипт из корневой директории проекта")
        print("💡 В директории должен быть файл main.py")
        return False

    try:
        # Шаг 1: Проверка Python
        if not check_python_version():
            return False

        # Шаг 2: Виртуальное окружение
        success, pip_cmd, python_cmd = setup_virtual_environment()
        if not success:
            return False

        # Шаг 3: Зависимости
        if not install_dependencies(pip_cmd):
            return False

        # Шаг 4: .env файл
        if not setup_environment_file():
            return False

        # Шаг 5: Директории
        if not create_directories():
            return False

        # Шаг 6: Тесты
        if not run_system_tests(python_cmd):
            print("   ⚠️ Продолжаем установку несмотря на ошибки тестов")

        # Шаг 7: Скрипты
        if not create_start_scripts():
            return False

        # Шаг 8: Отчет
        if not generate_deployment_report():
            return False

        # Финальные инструкции
        print_final_instructions()

        return True

    except KeyboardInterrupt:
        print("\n\n❌ Установка прервана пользователем")
        return False
    except Exception as e:
        print(f"\n\n💥 Критическая ошибка установки: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1

    if success:
        print(f"\n🎉 Деплой завершен успешно!")
    else:
        print(f"\n❌ Деплой завершен с ошибками")

    sys.exit(exit_code)