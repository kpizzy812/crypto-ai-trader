# СОЗДАНИЕ: scripts/setup_project.py
"""
Скрипт для первичной настройки проекта
"""
import os
import subprocess
import sys
from pathlib import Path


def setup_project():
    """Настройка проекта"""

    print("🚀 Настройка Crypto AI Trading Bot...")

    # Создание директорий
    directories = [
        "logs",
        "data/historical",
        "backtest_results",
        "secrets",
        "web/static",
        "web/templates"
    ]

    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"📁 Создана директория: {dir_path}")

    # Копирование .env файла
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
            print("📄 Создан файл .env из .env.example")
            print("⚠️ Отредактируйте .env файл с вашими API ключами!")
        else:
            print("❌ Файл .env.example не найден")

    # Установка зависимостей
    print("\n📦 Установка зависимостей...")
    result = subprocess.run([
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
    ])

    if result.returncode == 0:
        print("✅ Зависимости установлены успешно!")
    else:
        print("❌ Ошибка установки зависимостей")
        return False

    # Инициализация базы данных
    print("\n🗄️ Инициализация базы данных...")
    try:
        from data.storage.database import DatabaseManager
        db = DatabaseManager()
        print("✅ База данных инициализирована!")
    except Exception as e:
        print(f"⚠️ Ошибка инициализации БД: {e}")

    # Создание тестового файла с дашбордом
    dashboard_path = "web/templates/dashboard.html"
    if not os.path.exists(dashboard_path):
        print(f"⚠️ Создайте файл {dashboard_path} из артефакта 'Исправленный дашборд HTML'")

    print("\n🎉 Настройка завершена!")
    print("\n📋 Следующие шаги:")
    print("1. Отредактируйте .env файл с вашими API ключами")
    print("2. Создайте недостающие файлы из артефактов Claude")
    print("3. Запустите тесты: python scripts/run_tests.py")
    print("4. Запустите бота: python main.py --mode bot")
    print("5. Запустите API: python main.py --mode api")
    print("6. Откройте дашборд: http://localhost:8000")


if __name__ == "__main__":
    setup_project()